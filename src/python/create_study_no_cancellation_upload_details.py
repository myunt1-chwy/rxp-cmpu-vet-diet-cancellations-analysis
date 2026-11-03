"""Current missing-reason line statuses with the report's retained uploads."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import duckdb
import pandas as pd

from src.python import create_study_upload_coverage_by_cancel_reason as coverage
from src.python.markdown_tables import markdown_table, write_text

ROOT = coverage.ROOT
NAME = 'study-no-cancellation-upload-details'
PARENT = ROOT / 'data' / coverage.NAME / coverage.PERIOD
DATA = ROOT / 'data' / NAME / coverage.PERIOD
SQL = ROOT / 'src/sql/study_no_cancellation_upload_details.sql'
MATCH = coverage.MATCH
KEYS = coverage.KEYS
GROUPS = ['rx_status', 'order_status', 'order_cancellation_reason', 'line_item_status']
COUNTS = ['prescriptions', 'line_items', 'with_upload', 'without_upload']
VERIFY_SQL = '''SELECT s.rx_status, s.order_status,
 COALESCE(s.order_cancellation_reason, '[No recorded cancellation reason]') order_cancellation_reason,
 s.line_item_status,
 COUNT(DISTINCT s.rx_id) prescriptions,
 COUNT(DISTINCT (s.order_id,s.order_line_id)) line_items,
 COUNT(DISTINCT CASE WHEN u.upload_id IS NOT NULL THEN (s.order_id,s.order_line_id) END) with_upload,
 COUNT(DISTINCT CASE WHEN u.upload_id IS NULL THEN (s.order_id,s.order_line_id) END) without_upload
FROM snapshot s LEFT JOIN uploads u
 ON s.rx_id=u.rx_id AND s.customer_id=u.customer_id
 AND s.order_id=u.order_id AND s.order_line_id=u.order_line_id
WHERE COALESCE(NULLIF(TRIM(s.order_cancellation_reason),''), '[No recorded cancellation reason]') = ?
GROUP BY ALL ORDER BY ALL'''


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def frozen_inputs(cancellation_reason=coverage.base.MISSING_REASON):
    manifest = json.loads((PARENT / 'analysis.json').read_text())
    hashes = {}
    frames = []
    for name in ['study-lines.parquet', 'upload-associations.parquet']:
        path = PARENT / name
        hashes[name] = digest(path)
        if hashes[name] != manifest['exports'][name]:
            raise ValueError(f'Frozen input fingerprint differs: {path}')
        frames.append(pd.read_parquet(path))
    study, uploads = frames
    expected_lines, expected_orders = {
        coverage.base.MISSING_REASON: (40864, 38413), 'aged order': (26443, 24408)
    }[cancellation_reason]
    cohort = study.loc[study.cancellation_reason.eq(cancellation_reason)].copy()
    if (len(cohort) != expected_lines or cohort.order_id.nunique() != expected_orders
            or not cohort.rx_id.is_unique or cohort.duplicated(KEYS).any()
            or cohort[MATCH].isna().any().any()):
        raise ValueError('Frozen cohort identity or totals changed')
    if (uploads[MATCH + ['upload_id']].isna().any().any()
            or uploads.duplicated(MATCH + ['upload_id']).any()):
        raise ValueError('Missing or duplicated frozen upload identity')
    return cohort, uploads, hashes


def analyze(source, cohort, uploads, cancellation_reason=coverage.base.MISSING_REASON):
    source = source.rename(columns=str.lower).copy()
    source.rx_id = source.rx_id.astype('string').str.strip()
    for col in MATCH[1:] + ['line_customer_id']:
        source[col] = source[col].map(coverage.base.identifier)
    if (not source.rx_id.is_unique or not source.source_rows.eq(1).all()
            or source[MATCH + ['line_customer_id']].isna().any().any()
            or not source.shipment_rows.gt(0).all()):
        raise ValueError('Missing or duplicated prescription/first-order-line source')
    for col in ['customer_variants', 'order_status_variants', 'line_status_variants', 'reason_variants']:
        if not source[col].eq(1).all():
            raise ValueError(f'Conflicting shipment-to-line values: {col}')
    if not source.customer_id.eq(source.line_customer_id).all():
        raise ValueError('Prescription and line customer IDs differ')
    check = cohort[MATCH].merge(source[MATCH], on=MATCH, how='outer',
                                validate='one_to_one', indicator=True)
    if not check['_merge'].eq('both').all():
        raise ValueError('Extracted identity differs from frozen first-order membership')
    for col in GROUPS:
        source[col] = source[col].astype('string').str.strip().replace('', pd.NA)
    if source.extracted_at_utc.nunique(dropna=False) != 1 or source.extracted_at_utc.isna().any():
        raise ValueError('Expected one extraction timestamp')
    extracted = pd.to_datetime(source.extracted_at_utc.iloc[0], utc=True).isoformat()
    eligible = source.order_cancellation_reason.fillna(coverage.base.MISSING_REASON).eq(cancellation_reason)
    retained = source.loc[eligible].copy()
    excluded = source.loc[~eligible].copy()
    counts = uploads.groupby(MATCH, as_index=False).agg(upload_count=('upload_id', 'nunique'))
    retained = retained.merge(counts, on=MATCH, how='left', validate='one_to_one')
    retained['upload_count'] = retained.upload_count.fillna(0).astype('int64')
    retained['has_upload'] = retained.upload_count.gt(0)
    display = retained.copy()
    display[GROUPS] = display[GROUPS].fillna('[Missing]')
    display['order_cancellation_reason'] = cancellation_reason
    summary = display.groupby(GROUPS, as_index=False).agg(
        prescriptions=('rx_id', 'nunique'), line_items=('rx_id', 'size'),
        with_upload=('has_upload', 'sum'))
    summary['without_upload'] = summary.line_items - summary.with_upload
    summary = summary.sort_values(GROUPS).reset_index(drop=True)
    with duckdb.connect() as connection:
        connection.register('snapshot', source)
        connection.register('uploads', uploads)
        independent = connection.execute(VERIFY_SQL, [cancellation_reason]).df()
    independent[GROUPS] = independent[GROUPS].fillna('[Missing]')
    independent = independent.sort_values(GROUPS).reset_index(drop=True)
    pd.testing.assert_frame_equal(summary, independent, check_dtype=False)
    if summary.line_items.sum() != len(retained) or len(retained) + len(excluded) != len(cohort):
        raise ValueError('Retained/excluded totals do not reconcile')
    if summary.prescriptions.sum() != retained.rx_id.nunique():
        raise ValueError('Prescription groups do not reconcile to distinct retained RX IDs')
    audit = dict(cancellation_reason=cancellation_reason,
                 parent_lines=len(cohort), parent_orders=cohort.order_id.nunique(),
                 retained_lines=len(retained), retained_prescriptions=retained.rx_id.nunique(),
                 retained_orders=retained.order_id.nunique(),
                 excluded_lines=len(excluded), extracted_at_utc=extracted,
                 excluded_by_reason=excluded.order_cancellation_reason.value_counts().to_dict(),
                 verification='Every group reconciles to independent DuckDB distinct prescription and physical-line counts')
    return retained, excluded, summary, audit


def latex_rows(summary, highlight=False):
    def escape(value):
        return str(value).replace('\\', r'\textbackslash{}').replace('_', r'\_').replace('&', r'\&').replace('%', r'\%').replace('#', r'\#')

    rows = []
    for row in summary.itertuples(index=False, name=None):
        if highlight:
            rows.append(r'\rowcolor{yellow!35}')
        rows.append(' & '.join([escape(v) for v in row[:4]] + [f'{v:,}' for v in row[4:]]) + r' \\')
    totals = summary[COUNTS].sum()
    rows += [r'\midrule', r'\multicolumn{4}{l}{Total} & ' +
             ' & '.join(f'{v:,}' for v in totals) + r' \\']
    return '\n'.join(rows)


def latex_table(summary, audit):
    return r'''% Generated by make study-no-cancellation-upload-details.
\begin{landscape}
\begin{table}[htbp]
\centering
\caption{Prescription and order statuses for first-order lines with no currently recorded cancellation reason, by retained upload coverage.}
\label{tab:study-no-cancellation-upload-details}
\small
\setlength{\tabcolsep}{6pt}
\begin{tabular}{llllrrrr}
\toprule
RX\_STATUS & Order status & Order cancellation reason & Line-item status & Prescriptions & Line items & With upload & Without upload \\
\midrule
''' + latex_rows(summary) + r'''
\bottomrule
\end{tabular}
\begin{minipage}{\linewidth}
\footnotesize
\textit{Notes:} Start with the frozen ''' + f"{audit['parent_lines']:,}" + r''' prescriptions/first-order lines
(''' + f"{audit['parent_orders']:,}" + r''' orders) in the no-recorded-reason rows of
Table~\ref{tab:study-upload-coverage-by-cancellation-reason}.
At the status extraction (''' + audit['extracted_at_utc'] + r'''),
''' + f"{audit['retained_lines']:,}" + r''' lines still had a null or blank reason;
''' + f"{audit['excluded_lines']:,}" + r''' lines with newly populated reasons are excluded and retained in the audit.
Prescriptions count distinct \texttt{RX\_ID}s and equal line-item counts in this
one-prescription-per-first-order-line cohort. Each physical first-order line
counts once. Validate both first-order keys and
customer identity; collapse shipment rows only when their customer, statuses and
reason agree. Status codes are shown as recorded; a missing cancellation reason
does not establish that an order shipped successfully.

With/without upload counts refer to lines with/without at least one matched
entity, not the number of entities. Reuse the frozen HCDM diet-prescription
upload associations from the preceding table: match prescription ID, customer ID,
order ID and line ID. The August 1--October 25, 2026 inclusive UTC discovery window,
unknown-creation-time rule and all entity states are retained. Uploads need not
precede cancellation and are not refreshed with these statuses.
\end{minipage}
\end{table}
\input{../autogenerated/study_aged_order_upload_coverage}
\end{landscape}
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cached', action='store_true')
    args = parser.parse_args()
    try:
        cohort, uploads, hashes = frozen_inputs()
        ids = json.dumps(sorted(cohort.rx_id.tolist()), separators=(',', ':')).replace("'", "''")
        sql = SQL.read_text().replace('__RX_IDS_JSON__', ids)
        expected = dict(version=1, frozen_inputs=hashes,
                        sql_sha256=hashlib.sha256(sql.encode()).hexdigest())
        DATA.mkdir(parents=True, exist_ok=True)
        source_path = DATA / 'source.parquet'
        if args.cached:
            metadata = json.loads((DATA / 'source.json').read_text())
            if any(metadata.get(k) != v for k, v in expected.items()) or digest(source_path) != metadata['parquet_sha256']:
                raise ValueError('Status snapshot or input/query fingerprint differs')
            source = pd.read_parquet(source_path)
        else:
            generated = ROOT / 'src/autogenerated' / NAME
            generated.mkdir(parents=True, exist_ok=True)
            query_path = generated / 'extract.sql'
            write_text(query_path, sql)
            pending = DATA / 'pending-source.parquet'
            subprocess.run([sys.executable, str(ROOT / '.agents/skills/rxp-sql/scripts/run_snowflake_query.py'),
                            str(query_path), '--output-parquet', str(pending.relative_to(ROOT)),
                            '--sql-log-dir', str((generated / 'sql-history').relative_to(ROOT))],
                           check=True, cwd=ROOT)
            source = pd.read_parquet(pending)
        retained, excluded, summary, audit = analyze(source, cohort, uploads)
        if not args.cached:
            pending.replace(source_path)
            write_text(DATA / 'source.json', json.dumps(dict(expected, parquet_sha256=digest(source_path),
                       extracted_at_utc=audit['extracted_at_utc']), indent=2) + '\n')
        frames = {'retained-lines': retained, 'excluded-lines': excluded, 'summary': summary}
        for name, frame in frames.items():
            frame.to_parquet(DATA / f'{name}.parquet', index=False)
        write_text(DATA / 'verify.sql', '-- Bind parameter: ' + audit['cancellation_reason'] + '\n' + VERIFY_SQL)
        write_text(DATA / 'audit.json', json.dumps(audit, indent=2) + '\n')
        write_text(DATA / 'analysis.json', json.dumps(dict(expected, generator_sha256=digest(Path(__file__)),
                   exports={p.name: digest(p) for p in DATA.glob('*.parquet')}), indent=2) + '\n')
        tables = ROOT / 'outputs/tables' / NAME / coverage.PERIOD
        tables.mkdir(parents=True, exist_ok=True)
        total = {**{k: '' for k in GROUPS}, 'rx_status': 'TOTAL', **summary[COUNTS].sum().to_dict()}
        table = pd.concat([summary, pd.DataFrame([total])], ignore_index=True)
        write_text(tables / 'summary.md', '# No-current-cancellation-reason upload details\n\n' +
                   markdown_table(table) + '\n\nAudit: ' + json.dumps(audit) + '\n')
        write_text(ROOT / 'src/autogenerated/study_no_cancellation_upload_details.tex', latex_table(summary, audit))
        print(json.dumps(audit, indent=2))
        print(table.to_string(index=False))
    except (OSError, ValueError, KeyError) as error:
        raise SystemExit(f'{error}\nRestore the frozen coverage inputs if needed, then run: '
                         'make study-no-cancellation-upload-details') from error


if __name__ == '__main__':
    main()

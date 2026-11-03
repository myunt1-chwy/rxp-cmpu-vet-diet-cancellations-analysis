"""First-order-line upload coverage by reason and status in the frozen study."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import duckdb
import pandas as pd

from scripts import summarize_study_population_prescription_decisions as decisions
from src.python import create_cmpu_upload_entity_state_change_distributions as entity
from src.python import create_opportunity_order_cancellation_summary as base
from src.python.markdown_tables import markdown_table, write_text

ROOT = base.ROOT
DATA = ROOT / 'data'
NAME = 'study-upload-coverage-by-cancel-reason'
PERIOD = '2026-08-15_2026-10-14'
BASELINE = DATA / 'cmpu-first-order-line-status/2026-08-15_2026-10-15_uploads-from-2026-08-01_uploads-end-2026-10-26_accepted-state-change_order-placed_block-reasons'
KEYS = ['order_id', 'order_line_id']
MATCH = ['rx_id', 'customer_id'] + KEYS
CUTOFF = pd.Timestamp('2026-10-27', tz='UTC')
PARAMS = entity.parameters('2026-08-15', '2026-10-15', '2026-08-01', '2026-10-27')
VERIFY_SQL = """WITH joined AS (
 SELECT b.*,u.upload_id,u.state_name FROM study b LEFT JOIN uploads u
 ON b.rx_id=u.rx_id AND b.customer_id=u.customer_id
 AND b.order_id=u.order_id AND b.order_line_id=u.order_line_id
), classified AS (
 SELECT *,CASE WHEN reason_key='aged order' AND (cancel_time IS NULL OR cancel_time>TIMESTAMPTZ '2026-10-27 00:00:00+00')
 THEN '[Aged order outside cutoff]' ELSE reason_key END AS category FROM joined
), counts AS (
 SELECT CASE WHEN GROUPING(category)=1 THEN 'total' ELSE 'reason' END AS row_type,
 CASE WHEN GROUPING(category)=1 THEN 'TOTAL' ELSE category END AS cancellation_reason,
 CASE WHEN GROUPING(category)=1 THEN 'All' ELSE line_item_status END AS line_item_status,
 COUNT(DISTINCT order_id) orders,COUNT(DISTINCT rx_id) prescriptions,
 COUNT(DISTINCT (order_id,order_line_id)) line_items,
 COUNT(DISTINCT CASE WHEN upload_id IS NOT NULL THEN (order_id,order_line_id) END) lines_with_upload,
 COUNT(DISTINCT upload_id) uploads,
 COUNT(DISTINCT CASE WHEN state_name='ACCEPTED' THEN upload_id END) accepted_uploads,
 COUNT(DISTINCT CASE WHEN state_name='REJECTED' THEN upload_id END) rejected_uploads
 FROM classified GROUP BY GROUPING SETS ((category,line_item_status),())
) SELECT *,100.0*lines_with_upload/NULLIF(line_items,0) upload_coverage_pct
FROM counts ORDER BY row_type,cancellation_reason,line_item_status"""


def load_source(directory):
    metadata = json.loads((directory / 'source.json').read_text())
    source = directory / 'source.parquet'
    if base.digest(source) != metadata['parquet_sha256']:
        raise ValueError(f'Source fingerprint differs: {source}')
    if hashlib.sha256(metadata['sql'].encode()).hexdigest() != metadata['sql_sha256']:
        raise ValueError(f'Source SQL fingerprint differs: {directory}')
    return pd.read_parquet(source).rename(columns=str.lower), metadata


def reason_key(series):
    return series.astype('string').str.strip().str.casefold().replace('', pd.NA).fillna(base.MISSING_REASON)


def analyze(baseline, decision_source, upload_source):
    matched = baseline.loc[baseline.line_source_rows.gt(0)].copy()
    if not matched.rx_id.is_unique or not matched.cancel_reason_variants.eq(1).all():
        raise ValueError('Conflicting frozen prescription or cancellation membership')
    if not matched.line_status_variants.eq(1).all():
        raise ValueError('Conflicting frozen shipment-to-line statuses')
    if (matched.matched_order_id.ne(matched.first_order_id).any()
            or matched.matched_order_line_id.ne(matched.first_order_line_id).any()):
        raise ValueError('Frozen first-order keys disagree')
    # Freeze membership to the same baseline used by the existing study tables.
    omitted = decision_source.loc[~decision_source.rx_id.isin(matched.rx_id)].copy()
    details, _ = decisions.summarize(decision_source.loc[decision_source.rx_id.isin(matched.rx_id)].copy())
    check = details.merge(matched[['rx_id', 'customer_id', 'first_order_id', 'first_order_line_id',
                                   'approval_channel', 'order_cancel_reason']], on='rx_id', suffixes=('', '_baseline'),
                          how='outer', validate='one_to_one', indicator=True)
    if not check['_merge'].eq('both').all():
        raise ValueError('Decision source does not cover the frozen study')
    for col in ['customer_id', 'first_order_id', 'first_order_line_id', 'approval_channel']:
        if not check[col].eq(check[col + '_baseline']).all():
            raise ValueError(f'Frozen {col} differs from the decision source')
    changed = ~reason_key(check.cancel_reason).eq(reason_key(check.order_cancel_reason))
    if (changed & reason_key(check.order_cancel_reason).ne(base.MISSING_REASON)).any():
        raise ValueError('A populated frozen cancellation reason changed')
    reason_differences = check.loc[changed & check.approval_channel.eq('CUSTOMER_UPLOAD'),
        ['rx_id', 'customer_id', 'first_order_id', 'first_order_line_id',
         'order_cancel_reason', 'cancel_reason', 'cancel_time']].copy()
    study = details.loc[details.approval_channel.eq('CUSTOMER_UPLOAD'),
                        MATCH + ['cancel_reason', 'cancel_time']].copy()
    study['reason_key'] = reason_key(study.cancel_reason)
    if study[MATCH].isna().any().any() or study.duplicated(KEYS).any():
        raise ValueError('Missing or non-unique frozen first-order-line identity')
    associations, _, entity_audit = entity.validate(upload_source, PARAMS)
    uploads = associations.loc[associations.approval_channel.eq('CUSTOMER_UPLOAD')
        & associations.matched_order_id.notna() & associations.matched_order_line_id.notna(),
        ['matched_rx_id', 'rx_customer_id', 'matched_order_id', 'matched_order_line_id', 'upload_id',
         'state_name', 'created_ts_utc', 'state_changed_ts_utc', 'order_cancel_reason', 'order_cancel_time']].rename(
        columns=dict(zip(['matched_rx_id', 'rx_customer_id', 'matched_order_id', 'matched_order_line_id'], MATCH)))
    for frame in [study, uploads]:
        frame['rx_id'] = frame.rx_id.astype('string').str.strip()
        for col in MATCH[1:]:
            frame[col] = frame[col].map(base.identifier)
    linked = uploads.merge(study[MATCH + ['reason_key', 'cancel_time']], on=MATCH, how='left',
                           validate='many_to_one', indicator=True)
    if not linked['_merge'].eq('both').all():
        raise ValueError('Upload association is outside the frozen first-order study')
    if (not reason_key(linked.order_cancel_reason).eq(linked.reason_key).all()
            or not (linked.order_cancel_time.eq(linked.cancel_time)
                    | (linked.order_cancel_time.isna() & linked.cancel_time.isna())).all()):
        raise ValueError('Upload and frozen cancellation evidence disagree')
    uploads = uploads.drop_duplicates(MATCH + ['upload_id']).copy()
    study['cancellation_reason'] = study.reason_key
    outside = study.reason_key.eq('aged order') & (study.cancel_time.isna() | study.cancel_time.gt(CUTOFF))
    study.loc[outside, 'cancellation_reason'] = '[Aged order outside cutoff]'
    statuses = matched[['rx_id', 'customer_id', 'first_order_id', 'first_order_line_id',
                        'order_line_status']].rename(columns={
                            'first_order_id': 'order_id', 'first_order_line_id': 'order_line_id',
                            'order_line_status': 'line_item_status'})
    statuses['rx_id'] = statuses.rx_id.astype('string').str.strip()
    for col in MATCH[1:]:
        statuses[col] = statuses[col].map(base.identifier)
    statuses['line_item_status'] = (statuses.line_item_status.astype('string').str.strip()
                                   .str.upper().replace('', pd.NA).fillna('[Missing]'))
    study_with_status = study.merge(statuses, on=MATCH, how='left', validate='one_to_one', indicator=True)
    if not study_with_status['_merge'].eq('both').all():
        raise ValueError('Frozen line status does not cover every study identity')
    study_with_status = study_with_status.drop(columns='_merge')
    joined = study_with_status.merge(uploads, on=MATCH, how='left', validate='one_to_many')

    def counts(group, label, status, row_type):
        with_upload = group.upload_id.notna()
        n = len(group[KEYS].drop_duplicates())
        covered = len(group.loc[with_upload, KEYS].drop_duplicates())
        return dict(row_type=row_type, cancellation_reason=label, line_item_status=status,
            orders=group.order_id.nunique(), prescriptions=group.rx_id.nunique(),
            line_items=n, lines_with_upload=covered, uploads=group.upload_id.nunique(),
            accepted_uploads=group.loc[group.state_name.eq('ACCEPTED'), 'upload_id'].nunique(),
            rejected_uploads=group.loc[group.state_name.eq('REJECTED'), 'upload_id'].nunique(),
            upload_coverage_pct=100 * covered / n if n else float('nan'))

    rows = [counts(group, label, status, 'reason')
            for (label, status), group in joined.groupby(['cancellation_reason', 'line_item_status'])]
    rows.append(counts(joined, 'TOTAL', 'All', 'total'))
    summary = pd.DataFrame(rows).sort_values(['row_type', 'cancellation_reason', 'line_item_status']).reset_index(drop=True)
    with duckdb.connect() as connection:
        connection.execute("SET TimeZone='UTC'")
        connection.register('study', study_with_status)
        connection.register('uploads', uploads)
        independent = connection.execute(VERIFY_SQL).df()
    pd.testing.assert_frame_equal(summary, independent, check_dtype=False, atol=1e-10, rtol=0)
    total = summary.iloc[-1]
    if tuple(total[['orders', 'prescriptions', 'line_items', 'uploads', 'accepted_uploads', 'rejected_uploads']]) != (87724, 95073, 95073, 29715, 25606, 914):
        raise ValueError('Totals differ from the retained study snapshot')
    if not summary.upload_coverage_pct.between(0, 100).all():
        raise ValueError('Upload coverage outside 0--100%')
    if not summary.loc[summary.row_type.eq('reason'), ['prescriptions', 'line_items', 'lines_with_upload']].sum().eq(
            total[['prescriptions', 'line_items', 'lines_with_upload']]).all():
        raise ValueError('Reason/status line counts do not partition the study')
    audit = dict(excluded_newly_linked_decision_rows=len(omitted),
        frozen_membership_lines_with_newly_populated_reason=len(reason_differences),
        raw_upload_rows=len(upload_source), eligible_upload_associations=len(uploads),
        missing_upload_creation_dates=int(uploads.loc[uploads.created_ts_utc.isna(), 'upload_id'].nunique()),
        uploads_in_multiple_reason_groups=int(joined.dropna(subset=['upload_id']).groupby('upload_id').cancellation_reason.nunique().gt(1).sum()),
        orders_in_multiple_reason_groups=int(study.groupby('order_id').cancellation_reason.nunique().gt(1).sum()),
        entity_audit=entity_audit.to_dict('records'), independent_verification='All reason/status and TOTAL counts and coverage agree with DuckDB')
    return dict(study_lines=study, upload_associations=uploads, summary=summary,
                study_status_lines=study_with_status,
                excluded_decisions=omitted, reason_snapshot_differences=reason_differences), audit


def latex_rows(summary):
    rows = []
    for r in summary.itertuples():
        label = r.cancellation_reason if r.cancellation_reason.startswith('[') or r.row_type == 'total' else r.cancellation_reason.capitalize()
        label = label.replace('&', r'\&').replace('_', r'\_').replace('%', r'\%')
        if r.row_type == 'total':
            rows.append(r'\midrule')
        if r.cancellation_reason == 'aged order':
            rows.append(r'\rowcolor{yellow!35}')
        status = r.line_item_status.replace('_', r'\_')
        rows.append('{' + label + '}' + f' & {status} & {r.orders:,} & {r.prescriptions:,} & {r.line_items:,} & {r.lines_with_upload:,} & {r.upload_coverage_pct:.2f}'
                    + r'\%' + f' & {r.uploads:,} & {r.accepted_uploads:,} & {r.rejected_uploads:,}' + r' \\')
    return '\n'.join(rows)


def latex_table(summary):
    return r'''% Generated by make study-upload-coverage-by-cancel-reason.
\clearpage
\begin{landscape}
\subsubsection{What is the percentage of prescription upload?}\label{subsec:study-upload-coverage}
Table~\ref{tab:study-upload-coverage-by-cancellation-reason} reports upload coverage
for the study's first orders and first-order lines, by cancellation reason and line-item status.
\begin{table}[!htbp]
\centering
\caption{Prescription upload coverage by first-order cancellation reason and line-item status: CMPU vet-diet CUSTOMER\_UPLOAD prescriptions created August 15--October 14, 2026, inclusive, UTC.}
\label{tab:study-upload-coverage-by-cancellation-reason}
\small
\setlength{\tabcolsep}{6pt}
\begin{tabular}{@{}llrrrrrrrr@{}}
\toprule
Cancellation reason & \shortstack{Line-item\\status} & \shortstack{First\\orders} & Prescriptions & \shortstack{First-order\\line items} & \shortstack{Line items\\with upload} & \shortstack{Upload\\coverage (\%)} & \shortstack{Total\\uploads} & \shortstack{Accepted\\uploads} & \shortstack{Rejected\\uploads} \\
\midrule
''' + latex_rows(summary) + r'''
\bottomrule
\end{tabular}
\begin{minipage}{\linewidth}
\footnotesize
\textit{Notes:} Coverage = 100 $\times$ distinct first-order lines with at least
one matched upload $\div$ all study first-order lines in that reason/status group, including
lines without uploads. Prescriptions count distinct \texttt{RX\_ID}s and equal
line-item counts in this frozen one-prescription-per-first-order-line cohort.
Orders and physical order/line pairs count distinctly;
shipment rows cannot multiply counts. The frozen population is the same as
Table~\ref{tab:study-population-counts}, not the later financial comparison snapshot.
Uploads are distinct \texttt{UPLOAD\_ID}s from HCDM
\texttt{rxp\_upload\_entity}, restricted to \texttt{DIET\_PRESCRIPTION} entities.
Expand prescription IDs and match both prescription and numeric customer IDs,
then both first-order keys. Upload discovery is August 1--October 25 inclusive,
UTC; missing creation timestamps follow the existing study's unknown-window rule
and are audited. No requirement that upload precede cancellation is imposed.
Accepted and rejected refer to current entity \texttt{STATE\_NAME=ACCEPTED} and
\texttt{REJECTED}, not prescription approval or denial. Other entity states
remain in Total uploads, so Accepted plus Rejected need not equal Total.
Reasons are trimmed and case-insensitive. Aged order uses the inclusive
October 27, 2026, 00:00 UTC cancellation cutoff; later or undated aged reasons
remain in the outside-cutoff row. Missing/blank reasons do not prove an uncancelled
order. Line-item status is \texttt{ORDER\_ORDER\_LINE\_STATUS} from the frozen
October 28, 2026 first-order-line extract, with shipment-row consistency checked.
Codes are shown as recorded; missing status is explicit. Table~\ref{tab:study-no-cancellation-upload-details}
uses a later status/reason extraction, so its counts can differ.
An entity may match multiple prescriptions/lines and reason/status groups;
an order can also span groups. TOTAL independently deduplicates both and is not
the sum of overlapping rows. Cancellation reasons/times use the retained
prescription-decision extract and agree with the upload extract; originally blank
reasons populated since the earlier membership snapshot are audited separately.
Counts describe the retained source snapshots.
\end{minipage}
\end{table}
\end{landscape}
\input{../autogenerated/study_no_cancellation_upload_details}
\clearpage
'''


def main():
    sources = dict(baseline=BASELINE, decisions=DATA / 'cmpu-study-population-prescription-decisions',
                   uploads=DATA / 'cmpu-study-population-uploaded-documents')
    loaded = {name: load_source(directory) for name, directory in sources.items()}
    frames, audit = analyze(*(loaded[name][0] for name in ['baseline', 'decisions', 'uploads']))
    output = DATA / NAME / PERIOD
    output.mkdir(parents=True, exist_ok=True)
    for name, frame in frames.items():
        frame.to_parquet(output / f'{name.replace("_", "-")}.parquet', index=False)
    write_text(output / 'verification.sql', VERIFY_SQL + ';\n')
    write_text(output / 'audit.json', json.dumps(audit, indent=2) + '\n')
    write_text(output / 'analysis.json', json.dumps(dict(generated_at_utc=datetime.now(timezone.utc).isoformat(),
        version=2, generator_sha256=base.digest(Path(__file__)), parameters=PARAMS,
        coverage_definition='100 * distinct first-order lines with an upload / all study first-order lines in the reason/status group',
        sources={name: dict(path=str(sources[name].relative_to(ROOT)), **loaded[name][1]) for name in loaded},
        exports={p.name: base.digest(p) for p in output.glob('*.parquet')}), indent=2) + '\n')
    write_text(ROOT / 'outputs/tables' / PERIOD / f'{NAME}.md',
        '# Prescription upload coverage by cancellation reason and line-item status\n\n'
        'Frozen CUSTOMER_UPLOAD first-order study; percentage is line-item coverage, not uploads divided by lines. '
        'Upload discovery [2026-08-01,2026-10-26) UTC; aged cutoff 2026-10-27 00:00 UTC. '
        'Line-item status is ORDER_ORDER_LINE_STATUS from the frozen October 28 first-order-line snapshot. '
        'Prescriptions count distinct RX_IDs, equal to line counts in this frozen cohort. '
        'TOTAL deduplicates entities/orders across reason/status groups. Accepted/rejected are current entity states.\n\n'
        + markdown_table(frames['summary']) + '\n')
    write_text(ROOT / 'src/latex/appendix/study_upload_coverage_by_cancel_reason.tex', latex_table(frames['summary']))
    print(frames['summary'].to_string(index=False))


if __name__ == '__main__':
    main()

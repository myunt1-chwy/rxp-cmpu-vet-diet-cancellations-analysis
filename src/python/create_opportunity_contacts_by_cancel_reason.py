"""Distinct contacting customers by cancellation reason through observed endpoints."""

from datetime import date, datetime, timedelta, timezone
import hashlib
import json

import click
import duckdb
from jinja2 import Environment, StrictUndefined
import pandas as pd

from src.python import create_opportunity_order_cancellation_summary as base
from src.python.markdown_tables import markdown_table, write_text

ROOT = base.ROOT
KEYS = ['order_id', 'reason_key']
ORDER_COLUMNS = KEYS + ['customer_id', 'placed_at_utc', 'shipped_at_utc', 'cancelled_at_utc',
    'observed_end_utc', 'qualifying_lines', 'registry_variants', 'customer_variants', 'placement_variants']


def render_sql(start, end):
    return Environment(undefined=StrictUndefined).from_string(
        (ROOT / 'src/sql/opportunity_customer_contacts_by_cancel_reason.sql').read_text()
    ).render(**base.parameters(start, end))


def aggregate_sql(source_sql, handled_only=False):
    return '''WITH source AS (
''' + source_sql.rstrip() + '''
), eligible AS (
 SELECT *,CASE WHEN contact_order_id=order_id AND contact_customer_id=customer_id
 AND contact_at_utc IS NOT NULL AND LOWER(TRIM(session_initial_direction))='inbound'
 AND contact_at_utc::TIMESTAMP_NTZ<=observed_end_utc::TIMESTAMP_NTZ
''' + (' AND handled_flag=TRUE\n' if handled_only else '') + ''' THEN TRUE ELSE FALSE END AS contacted
 FROM source WHERE customer_id IS NOT NULL AND placed_at_utc IS NOT NULL
 AND observed_end_utc IS NOT NULL AND observed_end_utc::TIMESTAMP_NTZ>=placed_at_utc::TIMESTAMP_NTZ
 AND registry_variants=1 AND customer_variants=1 AND placement_variants=1
), totals AS (
 SELECT CASE WHEN GROUPING(reason_key)=1 THEN 'total' ELSE 'reason' END AS row_type,
 CASE WHEN GROUPING(reason_key)=1 THEN 'TOTAL' ELSE reason_key END AS reason_key,
 COUNT(DISTINCT customer_id) AS cohort_customers,
 COUNT(DISTINCT CASE WHEN contacted THEN customer_id END) AS contacting_customers,
 COUNT(DISTINCT order_id) AS cohort_orders,
 COUNT(DISTINCT CASE WHEN contacted THEN order_id END) AS contacting_orders
 FROM eligible GROUP BY GROUPING SETS ((reason_key),())
)
SELECT *,100.0*contacting_customers/NULLIF(cohort_customers,0) AS contacted_percentage
FROM totals ORDER BY row_type,reason_key'''


def analyze(raw, handled_only=False):
    f = raw.rename(columns=str.lower).copy()
    for col in ['order_id', 'customer_id', 'contact_order_id', 'contact_customer_id']:
        f[col] = f[col].map(base.identifier)
    for col in ['placed_at_utc', 'shipped_at_utc', 'cancelled_at_utc', 'observed_end_utc', 'contact_at_utc']:
        f[col] = pd.to_datetime(f[col], utc=True, format='mixed').astype('datetime64[ns, UTC]')
    if f[KEYS].isna().any().any():
        raise ValueError('Missing order/reason key')
    if f[['registry_variants', 'customer_variants', 'placement_variants']].ne(1).any().any():
        raise ValueError('Conflicting registry/customer/placement evidence')
    if f.groupby(KEYS)[ORDER_COLUMNS[2:]].nunique(dropna=False).gt(1).any().any():
        raise ValueError('Conflicting repeated order/reason evidence')
    if f.groupby('order_id')[['customer_id', 'placed_at_utc']].nunique(dropna=False).gt(1).any().any():
        raise ValueError('Conflicting customer/placement across order reasons')
    orders = f[ORDER_COLUMNS].drop_duplicates(KEYS).copy()
    orders['eligible'] = (orders[['customer_id', 'placed_at_utc', 'observed_end_utc']].notna().all(axis=1)
                          & orders.observed_end_utc.ge(orders.placed_at_utc))
    cohort = orders.loc[orders.eligible].copy()
    contacts = f.merge(cohort[KEYS], on=KEYS, validate='many_to_one')
    contacts['direction'] = contacts.session_initial_direction.astype('string').str.strip().str.lower()
    known = contacts.loc[contacts.contact_order_id.notna() & contacts.session_id.notna() & contacts.leg_id.notna()]
    fields = ['contact_customer_id', 'contact_at_utc', 'direction', 'handled_flag', 'session_channel', 'session_ingress_point']
    if known.groupby(KEYS + ['session_id', 'leg_id'])[fields].nunique(dropna=False).gt(1).any().any():
        raise ValueError('Conflicting contact-leg evidence')
    duplicates = int(contacts.duplicated().sum())
    contacts = contacts.drop_duplicates().copy()
    matched = contacts.contact_order_id.notna()
    if not contacts.loc[matched].contact_order_id.eq(contacts.loc[matched].order_id).all():
        raise ValueError('Contact order differs')
    dated = contacts.contact_at_utc.notna()
    if contacts.loc[dated].contact_at_utc.gt(contacts.loc[dated].observed_end_utc).any():
        raise ValueError('Contact after observed order endpoint')
    identity = contacts.contact_customer_id.notna() & contacts.contact_customer_id.eq(contacts.customer_id)
    contacts['included'] = (matched & dated & identity & contacts.direction.eq('inbound')).fillna(False)
    if handled_only:
        contacts['included'] &= contacts.handled_flag.eq(True).fillna(False)
    selected = contacts.loc[contacts.included]
    rows = []

    def counts(group, contacted, reason, row_type):
        customers = group.customer_id.nunique()
        n = contacted.customer_id.nunique()
        return dict(row_type=row_type, reason_key=reason, cohort_customers=customers,
                    contacting_customers=n, cohort_orders=group.order_id.nunique(),
                    contacting_orders=contacted.order_id.nunique(),
                    contacted_percentage=100*n/customers if customers else float('nan'))

    for reason, group in cohort.groupby('reason_key', sort=True):
        rows.append(counts(group, selected.loc[selected.reason_key.eq(reason)], reason, 'reason'))
    rows.append(counts(cohort, selected, 'TOTAL', 'total'))
    summary = pd.DataFrame(rows).sort_values(['row_type', 'reason_key']).reset_index(drop=True)
    verify = aggregate_sql('SELECT * FROM normalized_source', handled_only).replace('TIMESTAMP_NTZ', 'TIMESTAMPTZ')
    with duckdb.connect() as connection:
        connection.execute("SET TimeZone='UTC'")
        connection.register('normalized_source', f)
        expected = connection.execute(verify).df()
    pd.testing.assert_frame_equal(summary, expected, check_dtype=False, atol=1e-10)
    if summary.contacting_customers.gt(summary.cohort_customers).any():
        raise ValueError('Contacted customers exceed cohort')
    audit = dict(candidate_order_reason_pairs=len(orders), excluded_order_reason_pairs=int((~orders.eligible).sum()),
        cohort_customers=cohort.customer_id.nunique(), cohort_orders=cohort.order_id.nunique(),
        contacting_customers=selected.customer_id.nunique(), contacting_orders=selected.order_id.nunique(),
        identical_contact_duplicates_collapsed=duplicates, included_contact_rows=len(selected),
        missing_contact_time_rows=int((matched & ~dated).sum()),
        missing_or_mismatched_customer_rows=int((matched & ~identity).sum()),
        outbound_rows=int((matched & contacts.direction.eq('outbound')).sum()),
        unknown_direction_rows=int((matched & ~contacts.direction.isin(['inbound', 'outbound'])).sum()),
        customers_in_multiple_reasons=int(cohort.groupby('customer_id').reason_key.nunique().gt(1).sum()),
        orders_in_multiple_reasons=int(cohort.groupby('order_id').reason_key.nunique().gt(1).sum()),
        sql_null_pairs_with_cancellation_but_no_shipment=int((cohort.reason_key.eq('[SQL NULL]')
            & cohort.shipped_at_utc.isna() & cohort.cancelled_at_utc.notna()).sum()),
        handled_only=handled_only, contact_window='No creation-relative bounds; through observed endpoint',
        independent_verification='DuckDB independently recomputes every reason and global distinct count and percentage')
    return dict(candidate_order_reasons=orders, cohort_order_reasons=cohort,
                contact_details=contacts, summary=summary), audit, verify


def reason_label(value):
    return value if value.startswith('[') or value == 'TOTAL' else value.capitalize()


def latex_table(summary, audit, start, end):
    def escape(value):
        return ''.join({'\\': r'\textbackslash{}', '&': r'\&', '%': r'\%', '_': r'\_',
                        '#': r'\#', '{': r'\{', '}': r'\}'}.get(c, c) for c in str(value))
    rows = []
    for row in summary.itertuples():
        if row.row_type == 'total':
            rows.append(r'\midrule')
        if row.reason_key == 'aged order':
            rows.append(r'\rowcolor{yellow!35}')
        percentage = 'N/A' if pd.isna(row.contacted_percentage) else f'{row.contacted_percentage:.2f}'+r'\%'
        rows.append('{' + escape(reason_label(row.reason_key)) + '} & '
                    + f'{row.cohort_customers:,} & {row.contacting_customers:,} & {percentage}' + r' \\')
    first = date.fromisoformat(start).strftime('%B %-d, %Y')
    last = (date.fromisoformat(end)-timedelta(days=1)).strftime('%B %-d, %Y')
    return r'''\subsubsection{What is the distribution of CMPU customers with APPROVAL CHANNEL = CUSTOMER\_UPLOAD that contacted Chewy by cancellation reason?}
Table~\ref{tab:customer-contacts-by-cancellation-reason} compares customers with
inbound contacts across CMPU vet-diet \texttt{CUSTOMER\_UPLOAD} orders with
qualifying shipment or cancellation activity from ''' + first + ' through ' + last + r''', inclusive, UTC.

\begin{table}[!htbp]
\centering
\caption{Distinct customers contacting by current order cancellation reason, through the latest observed shipment or cancellation event.}
\label{tab:customer-contacts-by-cancellation-reason}
\small
\begin{tabular}{@{}lrrr@{}}
\toprule
Cancellation reason & Cohort customers & Customers contacting & Contacted (\%) \\
\midrule
''' + '\n'.join(rows) + r'''
\bottomrule
\end{tabular}

\begin{minipage}{\linewidth}
\footnotesize
\textit{Notes:} No lower or upper day limit relative to order creation applies.
Include contacts at any available earlier timestamp, capped inclusively at the
latest observed shipment/cancellation timestamp among
qualifying rows for that order and reason. For split or mixed outcomes, use the
later of the observed events. Match inbound contacts on the original order ID
and numeric customer ID, across all categories. ''' + (
    r'Require \texttt{HANDLED\_FLAG=TRUE}.' if audit['handled_only'] else
    'Include handled, unhandled and unknown-handled inbound attempts.') + r'''
Count each customer once per reason across all their qualifying orders and
contact days. Percentages divide contacting customers by all eligible customers
in that reason, including those without a qualifying contact. Customers can
appear in multiple reason rows; TOTAL independently counts each customer once
overall and is not the sum of the reason rows. Reasons reflect the current
snapshot, grouped case-insensitively after trimming. SQL NULL is explicit;
blank strings, if present, form a separate row. NULL does not imply no cancellation.
This cohort includes ''' + f"{audit['sql_null_pairs_with_cancellation_but_no_shipment']:,}" + r'''
NULL-reason order/reason records with observed cancellation but no qualifying
shipment. This summary has no creation-relative day bounds.
Observation ends at each order's observed
event, so exposure varies; these are descriptive contact shares, not causal effects.
Exact duplicate contacts collapse; missing or mismatching contact customers,
missing contact times and non-inbound directions are excluded and audited.
Inbound direction is a source proxy, not proof of human initiation.
No prescription-creation or first-order restriction applies.
Extraction time (UTC): ''' + audit['extracted_at_utc'] + r'''.
Executable SQL and complete order/contact records are under
\path{data/opportunity/customer-contacts-by-cancel-reason/}.
\end{minipage}
\end{table}
'''


def publish_latex(text):
    write_text(ROOT / 'src/latex/appendix/customer_contacts_by_cancellation_reason.tex', text)
    main = ROOT / 'src/latex/main.tex'
    include = r'\input{appendix/customer_contacts_by_cancellation_reason}'
    parent = ROOT / 'src/latex/appendix/contact_analysis.tex'
    body = parent.read_text()
    if include not in body:
        anchor = r'\label{subsec:contact-analysis}'
        if anchor not in body:
            raise ValueError('Cannot locate parent contact section')
        write_text(parent, body.replace(anchor, anchor + '\n' + include + '\n' + r'\clearpage', 1))
    body = main.read_text()
    if include in body:
        write_text(main, body.replace(include + '\n', ''))


@click.command()
@click.option('--start-date', default='2026-05-01', show_default=True)
@click.option('--end-date', default='2026-08-01', show_default=True)
@click.option('--handled-only', is_flag=True)
@click.option('--write-latex', is_flag=True)
@click.option('--cached', is_flag=True)
@click.option('--print-sql', is_flag=True)
def main(start_date, end_date, handled_only, write_latex, cached, print_sql):
    sql = render_sql(start_date, end_date)
    report_sql = aggregate_sql(sql, handled_only)
    if print_sql:
        click.echo(report_sql)
        return
    directory = ROOT / 'data/opportunity/customer-contacts-by-cancel-reason' / f'{start_date}_{end_date}' / 'event-capped'
    directory.mkdir(parents=True, exist_ok=True)
    source, manifest = directory / 'source.parquet', directory / 'source.json'
    identity = dict(version=2, start_date=start_date, end_date=end_date,
                    contact_window='event-capped', timezone='UTC', sql_sha256=hashlib.sha256(sql.encode()).hexdigest())
    if cached:
        metadata = json.loads(manifest.read_text())
        if metadata['identity'] != identity or metadata['source_sha256'] != base.digest(source):
            raise click.ClickException('Cache fingerprint differs; run a fresh extraction')
    else:
        write_text(directory / 'query.sql', sql)
        engine = base.extract(directory / 'query.sql', source, directory)
        metadata = dict(identity=identity, source_sha256=base.digest(source),
                        extracted_at_utc=datetime.now(timezone.utc).isoformat(), **engine)
        write_text(manifest, json.dumps(metadata, indent=2) + '\n')
    frames, audit, verify = analyze(pd.read_parquet(source), handled_only)
    audit['extracted_at_utc'] = metadata['extracted_at_utc']
    mode = directory / ('handled-inbound' if handled_only else 'all-inbound')
    mode.mkdir(parents=True, exist_ok=True)
    receipt = mode / 'warehouse-reconciliation.json'
    if receipt.exists():
        record = json.loads(receipt.read_text())
        if (record['source_sha256'] == metadata['source_sha256']
                and record['summary_sql_sha256'] == hashlib.sha256((report_sql + '\n').encode()).hexdigest()):
            warehouse_file = mode / 'warehouse-summary.parquet'
            if base.digest(warehouse_file) != record['warehouse_result_sha256']:
                raise ValueError('Warehouse validation result fingerprint differs')
            warehouse = pd.read_parquet(warehouse_file).rename(columns=str.lower)
            pd.testing.assert_frame_equal(frames['summary'].drop(columns='contacted_percentage'),
                warehouse.drop(columns='contacted_percentage'), check_dtype=False, check_exact=True)
            if not frames['summary'].contacted_percentage.sub(
                    warehouse.contacted_percentage.astype(float)).abs().le(0.000001).all():
                raise ValueError('Warehouse contact percentages differ')
            audit['warehouse_verification'] = record
    for name, frame in frames.items():
        base.write_parquet(frame, mode / f'{name}.parquet')
    write_text(mode / 'summary.sql', report_sql + '\n')
    write_text(mode / 'verification.sql', verify + ';\n')
    write_text(mode / 'audit.json', json.dumps(dict(audit, source_sha256=metadata['source_sha256']), indent=2) + '\n')
    display = frames['summary'][['reason_key', 'cohort_customers', 'contacting_customers', 'contacted_percentage']].copy()
    display.reason_key = display.reason_key.map(reason_label)
    display.contacted_percentage = display.contacted_percentage.map(lambda v: 'N/A' if pd.isna(v) else f'{v:.2f}%')
    display.columns = ['Cancellation reason', 'Cohort customers', 'Customers contacting', 'Contacted (%)']
    tables = ROOT / 'outputs/tables/opportunity' / f'{start_date}_{date.fromisoformat(end_date)-timedelta(days=1)}'
    tables.mkdir(parents=True, exist_ok=True)
    suffix = '-handled-only' if handled_only else ''
    note = (f'Shipment/cancellation activity [{start_date}, {end_date}) UTC; CMPU vet diet CUSTOMER_UPLOAD. '
            'Inbound contacts must match order/customer IDs. No creation-relative day bounds; '
            'capped at the latest observed shipment/cancellation event. '
            'Unique customers per reason; TOTAL is independently deduplicated. Reasons and customer memberships overlap. '
            f"Extracted UTC: {metadata['extracted_at_utc']}.\n\n")
    write_text(tables / f'customer-contacts-by-cancellation-reason{suffix}.md',
               '# Contacting customers by order cancellation reason\n\n' + note + markdown_table(display) + '\n')
    latex = latex_table(frames['summary'], audit, start_date, end_date)
    write_text(mode / 'contact-table.tex', latex)
    if write_latex:
        publish_latex(latex)
    click.echo(display.to_string(index=False))
    click.echo(json.dumps(audit, indent=2))


if __name__ == '__main__':
    main()

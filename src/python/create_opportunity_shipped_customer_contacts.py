"""Creation-relative inbound contacts through shipment for NULL-reason RxP orders."""

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
MIN_DAY, MAX_DAY = -2, 11
DAY_NS = 86_400_000_000_000
ORDER_COLUMNS = ['order_id', 'customer_id', 'placed_at_utc', 'shipped_at_utc',
                 'first_shipped_at_utc', 'registry_variants', 'qualifying_lines',
                 'shipment_source_rows', 'customer_variants', 'placement_variants',
                 'nonnull_reason_rows', 'cancellation_evidence_rows', 'missing_shipment_time_rows']
VERIFY_SQL = '''WITH days AS (SELECT range AS relative_day FROM range(-2,12)), counts AS (
 SELECT FLOOR((epoch_ns(contact_time)-epoch_ns(placed_time))/86400000000000.0)::INTEGER AS relative_day,
 COUNT(DISTINCT customer_id) AS distinct_customers,
 COUNT(DISTINCT order_id) AS distinct_shipped_orders
 FROM contacts WHERE direction='inbound' AND contact_customer_id=customer_id
 AND contact_time IS NOT NULL AND contact_time<=shipped_time {handled_filter}
 GROUP BY 1)
 SELECT d.relative_day,COALESCE(c.distinct_customers,0) AS distinct_customers,
 COALESCE(c.distinct_shipped_orders,0) AS distinct_shipped_orders
 FROM days d LEFT JOIN counts c USING(relative_day) ORDER BY d.relative_day'''


def render_sql(start, end):
    params = base.parameters(start, end)
    return Environment(undefined=StrictUndefined).from_string(
        (ROOT / 'src/sql/opportunity_shipped_customer_contacts.sql').read_text()
    ).render(**params, min_day=MIN_DAY, end_day=MAX_DAY + 1)


def summary_sql(sql, handled_only=False):
    return '''WITH source AS (
''' + sql.rstrip() + '''
), days AS (SELECT ROW_NUMBER() OVER (ORDER BY SEQ4())-3 AS relative_day
 FROM TABLE(GENERATOR(ROWCOUNT=>14))), counts AS (
 SELECT FLOOR(DATEDIFF(nanosecond,placed_at_utc::TIMESTAMP_NTZ,
 contact_at_utc::TIMESTAMP_NTZ)::DOUBLE/86400000000000.0)::INTEGER AS relative_day,
 COUNT(DISTINCT customer_id) AS distinct_customers,
 COUNT(DISTINCT order_id) AS distinct_shipped_orders
 FROM source WHERE nonnull_reason_rows=0 AND registry_variants=1
 AND customer_variants=1 AND placement_variants=1
 AND customer_id IS NOT NULL AND placed_at_utc IS NOT NULL
 AND shipped_at_utc::TIMESTAMP_NTZ>=placed_at_utc::TIMESTAMP_NTZ
 AND contact_order_id IS NOT NULL AND contact_customer_id=customer_id
 AND LOWER(TRIM(session_initial_direction))='inbound' AND contact_at_utc IS NOT NULL
 AND contact_at_utc::TIMESTAMP_NTZ<=shipped_at_utc::TIMESTAMP_NTZ
''' + (' AND handled_flag=TRUE\n' if handled_only else '') + ''' GROUP BY 1)
 SELECT d.relative_day,COALESCE(c.distinct_customers,0) AS distinct_customers,
 COALESCE(c.distinct_shipped_orders,0) AS distinct_shipped_orders
 FROM days d LEFT JOIN counts c ON d.relative_day=c.relative_day ORDER BY d.relative_day'''


def analyze(raw, handled_only=False):
    f = raw.rename(columns=str.lower).copy()
    for col in ['order_id', 'customer_id', 'contact_order_id', 'contact_customer_id']:
        f[col] = f[col].map(base.identifier)
    for col in ['placed_at_utc', 'shipped_at_utc', 'first_shipped_at_utc', 'contact_at_utc']:
        f[col] = pd.to_datetime(f[col], utc=True, format='mixed').astype('datetime64[ns, UTC]')
    if f.order_id.isna().any():
        raise ValueError('Missing order ID')
    if f[['registry_variants', 'customer_variants', 'placement_variants']].ne(1).any().any():
        raise ValueError('Conflicting registry/customer/placement evidence')
    if f.groupby('order_id')[ORDER_COLUMNS[1:]].nunique(dropna=False).gt(1).any().any():
        raise ValueError('Conflicting repeated order evidence')
    candidates = f[ORDER_COLUMNS].drop_duplicates('order_id').copy()
    candidates['eligibility'] = 'Included'
    candidates.loc[candidates.nonnull_reason_rows.gt(0), 'eligibility'] = 'Non-NULL reason on qualifying lines'
    candidates.loc[candidates.shipped_at_utc.lt(candidates.placed_at_utc), 'eligibility'] = 'Shipment before placement'
    missing = candidates[['customer_id', 'placed_at_utc', 'shipped_at_utc']].isna().any(axis=1)
    candidates.loc[missing, 'eligibility'] = 'Missing customer/placement/shipment'
    orders = candidates.loc[candidates.eligibility.eq('Included')].copy()
    contacts = f.loc[f.order_id.isin(orders.order_id) & f.contact_order_id.notna()].copy()
    if not contacts.contact_order_id.eq(contacts.order_id).all():
        raise ValueError('Contact order ID differs')
    contacts['direction'] = contacts.session_initial_direction.astype('string').str.strip().str.lower()
    known = contacts.loc[contacts.leg_id.notna() & contacts.session_id.notna()]
    fields = ['contact_customer_id', 'contact_at_utc', 'direction', 'handled_flag',
              'session_channel', 'session_ingress_point']
    if known.groupby(['contact_order_id', 'session_id', 'leg_id'])[fields].nunique(dropna=False).gt(1).any().any():
        raise ValueError('Conflicting contact-leg evidence')
    duplicates = int(contacts.duplicated().sum())
    contacts = contacts.drop_duplicates().copy()
    delta = (contacts.contact_at_utc - contacts.placed_at_utc).astype('int64').astype('Int64')
    delta.loc[contacts.contact_at_utc.isna()] = pd.NA
    contacts['relative_day'] = delta // DAY_NS
    dated = contacts.contact_at_utc.notna()
    if (not contacts.loc[dated, 'relative_day'].between(MIN_DAY, MAX_DAY).all()
            or contacts.loc[dated, 'contact_at_utc'].gt(contacts.loc[dated, 'shipped_at_utc']).any()):
        raise ValueError('Contact outside creation-relative / shipment observation window')
    identity = contacts.contact_customer_id.notna() & contacts.contact_customer_id.eq(contacts.customer_id)
    contacts['included'] = (dated & identity & contacts.direction.eq('inbound')).fillna(False)
    if handled_only:
        contacts['included'] &= contacts.handled_flag.eq(True).fillna(False)
    selected = contacts.loc[contacts.included]
    counts = selected.groupby('relative_day').agg(distinct_customers=('customer_id', 'nunique'),
                                                 distinct_shipped_orders=('order_id', 'nunique'))
    daily = pd.DataFrame({'relative_day': range(MIN_DAY, MAX_DAY + 1)}).merge(
        counts, on='relative_day', how='left').fillna(0).astype('int64')
    verification = VERIFY_SQL.format(handled_filter='AND handled_flag=TRUE' if handled_only else '')
    independent = contacts.copy()
    for source, destination in [('contact_at_utc', 'contact_time'), ('placed_at_utc', 'placed_time'),
                                ('shipped_at_utc', 'shipped_time')]:
        independent[destination] = independent[source].dt.tz_localize(None)
    with duckdb.connect() as connection:
        connection.register('contacts', independent)
        expected = connection.execute(verification).df()
    pd.testing.assert_frame_equal(daily, expected, check_dtype=False)
    exposure = pd.DataFrame([dict(relative_day=day,
        orders_under_observation=int(orders.shipped_at_utc.ge(orders.placed_at_utc + pd.Timedelta(days=day)).sum()),
        customers_under_observation=orders.loc[orders.shipped_at_utc.ge(
            orders.placed_at_utc + pd.Timedelta(days=day)), 'customer_id'].nunique())
        for day in range(MIN_DAY, MAX_DAY + 1)])
    if (daily.distinct_shipped_orders.gt(exposure.orders_under_observation).any()
            or daily.distinct_customers.gt(exposure.customers_under_observation).any()):
        raise ValueError('Daily contacts exceed the observed population')
    audit = dict(candidate_orders=len(candidates), shipped_orders=len(orders),
        shipped_customers=orders.customer_id.nunique(), distinct_customers_contacting=selected.customer_id.nunique(),
        distinct_orders_contacting=selected.order_id.nunique(), included_contact_rows=len(selected),
        identical_contact_duplicates_collapsed=duplicates, missing_contact_time_rows=int((~dated).sum()),
        missing_or_mismatched_customer_rows=int((~identity).sum()),
        inbound_rows=int(contacts.direction.eq('inbound').sum()),
        outbound_rows=int(contacts.direction.eq('outbound').sum()),
        unknown_direction_rows=int((~contacts.direction.isin(['inbound', 'outbound'])).sum()),
        orders_with_cancellation_evidence=int(orders.cancellation_evidence_rows.gt(0).sum()),
        orders_with_missing_qualifying_shipment_times=int(orders.missing_shipment_time_rows.gt(0).sum()),
        excluded_orders=candidates.loc[candidates.eligibility.ne('Included')].eligibility.value_counts().to_dict(),
        min_day=MIN_DAY, max_day=MAX_DAY, handled_only=handled_only,
        independent_verification='DuckDB recomputes all daily distinct customer/order counts from retained contacts')
    return dict(candidate_orders=candidates, shipped_orders=orders, contact_details=contacts,
                daily_summary=daily, day_exposure=exposure), audit, verification


def latex_table(daily, audit, start, end, handled_only):
    first = date.fromisoformat(start).strftime('%B %-d, %Y')
    last = (date.fromisoformat(end) - timedelta(days=1)).strftime('%B %-d, %Y')
    rows = [f'{r.relative_day} & {r.distinct_customers:,} & {r.distinct_shipped_orders:,}' + r' \\'
            for r in daily.itertuples()]
    return r'''\clearpage
\subsection{What is the contact pattern of CMPU order customers?}
\label{subsec:shipped-customer-contact-analysis}
\subsubsection{When did customers contact us between order creation and shipment?}
Table~\ref{tab:shipped-customer-contacts-by-creation-day} follows CMPU vet-diet
\texttt{CUSTOMER\_UPLOAD} orders with SQL NULL cancellation reason and at least
one qualifying shipment from ''' + first + ' through ' + last + r''', inclusive, UTC.
The cohort contains ''' + f"{audit['shipped_customers']:,} customers and {audit['shipped_orders']:,} orders." + r'''

\begin{table}[!htbp]
\centering
\caption{Inbound contacts for shipped orders with NULL cancellation reason, relative to order creation: distinct customers contacting and distinct order IDs, from day $-2$ through $+11$, stopping at shipment. A total of ''' + f"{audit['distinct_customers_contacting']:,}" + r''' distinct customers contacted in this window.}
\label{tab:shipped-customer-contacts-by-creation-day}
\begin{tabular}{@{}rrr@{}}
\toprule
Days relative to creation & Customers contacting & Shipped order IDs \\
\midrule
''' + '\n'.join(rows) + r'''
\bottomrule
\end{tabular}

\begin{minipage}{\linewidth}
\footnotesize
\textit{Notes:} Same inbound direction and order/customer matching rules as
Table~\ref{tab:aged-customer-contacts-by-cancellation-day}, across all contact
categories. ''' + (r'Require \texttt{HANDLED\_FLAG=TRUE}.' if handled_only else
                  'Include handled, unhandled and unknown-handled inbound attempts.') + r'''
Day 0 begins at UTC \texttt{ORDER\_PLACED\_DTTM}, used as order creation;
day $n$ is the elapsed 24-hour bin $[n,n+1)$, so day $-2$ is creation minus
two days through creation minus one day. Count only contacts at or before
the latest \texttt{ORDER\_LINE\_SHIPPED\_DTTM} across qualifying RxP lines
on that order, including split-shipment rows outside the shipment cohort window.
Day $+11$ ends at creation plus 12 days, or shipment if earlier. This does not
restrict orders to shipping within 11 days. It does not establish that every
line on the order shipped. NULL means SQL NULL, excluding blank strings;
orders with any non-NULL reason on qualifying lines are excluded.
An observed shipment is required; a NULL reason alone is not shipment evidence.
''' + f"{audit['orders_with_cancellation_evidence']:,}" + r''' cohort orders also have cancellation evidence on
other qualifying line/shipment rows; their observed shipped rows still qualify.
Each customer and order counts once per relative day, regardless of repeated
legs, sessions, lines or shipments. Counts overlap across days. Missing or
mismatching contact customers, missing contact times, outbound and unknown
directions are excluded and audited. Later days cover fewer orders because
observation ends at shipment; these are counts, not contact rates. There is
no first-order or prescription-creation restriction. Current source snapshots
and the shipment-date cohort differ from the aged-cancellation comparison.
Customers may appear in both tables through different orders.
Extraction time (UTC): ''' + audit['extracted_at_utc'] + r'''.
SQL and full order/contact audits are retained under
\path{data/opportunity/shipped-customer-contacts/};
the source template is \path{src/sql/opportunity_shipped_customer_contacts.sql}.
\end{minipage}
\end{table}
'''


def publish_latex(text):
    write_text(ROOT / 'src/latex/appendix/shipped_customer_contacts.tex', text)
    main = ROOT / 'src/latex/main.tex'
    body = main.read_text()
    include = r'\input{appendix/shipped_customer_contacts}'
    if include not in body:
        anchor = r'\input{appendix/contact_analysis}'
        if anchor not in body:
            raise ValueError('Cannot locate contact analysis in report')
        write_text(main, body.replace(anchor, anchor + '\n' + include, 1))


@click.command()
@click.option('--start-date', default='2026-05-01', show_default=True)
@click.option('--end-date', default='2026-08-01', show_default=True, help='Exclusive UTC shipment end.')
@click.option('--handled-only', is_flag=True)
@click.option('--write-latex', is_flag=True)
@click.option('--cached', is_flag=True)
@click.option('--print-sql', is_flag=True)
def main(start_date, end_date, handled_only, write_latex, cached, print_sql):
    sql = render_sql(start_date, end_date)
    report_sql = summary_sql(sql, handled_only)
    if print_sql:
        click.echo(report_sql)
        return
    directory = ROOT / 'data/opportunity/shipped-customer-contacts' / f'{start_date}_{end_date}'
    directory.mkdir(parents=True, exist_ok=True)
    source, manifest = directory / 'source.parquet', directory / 'source.json'
    identity = dict(version=1, start_date=start_date, end_date=end_date, timezone='UTC',
                    min_day=MIN_DAY, max_day=MAX_DAY, sql_sha256=hashlib.sha256(sql.encode()).hexdigest())
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
    audit['orders_with_final_shipment_after_reporting_window'] = int(
        frames['shipped_orders'].shipped_at_utc.ge(pd.Timestamp(end_date, tz='UTC')).sum())
    mode = directory / ('handled-inbound' if handled_only else 'all-inbound')
    mode.mkdir(parents=True, exist_ok=True)
    warehouse_record = mode / 'warehouse-reconciliation.json'
    if warehouse_record.exists():
        record = json.loads(warehouse_record.read_text())
        if (record['source_sha256'] == metadata['source_sha256']
                and record['summary_sql_sha256'] == hashlib.sha256((report_sql + '\n').encode()).hexdigest()):
            warehouse_result = mode / 'warehouse-summary.parquet'
            if base.digest(warehouse_result) != record['warehouse_result_sha256']:
                raise ValueError('Warehouse validation result fingerprint differs')
            pd.testing.assert_frame_equal(frames['daily_summary'],
                pd.read_parquet(warehouse_result).rename(columns=str.lower), check_dtype=False)
            audit['warehouse_verification'] = record
    for name, frame in frames.items():
        base.write_parquet(frame, mode / f'{name}.parquet')
    write_text(mode / 'verification.sql', verify + ';\n')
    write_text(mode / 'summary.sql', report_sql + '\n')
    write_text(mode / 'audit.json', json.dumps(dict(audit, source_sha256=metadata['source_sha256']), indent=2) + '\n')
    display = frames['daily_summary'].rename(columns={'relative_day': 'Days relative to creation',
        'distinct_customers': 'Customers contacting', 'distinct_shipped_orders': 'Shipped order IDs'})
    tables = ROOT / 'outputs/tables/opportunity' / f'{start_date}_{date.fromisoformat(end_date)-timedelta(days=1)}'
    tables.mkdir(parents=True, exist_ok=True)
    suffix = '-handled-only' if handled_only else ''
    note = (f'Shipments [{start_date}, {end_date}) UTC; SQL NULL reason on qualifying lines; '
            'CMPU vet diet CUSTOMER_UPLOAD, joined by RX_ID and numeric customer ID. '
            'Order creation = ORDER_PLACED_DTTM. Days -2..+11 are elapsed 24-hour bins; '
            'contacts stop at the latest observed qualifying line shipment, inclusive. '
            'Require inbound direction and matching order/customer IDs. '
            'Each customer/order counts once per day; counts overlap across days. '
            'Later days have shorter exposure because observation ends at shipment. '
            f"Extracted UTC: {metadata['extracted_at_utc']}. "
            f"Cohort: {audit['shipped_customers']:,} customers / {audit['shipped_orders']:,} orders.\n\n")
    write_text(tables / f'shipped-customer-contacts-by-creation-day{suffix}.md',
               '# Shipped-customer contacts relative to order creation\n\n' + note + markdown_table(display) + '\n')
    latex = latex_table(frames['daily_summary'], audit, start_date, end_date, handled_only)
    write_text(mode / 'contact-table.tex', latex)
    if write_latex:
        publish_latex(latex)
    click.echo(display.to_string(index=False))
    click.echo(json.dumps(audit, indent=2))
    click.echo(f'Exports and SQL: {mode}')


if __name__ == '__main__':
    main()

"""REFNUM 58: actual sales baseline for CMPU vet-diet CUSTOMER_UPLOAD orders."""
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation, localcontext
import hashlib
import json
from pathlib import Path
import runpy
import subprocess
import sys

import click
from jinja2 import Environment, StrictUndefined
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from src.python.markdown_tables import markdown_table, write_text
from src.python import opportunity_report_tables as report_tables

ROOT = Path(__file__).resolve().parents[2]
NAME = 'opportunity-order-cancellation-summary'
TEMPLATE = ROOT/'src/sql/opportunity_order_cancellation_summary.sql'
VERSION = 2
KEYS = ['order_id', 'order_line_id']
SHIPMENT_KEYS = KEYS + ['shipment_key']
MISSING_REASON = '[No recorded cancellation reason]'
SCALE = Decimal('0.00001')
ZERO = Decimal('0.00000')
CRITERIA = dict(is_vet_diet_flag=True, approval_channel='CUSTOMER_UPLOAD',
                prescription_source='CMPU', orders='all', revenue='qualifying lines only', timezone='UTC')
MONEY_COLUMNS = ['order_line_net_sales', 'known_net_sales', 'actual_net_sales']


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parameters(start, end, date_basis="placed"):
    start, end = date.fromisoformat(start), date.fromisoformat(end)
    if start >= end:
        raise ValueError('start date must precede exclusive end date')
    if date_basis not in ['placed','shipped-or-cancelled']:
        raise ValueError('invalid date basis')
    result = dict(start_date=str(start), end_date=str(end))
    if date_basis != 'placed': result['date_basis'] = date_basis
    return result


def render_sql(start, end, date_basis="placed"):
    return Environment(undefined=StrictUndefined).from_string(TEMPLATE.read_text()).render(**dict(parameters(start, end, date_basis), date_basis=date_basis))


def identifier(value):
    if pd.isna(value):
        return None
    try:
        number = Decimal(str(value))
        if not number.is_finite() or number != number.to_integral_value() or number < 0:
            raise ValueError('invalid numeric identifier')
        return str(int(number))
    except InvalidOperation as error:
        raise ValueError('invalid numeric identifier') from error


def money(value):
    if pd.isna(value):
        return None
    if isinstance(value, float):
        raise ValueError('floating-point sales amounts are not supported; extract exact strings')
    try:
        amount = Decimal(str(value))
        with localcontext() as context:
            context.prec = 50
            scaled = amount.quantize(SCALE)
        if not amount.is_finite() or amount != scaled or abs(scaled) >= Decimal('1e33'):
            raise ValueError('invalid sales precision or range')
        return scaled
    except InvalidOperation as error:
        raise ValueError('invalid sales amount') from error


def decimal_sum(values):
    with localcontext() as context:
        context.prec = 50
        return sum((v for v in values if v is not None and not pd.isna(v)), ZERO)


def event_window(frame, start, end):
    lower, upper = pd.Timestamp(start, tz='UTC'), pd.Timestamp(end, tz='UTC')
    return (frame.shipped_at_utc.between(lower, upper, inclusive='left')
            | frame.cancelled_at_utc.between(lower, upper, inclusive='left'))


def summarize(raw, start, end, date_basis="placed"):
    params = parameters(start, end, date_basis)
    f = raw.rename(columns=str.lower).copy()
    for column in ['order_id', 'order_line_id', 'shipment_key', 'customer_id', 'rx_customer_id', 'site_key', 'order_line_site_key']:
        f[column] = f[column].map(identifier)
    if f[KEYS].isna().any().any():
        raise ValueError('missing physical order/line identifiers')
    f['order_placed_utc'] = pd.to_datetime(f.order_placed_utc, utc=True, format='mixed', errors='raise')
    if date_basis == 'shipped-or-cancelled':
        for col in ['shipped_at_utc','cancelled_at_utc']:
            f[col] = pd.to_datetime(f[col], utc=True, format='mixed', errors='raise')
        f['in_event_window'] = event_window(f, start, end)
    f['order_line_net_sales'] = f.order_line_net_sales.map(money).astype(object)
    f['reason_key'] = (f.order_cancel_reason.astype('string').str.strip().str.casefold()
                       .replace('', pd.NA).fillna(MISSING_REASON))
    f['rx_id'] = f.rx_id.astype('string').str.strip().replace('', pd.NA)
    matched = f.rx_source_rows.gt(0)
    variants = ['rx_customer_variants', 'rx_vet_diet_variants', 'rx_channel_variants', 'rx_source_variants']
    if not f.loc[matched, variants].eq(1).all().all():
        raise ValueError('conflicting prescription registry eligibility values')
    registry_fields = ['rx_customer_id', 'rx_is_vet_diet_flag', 'rx_approval_channel', 'prescription_source']
    if f.loc[matched].groupby('rx_id')[registry_fields].nunique(dropna=False).gt(1).any().any():
        raise ValueError('conflicting repeated prescription eligibility evidence')
    customer_match = (f.customer_id.notna() & f.rx_customer_id.notna()
                      & f.customer_id.eq(f.rx_customer_id))
    qualified = (matched & customer_match & f.is_vet_diet_flag.eq(True)
                 & f.rx_is_vet_diet_flag.eq(True) & f.rx_approval_channel.eq('CUSTOMER_UPLOAD')
                 & f.prescription_source.eq('CMPU')).fillna(False)
    f['qualifying_prescription_match'] = qualified
    selected_keys = f.loc[qualified, KEYS].drop_duplicates()
    associations = f.merge(selected_keys, on=KEYS, how='inner', validate='many_to_one')
    consistent = ['customer_id', 'order_placed_utc', 'reason_key', 'is_vet_diet_flag']
    if associations.groupby(KEYS)[consistent].nunique(dropna=False).gt(1).any().any():
        raise ValueError('conflicting customer, placement, vet-diet flag or cancellation reason within a line')
    if date_basis == 'placed' and not associations.order_placed_utc.between(pd.Timestamp(params['start_date'], tz='UTC'),
            pd.Timestamp(params['end_date'], tz='UTC'), inclusive='left').all():
        raise ValueError('qualifying line outside UTC placement window or missing placement')
    if associations.groupby('order_id')[['customer_id', 'order_placed_utc']].nunique(dropna=False).gt(1).any().any():
        raise ValueError('conflicting order customer or placement across lines')
    # Financial grain is shipment × order line. Distinct shipments with equal
    # amounts are separate contributions; a repeated association is not.
    if (associations.groupby(SHIPMENT_KEYS, dropna=False).order_line_net_sales
            .nunique(dropna=False).gt(1).any()):
        raise ValueError('conflicting sales amounts for the same shipment/order-line key')
    if date_basis == 'shipped-or-cancelled':
        if associations.groupby(SHIPMENT_KEYS, dropna=False)[['shipped_at_utc','cancelled_at_utc']].nunique(dropna=False).gt(1).any().any():
            raise ValueError('conflicting event timestamps for the same shipment/order-line key')
        financial = associations.loc[associations.in_event_window]
    else:
        financial = associations
    shipments = financial.drop_duplicates(SHIPMENT_KEYS).copy()
    shipments['missing_sales'] = shipments.order_line_net_sales.isna()
    shipments['negative_sales'] = shipments.order_line_net_sales.map(lambda v: v is not None and v < 0)
    shipments['zero_sales'] = shipments.order_line_net_sales.map(lambda v: v is not None and v == 0)
    # pandas sums object Decimals without converting to binary floating point.
    with localcontext() as context:
        context.prec = 50
        lines = shipments.groupby(KEYS, sort=False, dropna=False).agg(
            customer_id=('customer_id', 'first'), order_placed_utc=('order_placed_utc', 'first'),
            reason_key=('reason_key', 'first'), known_net_sales=('order_line_net_sales', 'sum'),
            missing_revenue_records=('missing_sales', 'sum'), shipment_records=('missing_sales', 'size')).reset_index()
    lines['known_net_sales'] = lines.known_net_sales.map(money).astype(object)
    lines['actual_net_sales'] = lines.known_net_sales.where(lines.missing_revenue_records.eq(0), None)
    lines['revenue_complete'] = lines.missing_revenue_records.eq(0)
    reason_orders = lines.groupby('order_id').reason_key.nunique()
    rows = []

    def totals(group, reason, row_type):
        missing = int(group.missing_revenue_records.sum())
        known = decimal_sum(group.known_net_sales)
        return dict(row_type=row_type, cancellation_reason=reason, customers=group.customer_id.nunique(), orders=group.order_id.nunique(),
            line_items=len(group), actual_net_sales=None if missing else known,
            known_net_sales=known, missing_revenue_lines=int((~group.revenue_complete).sum()),
            missing_revenue_records=missing, revenue_complete=missing == 0)

    for key, group in lines.groupby('reason_key', sort=True):
        label = MISSING_REASON if key == MISSING_REASON else key.capitalize()
        rows.append(totals(group, label, 'reason'))
    rows.append(totals(lines, 'TOTAL', 'total'))
    summary = pd.DataFrame(rows)
    reasons = summary.loc[summary.row_type.eq('reason')]
    if (int(reasons.line_items.sum()) != len(lines)
            or decimal_sum(reasons.known_net_sales) != decimal_sum(shipments.order_line_net_sales)
            or int(lines.shipment_records.sum()) != len(shipments)):
        raise ValueError('line, shipment or revenue totals do not reconcile')
    audit = dict(source_rows=len(f), source_physical_lines=len(f[KEYS].drop_duplicates()),
        source_rows_without_registry_match=int((~matched).sum()),
        source_rows_with_customer_mismatch=int((matched & ~customer_match).sum()),
        qualifying_association_rows=int(qualified.sum()), qualifying_physical_lines=len(lines),
        excluded_physical_lines=len(f[KEYS].drop_duplicates())-len(lines),
        qualifying_rows_with_repeated_registry_source=int(f.loc[qualified, 'rx_source_rows'].gt(1).sum()),
        full_association_rows_retained=len(associations), financial_shipment_records=len(shipments),
        out_of_window_association_rows=len(associations)-len(financial),
        repeated_financial_keys_collapsed=len(financial)-len(shipments),
        missing_sales_records=int(shipments.missing_sales.sum()),
        negative_sales_records=int(shipments.negative_sales.sum()), zero_sales_records=int(shipments.zero_sales.sum()),
        orders=lines.order_id.nunique(), orders_in_multiple_reason_groups=int(reason_orders.gt(1).sum()))
    if date_basis == 'shipped-or-cancelled':
        lower, upper = pd.Timestamp(start, tz='UTC'), pd.Timestamp(end, tz='UTC')
        shipped = shipments.shipped_at_utc.between(lower, upper, inclusive='left')
        cancelled = shipments.cancelled_at_utc.between(lower, upper, inclusive='left')
        audit.update(shipment_records_in_window=int(shipped.sum()),
                     cancellation_records_in_window=int(cancelled.sum()),
                     records_meeting_both_events=int((shipped & cancelled).sum()))
        if int((shipped | cancelled).sum()) != len(shipments):
            raise ValueError('financial records outside event window')
    return dict(associations=associations, shipments=shipments, order_lines=lines,
                summary=summary, audit=pd.DataFrame(audit.items(), columns=['measure', 'count']))


def independent_verify(raw, summary, start, end, date_basis="placed"):
    """Recompute the final table directly from the raw extract in another engine."""
    import duckdb
    sql = """WITH eligible_keys AS (
        SELECT DISTINCT TRY_CAST(order_id AS DECIMAL(38,0)) AS order_id,
                        TRY_CAST(order_line_id AS DECIMAL(38,0)) AS order_line_id
        FROM source
        WHERE rx_source_rows>0 AND is_vet_diet_flag=TRUE AND rx_is_vet_diet_flag=TRUE
          AND rx_approval_channel='CUSTOMER_UPLOAD' AND prescription_source='CMPU'
          AND TRY_CAST(customer_id AS DECIMAL(38,0))=TRY_CAST(rx_customer_id AS DECIMAL(38,0))
          AND CAST(order_placed_utc AS TIMESTAMP_NS)>=CAST(? AS TIMESTAMP_NS)
          AND CAST(order_placed_utc AS TIMESTAMP_NS)<CAST(? AS TIMESTAMP_NS)
    ), financial AS (
        SELECT DISTINCT TRY_CAST(s.order_id AS DECIMAL(38,0)) AS order_id,
               TRY_CAST(s.order_line_id AS DECIMAL(38,0)) AS order_line_id,
               TRY_CAST(s.shipment_key AS DECIMAL(38,0)) AS shipment_key,
               TRY_CAST(s.customer_id AS DECIMAL(38,0)) AS customer_id,
               COALESCE(NULLIF(LOWER(TRIM(s.order_cancel_reason)),''),'[No recorded cancellation reason]') AS reason,
               CAST(s.order_line_net_sales AS DECIMAL(38,5)) AS sales
        FROM source s JOIN eligible_keys k
          ON TRY_CAST(s.order_id AS DECIMAL(38,0))=k.order_id
         AND TRY_CAST(s.order_line_id AS DECIMAL(38,0))=k.order_line_id
    ) SELECT 'reason' AS row_type,reason,COUNT(DISTINCT customer_id),COUNT(DISTINCT order_id),COUNT(DISTINCT(order_id,order_line_id)),
       CASE WHEN COUNT(*) FILTER(WHERE sales IS NULL)>0 THEN NULL ELSE COALESCE(SUM(sales),0) END
       FROM financial GROUP BY reason
       UNION ALL SELECT 'total','TOTAL',COUNT(DISTINCT customer_id),COUNT(DISTINCT order_id),COUNT(DISTINCT(order_id,order_line_id)),
       CASE WHEN COUNT(*) FILTER(WHERE sales IS NULL)>0 THEN NULL ELSE COALESCE(SUM(sales),0) END FROM financial"""
    bindings = [start, end]
    if date_basis == 'shipped-or-cancelled':
        sql = sql.replace("          AND CAST(order_placed_utc AS TIMESTAMP_NS)>=CAST(? AS TIMESTAMP_NS)\n          AND CAST(order_placed_utc AS TIMESTAMP_NS)<CAST(? AS TIMESTAMP_NS)", "")
        sql = sql.replace("    ) SELECT 'reason'", """        WHERE ((CAST(s.shipped_at_utc AS TIMESTAMP_NS)>=CAST(? AS TIMESTAMP_NS)
              AND CAST(s.shipped_at_utc AS TIMESTAMP_NS)<CAST(? AS TIMESTAMP_NS))
           OR (CAST(s.cancelled_at_utc AS TIMESTAMP_NS)>=CAST(? AS TIMESTAMP_NS)
              AND CAST(s.cancelled_at_utc AS TIMESTAMP_NS)<CAST(? AS TIMESTAMP_NS)))
    ) SELECT 'reason'""")
        bindings = [start, end, start, end]
    with duckdb.connect() as connection:
        connection.register('source', raw.rename(columns=str.lower))
        rows = connection.execute(sql, bindings).fetchall()
    observed = {(kind, reason.casefold()):(customers, orders, lines, amount) for kind, reason, customers, orders, lines, amount in rows}
    expected = {(row.row_type, row.cancellation_reason.casefold()):
                (row.customers, row.orders, row.line_items, None if pd.isna(row.actual_net_sales) else row.actual_net_sales)
                for row in summary.itertuples()}
    if observed != expected:
        raise ValueError('independent raw-source distinct counts or revenue do not reconcile')
    return dict(engine='DuckDB, raw-source aggregation', sql=sql, parameters=bindings, verified_groups=len(rows))


def write_parquet(frame, path):
    """Fix monetary schema even for empty or entirely missing columns."""
    table = pa.Table.from_pandas(frame.drop(columns=[c for c in MONEY_COLUMNS if c in frame]), preserve_index=False)
    for column in [c for c in frame if c in MONEY_COLUMNS]:
        table = table.append_column(column, pa.array(frame[column].tolist(), type=pa.decimal128(38, 5)))
    pq.write_table(table, path)


def display_summary(summary):
    displayed = summary[['cancellation_reason', 'customers', 'orders', 'line_items', 'actual_net_sales']].copy()
    displayed['actual_net_sales'] = displayed.actual_net_sales.map(
        lambda value: 'Incomplete (missing sales)' if pd.isna(value) else f'{value:,.2f}')
    for column in ['customers', 'orders', 'line_items']:
        displayed[column] = displayed[column].map(lambda n: f'{n:,}')
    return displayed.rename(columns=dict(cancellation_reason='Order cancellation reason', customers='Customers', orders='Orders',
        line_items='Line items', actual_net_sales='Net sales'))


def write_outputs(results, metadata, directory, tables):
    tables.mkdir(parents=True, exist_ok=True)
    for name, frame in results.items():
        write_parquet(frame, directory/(name.replace('_', '-')+'.parquet'))
    params = metadata['parameters']
    overlaps = int(results['audit'].set_index('measure').loc['orders_in_multiple_reason_groups', 'count'])
    note = (f"Order placement [{params['start_date']}, {params['end_date']}) UTC. "
        'All orders with qualifying vet-diet lines; prescription registry matching requires RX_ID and numeric customer ID, '
        'vet diet, CUSTOMER_UPLOAD approval channel and CMPU prescription source. No prescription-creation, first-order, '
        'order-status or cancellation-date restriction. Revenue covers qualifying lines only. '
        'ORDER_LINE_NET_SALES is summed once per shipment/order-line record; distinct shipments with equal amounts '
        'remain separate. Counts use distinct customers, physical orders and order lines. Customers can occur in multiple reason groups; TOTAL counts each customer once. '
        'Current cancellation reasons are trimmed and grouped case-insensitively; missing/blank reasons are explicit. '
        'No recorded reason does not establish an uncancelled order. '
        'Net sales are shown without an assumed currency symbol. '
        'Zero and negative amounts remain included. Five decimal places are retained in Parquet; only display is rounded. '
        'Groups with any missing sales have incomplete revenue; known subtotals and missing counts remain in exports. '
        f'{overlaps:,} orders occur in multiple reason groups; the TOTAL row always counts each order once. '
        'This is the actual-sales baseline for opportunity sizing. '
        f"Extracted {metadata['extracted_at_utc']}; source SHA-256 {metadata['parquet_sha256']}.\n\n")
    if params.get('date_basis') == 'shipped-or-cancelled':
        note = note.replace('Order placement [', 'Shipment or cancellation records [')
        note = note.replace('order-status or cancellation-date restriction.', 'order-status restriction; shipment or cancellation timestamps select records.')
        note += ('Only shipment/line contributions with a shipment or cancellation timestamp in the window contribute sales. '
                 'Split-shipment contributions outside the window are excluded; records meeting both dates count once.\n\n')
    write_text(tables/'order-cancellation-summary.md', '# Opportunity Analysis: order cancellation summary\n\n'
        + note + markdown_table(display_summary(results['summary']))+'\n')
    write_text(tables/'order-cancellation-audit.md', '# Opportunity Analysis: audit\n\n'
        + note + markdown_table(results['audit'])+'\n')
    # Explicit preview avoids creating enormous line-detail Markdown files.
    write_text(tables/'order-line-preview.md', '# Opportunity Analysis: line detail preview\n\n'+note
        + f"First 25 of {len(results['order_lines']):,} qualifying lines; complete records are in data/opportunity/.\n\n"
        + markdown_table(results['order_lines'].head(25))+'\n')
    context = results['associations'].groupby(
        ['site_key', 'order_line_site_key', 'legal_company_description', 'order_line_transaction_type'],
        dropna=False).size().reset_index(name='association_rows')
    write_parquet(context, directory/'site-context.parquet')
    write_text(directory/'analysis.json', json.dumps(dict(metadata, definition=note,
        implementation_sha256=digest(Path(__file__)), generated_at_utc=datetime.now(timezone.utc).isoformat(),
        exports={p.name:digest(p) for p in directory.glob('*.parquet') if p.name != 'source.parquet'}), indent=2)+'\n')
    return tables/'order-cancellation-summary.md'


def financial_opportunity_report_sql(source_sql, verification):
    """Compose executable Snowflake SQL from the extraction and verified aggregation."""
    aggregate = verification['sql']
    for value in verification['parameters']:
        value = date.fromisoformat(value).isoformat()
        aggregate = aggregate.replace('?', "'"+value+"'", 1)
    if '?' in aggregate:
        raise ValueError('unbound financial-report SQL parameter')
    aggregate = aggregate.replace('TIMESTAMP_NS', 'TIMESTAMP_NTZ')
    aggregate = aggregate.replace('COUNT(DISTINCT(order_id,order_line_id))',
                                  'COUNT(DISTINCT order_id,order_line_id)')
    aggregate = aggregate.replace('COUNT(*) FILTER(WHERE sales IS NULL)',
                                  'COUNT_IF(sales IS NULL)')
    assert aggregate.startswith('WITH eligible_keys AS (')
    return ('-- Financial opportunity table; UTC dates; includes TOTAL.\n'
            '-- Source validation rejects conflicting line/shipment values before publication.\n'
            'WITH source AS (\n'+source_sql.strip().rstrip(';')+'\n),\n'
            +aggregate.removeprefix('WITH ')+'\nORDER BY row_type, reason;\n')


def financial_opportunity_latex(summary, params):
    """Render the report appendix from the same verified summary as Markdown."""
    def escape(value):
        return ''.join({'\\':r'\textbackslash{}','&':r'\&','%':r'\%','_':r'\_','#':r'\#',
                        '{':r'\{','}':r'\}'}.get(char,char) for char in str(value))
    first = date.fromisoformat(params['start_date']).strftime('%B %-d, %Y')
    end = date.fromisoformat(params['end_date'])
    last = (end-timedelta(days=1)).strftime('%B %-d, %Y')
    rows=[]
    for row in summary.itertuples(index=False):
        if row.row_type=='total': rows.append(r'\midrule')
        amount='Incomplete' if pd.isna(row.actual_net_sales) else f'{row.actual_net_sales:,.2f}'
        if row.row_type == 'reason' and row.cancellation_reason != MISSING_REASON:
            amount = r'\textcolor{gray}{'+amount+'}'
        rows.append('{'+escape(row.cancellation_reason)+'} & '+f'{row.customers:,} & {row.orders:,} & {row.line_items:,} & {amount}'+r' \\')
    text = r'''\clearpage
\subsection{Financial Opportunity Analysis}\label{subsec:financial-opportunity-analysis}
Table~\ref{tab:financial-opportunity-cancellations} reports distinct customer and order counts,
qualifying order-line counts and recorded net sales by cancellation reason
for orders placed from '''+first+' through '+last+r''', inclusive, UTC
(\texttt{['''+params['start_date']+', '+params['end_date']+r''')}, with an exclusive end date).
The population requires vet-diet lines matched by prescription ID and numeric
customer ID to vet-diet prescriptions with
\texttt{PRESCRIPTION\_SOURCE = CMPU} and
\texttt{APPROVAL\_CHANNEL = CUSTOMER\_UPLOAD}.

\subsubsection{Orders by cancellation reason}
\begin{table}[htbp]
\centering
\caption{Financial opportunity baseline: cancellation reasons, customers, orders, qualifying order lines and net sales for CMPU vet-diet customer-upload orders placed '''+first+' through '+last+r''', inclusive, UTC.}
\label{tab:financial-opportunity-cancellations}
\small
\setlength{\tabcolsep}{5pt}
\begin{tabular}{@{}>{\raggedright\arraybackslash}p{0.40\linewidth}rrrr@{}}
\toprule
Cancellation reason & Customers & Orders & Order lines & Net sales \\
\midrule
'''+ '\n'.join(rows)+r'''
\bottomrule
\end{tabular}

\begin{minipage}{\linewidth}
\footnotesize
\textit{Notes:} Includes all qualifying orders, including subsequent orders;
there is no prescription-creation, order-status or cancellation-date cutoff.
This differs from the prescription-creation cohort and aged-cancellation cutoff
used in Table~\ref{tab:study-population-counts}.
Counts are distinct customers, orders and physical order lines. Customers may
appear in multiple reason rows; TOTAL counts each customer once. Sales include only
qualifying lines, summed from \texttt{ORDER\_LINE\_NET\_SALES} in
\texttt{EDLDB.BT\_HCA\_HCDM.ORDER\_LINE\_COST\_MEASURES\_RXP},
once per shipment-and-line record. Zero and negative sales remain included;
any missing sales make the group total incomplete. Display rounds to two
decimals; exports retain five. Current cancellation reasons are grouped
case-insensitively; a missing reason does not establish an uncancelled order.
Orders can appear in multiple reason rows if their lines have different
reasons; TOTAL counts each order once. Line counts and sales are additive.
Gray net-sales amounts have a recorded cancellation reason and represent
unrealized sales, not realized revenue. TOTAL includes these gray amounts.
Recorded net sales are a baseline for opportunity sizing, not an estimate of
recoverable revenue from cancelled orders.
\end{minipage}
\end{table}
'''

    if params.get('date_basis') == 'shipped-or-cancelled':
        text = text.replace('orders placed', 'orders shipped or cancelled')
        text = text.replace('there is no prescription-creation, order-status or cancellation-date cutoff.',
            'shipment or cancellation records must fall in the reporting window. There is no order-placement or prescription-creation restriction.')
        text = text.replace('once per shipment-and-line record.',
            'once per shipment-and-line record with a shipment or cancellation timestamp in the window. Split-shipment sales outside the window are excluded; records meeting both dates count once.')
    includes=report_tables.follow_up_inputs(ROOT/'src/latex/appendix')
    if includes:text+=includes+'\n'
    return text


def extract(sql_path, parquet, directory):
    runner = ROOT/'.agents/skills/rxp-sql/scripts/run_snowflake_query.py'
    with (directory/'extract.log').open('w') as log:
        result = subprocess.run([sys.executable, str(runner), str(sql_path), '--output-parquet',
            str(parquet.relative_to(ROOT)), '--sql-log-dir', str((directory/'sql-history').relative_to(ROOT))],
            cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
    if result.returncode == 0:
        return dict(engine='DuckDB Snowflake extension')
    failure = (directory/'extract.log').read_text()
    if '390195' not in failure or 'ID Token is invalid' not in failure:
        raise ValueError(f'Snowflake extraction failed; inspect {directory / "extract.log"}')
    click.echo('Cached Snowflake SSO token expired; refreshing with the installed browser-SSO connector.')
    # Same account, role, database and read-only SQL as the repository runner.
    import snowflake.connector
    helpers = runpy.run_path(str(runner))
    settings = helpers['parse_dotenv'](ROOT/'.env')
    sql = sql_path.read_text()
    helpers['validate_statement'](sql)
    options = {key.lower():settings['RXP_SNOWFLAKE_'+key] for key in ['ACCOUNT', 'USER', 'DATABASE', 'WAREHOUSE', 'SCHEMA']}
    if 'RXP_SNOWFLAKE_ROLE' in settings:
        options['role'] = settings['RXP_SNOWFLAKE_ROLE']
    with snowflake.connector.connect(**options, authenticator='externalbrowser', client_store_temporary_credential=False) as connection:
        with connection.cursor() as cursor:
            cursor.execute(sql)
            table = cursor.fetch_arrow_all()
            if table is None:
                raise ValueError('Snowflake returned no result schema')
            pq.write_table(table, parquet)
            return dict(engine='snowflake-connector-python; expired ADBC token fallback', query_id=cursor.sfqid)


def load_source(params, sql, cached):
    directory = ROOT/'data/opportunity/order-cancellation-summary'/f"{params['start_date']}_{params['end_date']}"
    if params.get('date_basis'): directory = directory/params['date_basis']
    parquet, manifest = directory/'source.parquet', directory/'source.json'
    identity = dict(version=VERSION, parameters=params, criteria=CRITERIA,
                    sql_sha256=hashlib.sha256(sql.encode()).hexdigest())
    if cached:
        metadata = json.loads(manifest.read_text())
        if (metadata.get('identity') != identity or metadata.get('sql') != sql
                or metadata.get('parquet_sha256') != digest(parquet)):
            raise ValueError('cached SQL, dates, eligibility definition or source fingerprint differs; rerun fresh')
    else:
        directory.mkdir(parents=True, exist_ok=True)
        manifest.unlink(missing_ok=True)
        query = directory/'query.sql'
        write_text(query, sql+'\n')
        engine = extract(query, parquet, directory)
        metadata = dict(identity=identity, parameters=params, sql=sql, **engine,
            parquet_sha256=digest(parquet), extracted_at_utc=datetime.now(timezone.utc).isoformat())
    return pd.read_parquet(parquet), metadata, directory


@click.command()
@click.option('--start-date', default='2026-05-01', show_default=True)
@click.option('--end-date', default='2026-08-01', show_default=True, help='Exclusive UTC reporting-window end date.')
@click.option('--cached', is_flag=True)
@click.option('--print-sql', is_flag=True)
@click.option('--date-basis', type=click.Choice(['placed','shipped-or-cancelled']), default='placed', show_default=True)
@click.option('--write-latex', is_flag=True, help='Update the Financial Opportunity Analysis appendix.')
def main(start_date, end_date, cached, print_sql, date_basis, write_latex):
    try:
        params = parameters(start_date, end_date, date_basis)
        sql = render_sql(start_date, end_date, date_basis)
        if print_sql:
            click.echo(sql)
            return
        raw, metadata, directory = load_source(params, sql, cached)
        results = summarize(raw, start_date, end_date, date_basis)
        verification = independent_verify(raw, results['summary'], start_date, end_date, date_basis)
        if not cached:
            write_text(directory/'source.json', json.dumps(metadata, indent=2)+'\n')
        metadata = dict(metadata, independent_verification=verification)
        dated = f'{start_date}_{date.fromisoformat(end_date)-timedelta(days=1)}'
        tables = ROOT/'outputs/tables/opportunity'/dated
        if date_basis != 'placed': tables = tables/date_basis
        path = write_outputs(results, metadata, directory, tables)
        report_sql = financial_opportunity_report_sql(metadata['sql'], verification)
        write_text(directory/'summary-report.sql', report_sql)
        if write_latex:
            (ROOT/'src/latex/appendix').mkdir(parents=True, exist_ok=True)
            write_text(ROOT/'src/latex/appendix/financial_opportunity.tex',
                       financial_opportunity_latex(results['summary'], params))
        click.echo(display_summary(results['summary']).to_string(index=False))
        click.echo(f'Table: {path}\nComplete source and details: {directory}')
    except (ValueError, OSError, KeyError, InvalidOperation, subprocess.CalledProcessError) as error:
        raise click.ClickException(str(error)) from error


if __name__ == '__main__':
    main()

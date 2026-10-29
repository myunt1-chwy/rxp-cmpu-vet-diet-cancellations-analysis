"""Distinct aged orders and customers initiating inbound contacts around cancellation."""
from datetime import date,datetime,timedelta,timezone
import hashlib
import json

import click
import duckdb
from jinja2 import Environment,StrictUndefined
import pandas as pd

from src.python import create_opportunity_order_cancellation_summary as base
from src.python.markdown_tables import markdown_table,write_text

ROOT=base.ROOT
MIN_DAY=-13
MAX_DAY=3
DAY_NS=86_400_000_000_000
ORDER_COLUMNS=['order_id','customer_id','cancelled_at_utc','registry_variants','qualifying_lines','customer_variants','cancellation_variants']
VERIFY_SQL="""WITH days AS (SELECT range AS relative_day FROM range({min_day},{end_day})), counts AS (
 SELECT CAST(FLOOR((epoch_ns(contact_time_sql)-epoch_ns(cancellation_time_sql))/86400000000000.0) AS INTEGER) AS relative_day,
 COUNT(DISTINCT customer_id) AS distinct_customers,COUNT(DISTINCT order_id) AS distinct_aged_orders
 FROM contacts WHERE direction='inbound' AND contact_customer_id=customer_id
 AND contact_time_sql IS NOT NULL {handled_filter}
 GROUP BY 1)
 SELECT d.relative_day,COALESCE(c.distinct_customers,0) AS distinct_customers,
 COALESCE(c.distinct_aged_orders,0) AS distinct_aged_orders
 FROM days d LEFT JOIN counts c USING(relative_day) ORDER BY d.relative_day"""


FREQUENCY_VERIFY_SQL="""WITH per_customer AS (
 SELECT customer_id,COUNT(DISTINCT FLOOR((epoch_ns(contact_time_sql)-epoch_ns(cancellation_time_sql))/86400000000000.0)) AS days_contacted
 FROM contacts WHERE direction='inbound' AND contact_customer_id=customer_id
 AND contact_time_sql IS NOT NULL {handled_filter} GROUP BY customer_id
), cohort AS (SELECT DISTINCT customer_id FROM aged_orders), counts AS (
 SELECT COALESCE(p.days_contacted,0)::BIGINT AS days_contacted,COUNT(*) AS distinct_customers
 FROM cohort c LEFT JOIN per_customer p USING(customer_id) GROUP BY 1
), days AS (SELECT range AS days_contacted FROM range(0,{end_count}))
SELECT d.days_contacted,COALESCE(c.distinct_customers,0) AS distinct_customers
FROM days d LEFT JOIN counts c USING(days_contacted) ORDER BY d.days_contacted"""


def render_sql(start,end):
    return Environment(undefined=StrictUndefined).from_string((ROOT/'src/sql/opportunity_aged_customer_contacts.sql').read_text()).render(**base.parameters(start,end),min_day=MIN_DAY,end_day=MAX_DAY+1)


def summary_sql(sql,handled_only):
    handled='AND handled_flag=TRUE' if handled_only else ''
    return '''WITH source AS (
'''+sql.rstrip()+'''
), days AS (SELECT ROW_NUMBER() OVER (ORDER BY SEQ4())'''+f'{MIN_DAY-1} AS relative_day FROM TABLE(GENERATOR(ROWCOUNT=>{MAX_DAY-MIN_DAY+1})))'+''', counts AS (
 SELECT FLOOR(DATEDIFF(nanosecond,cancelled_at_utc::TIMESTAMP_NTZ,contact_at_utc::TIMESTAMP_NTZ)::DOUBLE/86400000000000.0)::INTEGER AS relative_day,
 COUNT(DISTINCT customer_id) AS distinct_customers,COUNT(DISTINCT order_id) AS distinct_aged_orders
 FROM source WHERE contact_order_id IS NOT NULL AND contact_customer_id=customer_id
 AND LOWER(TRIM(session_initial_direction))='inbound' AND contact_at_utc IS NOT NULL
 '''+handled+'''
 GROUP BY 1)
 SELECT d.relative_day,COALESCE(c.distinct_customers,0) AS distinct_customers,
 COALESCE(c.distinct_aged_orders,0) AS distinct_aged_orders
 FROM days d LEFT JOIN counts c ON d.relative_day=c.relative_day ORDER BY d.relative_day
'''


def analyze(raw,start,end,handled_only=False):
    f=raw.rename(columns=str.lower).copy()
    for col in ['order_id','customer_id','contact_order_id','contact_customer_id']:f[col]=f[col].map(base.identifier)
    for col in ['cancelled_at_utc','contact_at_utc']:
        f[col]=pd.to_datetime(f[col],utc=True,format='mixed').astype('datetime64[ns, UTC]')
    if f[['order_id','customer_id','cancelled_at_utc']].isna().any().any():raise ValueError('missing aged-order keys/timestamps')
    if f[['registry_variants','customer_variants','cancellation_variants']].ne(1).any().any():raise ValueError('conflicting aged source values')
    if not f.cancelled_at_utc.between(pd.Timestamp(start,tz='UTC'),pd.Timestamp(end,tz='UTC'),inclusive='left').all():raise ValueError('cancellation outside requested window')
    if f.groupby('order_id')[ORDER_COLUMNS[1:]].nunique(dropna=False).gt(1).any().any():raise ValueError('conflicting aged order evidence')
    orders=f[ORDER_COLUMNS].drop_duplicates('order_id').copy()
    contacts=f.loc[f.contact_order_id.notna()].copy()
    if not contacts.contact_order_id.eq(contacts.order_id).all():raise ValueError('contact order ID differs')
    contacts['direction']=contacts.session_initial_direction.astype('string').str.strip().str.lower()
    known=contacts.loc[contacts.leg_id.notna() & contacts.session_id.notna()]
    source_fields=['session_id','contact_customer_id','contact_at_utc','direction','handled_flag','session_channel','session_ingress_point']
    if known.groupby(['contact_order_id','session_id','leg_id'])[source_fields].nunique(dropna=False).gt(1).any().any():raise ValueError('conflicting contact leg evidence')
    duplicates=int(contacts.duplicated().sum());contacts=contacts.drop_duplicates().copy()
    elapsed=(contacts.contact_at_utc-contacts.cancelled_at_utc).astype('int64').astype('Int64')
    elapsed.loc[contacts.contact_at_utc.isna()]=pd.NA
    contacts['elapsed_ns']=elapsed
    contacts['relative_day']=elapsed//DAY_NS
    dated=contacts.contact_at_utc.notna()
    if not contacts.loc[dated,'relative_day'].between(MIN_DAY,MAX_DAY).all():raise ValueError('contact outside extracted day window')
    contacts['customer_identity']=pd.Series('Matching customer',index=contacts.index,dtype='str')
    contacts.loc[contacts.contact_customer_id.isna(),'customer_identity']='Missing contact customer'
    contacts.loc[contacts.contact_customer_id.notna() & contacts.contact_customer_id.ne(contacts.customer_id),'customer_identity']='Different contact customer'
    contacts['included']=(contacts.direction.eq('inbound').fillna(False) & contacts.customer_identity.eq('Matching customer') & dated)
    if handled_only:contacts['included']=contacts.included & contacts.handled_flag.eq(True).fillna(False)
    selected=contacts.loc[contacts.included]
    counts=selected.groupby('relative_day').agg(distinct_customers=('customer_id','nunique'),distinct_aged_orders=('order_id','nunique'))
    daily=pd.DataFrame({'relative_day':range(MIN_DAY,MAX_DAY+1)}).merge(counts,on='relative_day',how='left').fillna(0)
    for col in ['distinct_customers','distinct_aged_orders']:daily[col]=daily[col].astype('int64')
    per_customer=orders[['customer_id']].drop_duplicates().merge(
        selected.groupby('customer_id').relative_day.nunique().rename('days_contacted'),on='customer_id',how='left').fillna({'days_contacted':0})
    per_customer.days_contacted=per_customer.days_contacted.astype('int64')
    frequency=pd.DataFrame({'days_contacted':range(MAX_DAY-MIN_DAY+2)}).merge(
        per_customer.groupby('days_contacted').size().rename('distinct_customers'),on='days_contacted',how='left').fillna(0)
    frequency.distinct_customers=frequency.distinct_customers.astype('int64')
    verify=VERIFY_SQL.format(min_day=MIN_DAY,end_day=MAX_DAY+1,handled_filter='AND handled_flag=TRUE' if handled_only else '')
    independent=contacts.copy()
    independent['contact_time_sql']=independent.contact_at_utc.dt.tz_localize(None)
    independent['cancellation_time_sql']=independent.cancelled_at_utc.dt.tz_localize(None)
    with duckdb.connect() as c:
        c.execute("SET TimeZone='UTC'");c.register('contacts',independent)
        expected=c.execute(verify).df()
        c.register('aged_orders',orders)
        frequency_expected=c.execute(FREQUENCY_VERIFY_SQL.format(end_count=MAX_DAY-MIN_DAY+2,handled_filter='AND handled_flag=TRUE' if handled_only else '')).df()
    pd.testing.assert_frame_equal(daily,expected,check_dtype=False)
    pd.testing.assert_frame_equal(frequency,frequency_expected,check_dtype=False)
    assert frequency.distinct_customers.sum()==orders.customer_id.nunique()
    assert frequency.loc[frequency.days_contacted.gt(0),'distinct_customers'].sum()==selected.customer_id.nunique()
    direction=contacts.assign(direction=contacts.direction.fillna('[Missing direction]')).groupby(['direction','handled_flag'],dropna=False).agg(
        contact_rows=('order_id','size'),distinct_customers=('customer_id','nunique'),distinct_aged_orders=('order_id','nunique')).reset_index()
    identity=contacts.groupby('customer_identity').size().rename('contact_rows').reset_index()
    channels=selected.groupby(['session_channel','session_ingress_point'],dropna=False).agg(contact_rows=('order_id','size'),distinct_customers=('customer_id','nunique'),distinct_aged_orders=('order_id','nunique')).reset_index()
    audit=dict(aged_customers=orders.customer_id.nunique(),aged_orders=len(orders),qualifying_lines=int(orders.qualifying_lines.sum()),
        contact_rows_in_extracted_window=len(contacts),identical_contact_duplicates_collapsed=duplicates,
        inbound_rows=int(contacts.direction.eq('inbound').sum()),outbound_rows=int(contacts.direction.eq('outbound').sum()),
        unknown_direction_rows=int((~contacts.direction.isin(['inbound','outbound'])).sum()),
        missing_contact_customer_rows=int(contacts.customer_identity.eq('Missing contact customer').sum()),
        mismatched_contact_customer_rows=int(contacts.customer_identity.eq('Different contact customer').sum()),
        missing_contact_time_rows=int(contacts.contact_at_utc.isna().sum()),
        included_contact_rows=len(selected),distinct_customers_contacting=selected.customer_id.nunique(),
        distinct_aged_orders_with_contacts=selected.order_id.nunique(),handled_only=handled_only,
        required_days=list(range(MIN_DAY,MAX_DAY+1)),independent_verification='DuckDB independently matches every UTC nanosecond-floor day/customer/order count, including zero rows')
    return dict(aged_orders=orders,contact_details=contacts,customer_contact_days=per_customer,contact_day_frequency=frequency,daily_summary=daily,direction_audit=direction,customer_identity_audit=identity,channel_audit=channels),audit,verify


def latex_table(daily,audit,start,end,as_of,handled_only):
    if daily.relative_day.tolist()!=list(range(MIN_DAY,MAX_DAY+1)):raise ValueError('contact table must include every day -13 through +3')
    first=date.fromisoformat(start).strftime('%B %-d, %Y')
    last=(date.fromisoformat(end)-timedelta(days=1)).strftime('%B %-d, %Y')
    rows=[f'{r.relative_day} & {r.distinct_customers:,} & {r.distinct_aged_orders:,}'+r' \\' for r in daily.itertuples()]
    handled_note=r'Require \texttt{HANDLED\_FLAG=TRUE}.' if handled_only else 'Include handled, unhandled and unknown-handled inbound attempts.'
    return r"""\clearpage
\subsection{Contact Analysis}\label{subsec:contact-analysis}
\subsubsection{Contacts by day relative to cancellation}
Table~\ref{tab:aged-customer-contacts-by-cancellation-day} summarizes inbound
contacts linked to CMPU vet-diet \texttt{CUSTOMER\_UPLOAD} aged orders cancelled
from """+first+' through '+last+r""", inclusive, UTC.
The full cohort contains """+f"{audit['aged_customers']:,} customers and {audit['aged_orders']:,} aged orders."+r"""

\begin{table}[!htbp]
\centering
\caption{Customer-initiated inbound contacts by day relative to aged-order cancellation: distinct customers contacting and distinct aged order IDs, from 13 days before through day 3 after cancellation. A total of """+f"{audit['distinct_customers_contacting']:,}"+r""" distinct customers contacted across this window.}
\label{tab:aged-customer-contacts-by-cancellation-day}
\begin{tabular}{@{}rrr@{}}
\toprule
Days relative to cancellation & Customers contacting & Aged order IDs \\
\midrule
"""+'\n'.join(rows)+r"""
\bottomrule
\end{tabular}

\begin{minipage}{\linewidth}
\footnotesize
\textit{Notes:} Customer-initiated is defined by
\texttt{SESSION\_INITIAL\_DIRECTION=inbound} in
\texttt{EDLDB.BT\_CUSTOMER\_CARE.FCT\_CONTACTS\_BRD}, across all contact
categories. """+handled_note+r""" Match the original aged \texttt{ORDER\_ID} and require
the contact's numeric \texttt{CUSTOMER\_ID} to match the order's customer.
Use UTC \texttt{SESSION\_START\_DTTM}. Day $n$ is the elapsed 24-hour interval
$[n,n+1)$ days relative to cancellation: day $-1$ is the preceding 24 hours,
and day $0$ starts exactly at cancellation. These are elapsed bins rather
than calendar-date differences. All seventeen rows from $-13$ through $+3$
are retained, with zero for missing days. Count each customer and aged order
once per day, regardless of repeat contact legs, sessions or qualifying order
lines. Counts may overlap across days and should not be added as global unique
totals. Missing timestamps or customer IDs, mismatching customer IDs, unknown
directions and outbound contacts remain audited and are excluded from this
table. Email contacts with Other ingress are included; inbound direction is
a source proxy and does not establish human initiation. Full channel/ingress
audits are exported with the data. Original eligibility uses cancellation
dates and all qualifying orders, without a first-order or prescription-creation
restriction. Observation cutoff: """+as_of+r""" 00:00 UTC, allowing the full positive-day window.
\end{minipage}
\end{table}
"""


def frequency_latex(frequency,audit):
    rows=[f'{r.days_contacted} & {r.distinct_customers:,}'+r' \\' for r in frequency.itertuples()]
    return r"""
\clearpage
\subsubsection{Customer contact-day frequency}
Table~\ref{tab:aged-customer-contact-day-frequency} groups customers by the
number of distinct relative days on which they contacted during the same
$-13$ through $+3$ window.
\begin{table}[!htbp]
\centering
\caption{Frequency of customer contact days around aged-order cancellation: number of distinct relative days contacted versus number of customers. Of """+f"{audit['aged_customers']:,}"+r""" cohort customers, """+f"{audit['distinct_customers_contacting']:,}"+r""" contacted on at least one day.}
\label{tab:aged-customer-contact-day-frequency}
\begin{tabular}{@{}rr@{}}
\toprule
Number of days contacted & Number of customers \\
\midrule
"""+'\n'.join(rows)+r"""
\bottomrule
\end{tabular}

\begin{minipage}{\linewidth}
\footnotesize
\textit{Notes:} Same CMPU vet-diet \texttt{CUSTOMER\_UPLOAD} aged cohort,
cancellation dates, observation cutoff and inbound contact rules as
Table~\ref{tab:aged-customer-contacts-by-cancellation-day}.
Count each distinct relative 24-hour day bin from $-13$ through $+3$ once
per customer across all qualifying aged orders. Multiple contacts, sessions,
legs or orders on the same relative day do not increase the day count.
These are relative cancellation-day bins, rather than distinct calendar dates.
Each customer appears in exactly one frequency row; zero includes cohort
customers with no qualifying contact in this window. All frequencies from
0 through 17 are retained, including zero-count rows. Customer counts sum to
the full cohort; positive-day rows sum to the distinct contacting customers.
\end{minipage}
\end{table}
"""


def publish_latex(text):
    appendix=ROOT/'src/latex/appendix';appendix.mkdir(parents=True,exist_ok=True)
    for name in ['contact_frequency_reorders','contact_window_reorders']:
        if (appendix/(name+'.tex')).exists():text=text.rstrip()+'\n\n'+r'\input{appendix/'+name+'}\n'
    write_text(appendix/'contact_analysis.tex',text)
    main=ROOT/'src/latex/main.tex';include=r'\input{appendix/contact_analysis}'
    if main.exists():
        body=main.read_text()
        if include not in body:
            anchor=r'\input{appendix/financial_opportunity}'
            if anchor in body:body=body.replace(anchor,anchor+'\n'+include,1)
            else:
                anchor=r'\input{appendix/study_population_analysis}'
                if anchor not in body:raise ValueError('cannot find the report appendix insertion point')
                body=body.replace(anchor,include+'\n'+anchor,1)
            write_text(main,body)


@click.command()
@click.option('--start-date',default='2026-05-01',show_default=True)
@click.option('--end-date',default='2026-08-01',show_default=True,help='Exclusive UTC aged cancellation end.')
@click.option('--as-of-date',default='2026-10-28',show_default=True)
@click.option('--write-latex',is_flag=True)
@click.option('--handled-only',is_flag=True,help='Require HANDLED_FLAG=TRUE as in the previous contact study.')
@click.option('--cached',is_flag=True)
@click.option('--print-sql',is_flag=True,help='Print standalone Snowflake SQL for the final seventeen-row table.')
def main(start_date,end_date,as_of_date,write_latex,handled_only,cached,print_sql):
    params=base.parameters(start_date,end_date)
    if date.fromisoformat(as_of_date)<date.fromisoformat(end_date)+timedelta(days=MAX_DAY+1):raise click.ClickException('as-of must allow all contacts through day +3')
    sql=render_sql(start_date,end_date);report_sql=summary_sql(sql,handled_only)
    if print_sql:click.echo(report_sql);return
    directory=ROOT/'data/opportunity/aged-customer-contacts'/f'{start_date}_{end_date}_as-of-{as_of_date}'
    directory.mkdir(parents=True,exist_ok=True);source=directory/'source.parquet';manifest=directory/'source.json'
    identity=dict(version=1,**params,as_of_date=as_of_date,timezone='UTC',min_day=MIN_DAY,max_day=MAX_DAY,sql_sha256=hashlib.sha256(sql.encode()).hexdigest())
    if cached:
        meta=json.loads(manifest.read_text())
        if meta['identity']!=identity or meta['source_sha256']!=base.digest(source):raise click.ClickException('cache fingerprint differs; rerun fresh')
    else:
        manifest.unlink(missing_ok=True);write_text(directory/'query.sql',sql)
        engine=base.extract(directory/'query.sql',source,directory)
        meta=dict(identity=identity,source_sha256=base.digest(source),extracted_at_utc=datetime.now(timezone.utc).isoformat(),**engine)
    frames,audit,verify=analyze(pd.read_parquet(source),start_date,end_date,handled_only)
    mode='handled-inbound' if handled_only else 'all-inbound';analysis=directory/mode;analysis.mkdir(parents=True,exist_ok=True)
    for name,frame in frames.items():frame.to_parquet(analysis/(name.replace('_','-')+'.parquet'),index=False)
    write_text(analysis/'verification.sql',verify+';\n');write_text(analysis/'summary.sql',report_sql)
    write_text(analysis/'frequency-verification.sql',FREQUENCY_VERIFY_SQL.format(end_count=MAX_DAY-MIN_DAY+2,handled_filter='AND handled_flag=TRUE' if handled_only else '')+';\n')
    write_text(analysis/'analysis.json',json.dumps(dict(source_sha256=meta['source_sha256'],audit=audit,
        exports={p.name:base.digest(p) for p in analysis.glob('*.parquet')}),indent=2)+'\n')
    write_text(manifest,json.dumps(meta,indent=2)+'\n')
    tables=ROOT/'outputs/tables/opportunity'/f'{start_date}_{date.fromisoformat(end_date)-timedelta(days=1)}';tables.mkdir(parents=True,exist_ok=True)
    display=frames['daily_summary'].rename(columns={'relative_day':'Days relative to cancellation','distinct_customers':'Distinct customers contacting','distinct_aged_orders':'Distinct aged order IDs'})
    note=(f'CMPU vet-diet CUSTOMER_UPLOAD aged cancellations [{start_date}, {end_date}) UTC, all qualifying orders and customers, with no first-order or prescription-creation restriction. '
          f"{audit['aged_orders']:,} aged orders / {audit['aged_customers']:,} customers; as of {as_of_date} 00:00 UTC. "
          'Use EDLDB.BT_CUSTOMER_CARE.FCT_CONTACTS_BRD, joined on original aged ORDER_ID, requiring contact CUSTOMER_ID to match the aged-order customer. '
          'Customer-initiated means normalized SESSION_INITIAL_DIRECTION=inbound, all categories; no WISMO filter. '
          +('Require HANDLED_FLAG=TRUE. ' if handled_only else 'Include handled, unhandled and unknown-handled inbound attempts. ')+
          'Time is SESSION_START_DTTM, confirmed UTC in the previous contact/Sankey study. Day n is the exact 24-hour interval [cancellation+n days, cancellation+(n+1) days): negative days are before cancellation, zero starts at cancellation. '
          'Always include all seventeen day rows -13 through +3, filling absent counts with zero. Each customer/order counts once per day regardless of contact legs, sessions or qualifying order lines; counts can overlap across days and must not be summed as global unique totals. '
          'Missing timestamps, unknown directions, missing/mismatched contact customer IDs and outbound contacts remain in details/audits but are excluded from the table. Source has no contacts outside the requested dated window, except undated rows retained for audit.\n\n')
    suffix='-handled-only' if handled_only else ''
    write_text(tables/f'aged-customer-contacts-by-cancellation-day{suffix}.md','# Customer-initiated contacts around aged cancellation\n\n'+note+markdown_table(display)+'\n')
    frequency=frames['contact_day_frequency'].rename(columns={'days_contacted':'Number of days contacted','distinct_customers':'Number of customers'})
    write_text(tables/f'aged-customer-contact-day-frequency{suffix}.md','# Customer contact-day frequency\n\n'+note+'Each customer is assigned to one row by distinct relative day bins across their aged orders. Zero includes customers with no qualifying contact; all 0..17 rows are present.\n\n'+markdown_table(frequency)+'\n')
    latex=latex_table(frames['daily_summary'],audit,start_date,end_date,as_of_date,handled_only)+frequency_latex(frames['contact_day_frequency'],audit)
    write_text(analysis/'contact-table.tex',latex)
    if write_latex:publish_latex(latex)
    click.echo(display.to_string(index=False));click.echo(json.dumps(audit,indent=2));click.echo(f'Exports and SQL: {analysis}')


if __name__=='__main__':main()

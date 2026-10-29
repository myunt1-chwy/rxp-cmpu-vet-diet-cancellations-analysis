"""Same-pet/part reorders segmented by customer contact-day frequency."""
from datetime import date, datetime, timedelta, timezone
import hashlib
import json

import click
import duckdb
import pandas as pd

from src.python import create_opportunity_aged_customer_contacts as contacts
from src.python import create_opportunity_aged_reorders as reorders
from src.python import create_opportunity_order_cancellation_summary as base
from src.python.markdown_tables import markdown_table, write_text

ROOT=base.ROOT
VERIFY_SQL='''WITH contacting AS (
 SELECT customer_id,COUNT(DISTINCT FLOOR((epoch_ns(contact_time_sql)-epoch_ns(cancellation_time_sql))/86400000000000.0)) AS days_contacted
 FROM contact_details WHERE direction='inbound' AND contact_customer_id=customer_id
 AND contact_time_sql IS NOT NULL {handled_filter} GROUP BY customer_id
), cohort AS (SELECT DISTINCT customer_id FROM aged_orders), frequencies AS (
 SELECT c.customer_id,COALESCE(d.days_contacted,0) AS days_contacted
 FROM cohort c LEFT JOIN contacting d USING(customer_id)
), returners AS (
 SELECT DISTINCT original_customer_id AS customer_id FROM matches WHERE qualifying_non_cancelled
), segments AS (SELECT * FROM (VALUES (1),(2)) AS t(days_contacted))
SELECT s.days_contacted,COUNT(DISTINCT f.customer_id) AS segment_customers,
 COUNT(DISTINCT r.customer_id) AS reordered_customers
FROM segments s LEFT JOIN frequencies f USING(days_contacted)
LEFT JOIN returners r ON f.customer_id=r.customer_id
GROUP BY s.days_contacted ORDER BY s.days_contacted'''


def queries(start,end,as_of,days):
    return {'contacts':contacts.render_sql(start,end),
            'reorders':reorders.render_sql(start,end,as_of,days)}


def analyze(contact_source,reorder_source,start,end,as_of,days,handled_only=False):
    cf,contact_audit,_=contacts.analyze(contact_source,start,end,handled_only)
    raw=reorder_source.rename(columns=str.lower).copy()
    frozen=raw[reorders.KEYS+['original_customer_id','original_cancel_utc']].drop_duplicates().rename(
        columns={'original_customer_id':'customer_id','original_cancel_utc':'cancelled_at_utc'})
    for col in reorders.KEYS+['customer_id']:frozen[col]=frozen[col].map(base.identifier)
    frozen.cancelled_at_utc=pd.to_datetime(frozen.cancelled_at_utc,utc=True,format='mixed')
    if frozen.duplicated(reorders.KEYS).any():raise ValueError('conflicting aged membership')
    if not frozen.cancelled_at_utc.between(pd.Timestamp(start,tz='UTC'),pd.Timestamp(end,tz='UTC'),inclusive='left').all():
        raise ValueError('cancellations outside requested dates')
    cols=['order_id','customer_id','cancelled_at_utc']
    cohort=frozen.rename(columns={'original_order_id':'order_id'})[cols].drop_duplicates()
    cohort.cancelled_at_utc=cohort.cancelled_at_utc.astype('datetime64[ns, UTC]')
    pd.testing.assert_frame_equal(cohort.sort_values(cols).reset_index(drop=True),
        cf['aged_orders'][cols].sort_values(cols).reset_index(drop=True),check_dtype=False,
        obj='contact and reorder aged cohorts')
    rf,_=reorders.analyze(raw,frozen,days,as_of)
    matching=rf['matches'].loc[rf['matches'].qualifying_non_cancelled].copy()
    per_customer=cf['customer_contact_days'].merge(
        matching.groupby('original_customer_id').reorder_order_id.nunique().rename('reorder_orders'),
        left_on='customer_id',right_index=True,how='left',validate='one_to_one').fillna({'reorder_orders':0})
    per_customer.reorder_orders=per_customer.reorder_orders.astype('int64')
    per_customer['reordered']=per_customer.reorder_orders.gt(0)
    rows=[]
    for frequency in [1,2]:
        segment=per_customer.loc[per_customer.days_contacted.eq(frequency)]
        count=int(segment.reordered.sum());denominator=len(segment)
        rows.append(dict(days_contacted=frequency,segment_customers=denominator,reordered_customers=count,
            reordered_percentage=100*count/denominator if denominator else None))
    summary=pd.DataFrame(rows)
    verify=VERIFY_SQL.format(handled_filter='AND handled_flag=TRUE' if handled_only else '')
    detail=cf['contact_details'].copy()
    detail['contact_time_sql']=detail.contact_at_utc.dt.tz_localize(None)
    detail['cancellation_time_sql']=detail.cancelled_at_utc.dt.tz_localize(None)
    with duckdb.connect() as c:
        c.register('contact_details',detail);c.register('aged_orders',cf['aged_orders'])
        c.register('matches',rf['matches'][['original_customer_id','qualifying_non_cancelled']])
        expected=c.execute(verify).df()
    pd.testing.assert_frame_equal(summary.drop(columns='reordered_percentage'),expected,check_dtype=False)
    matches=matching.merge(per_customer[['customer_id','days_contacted']],left_on='original_customer_id',
        right_on='customer_id',validate='many_to_one')
    return dict(summary=summary,customer_results=per_customer,reorder_associations=matches),dict(
        contact_audit=contact_audit,reorder_audit=rf['summary'].set_index('measure')['count'].to_dict(),
        independent_verification='DuckDB independently matches both segment denominators and returning-customer counts'),verify


def latex_table(summary,start,end,as_of,days,handled_only):
    first=date.fromisoformat(start).strftime('%B %-d, %Y')
    last=(date.fromisoformat(end)-timedelta(days=1)).strftime('%B %-d, %Y')
    rows=[]
    for r in summary.itertuples():
        percentage='N/A' if pd.isna(r.reordered_percentage) else f'{r.reordered_percentage:.2f}'+r'\%'
        rows.append(f'{r.days_contacted} & {r.segment_customers:,} & {r.reordered_customers:,} & {percentage}'+r' \\')
    handled=r'Require \texttt{HANDLED\_FLAG=TRUE}.' if handled_only else 'Include handled, unhandled and unknown-handled inbound attempts.'
    return r"""
\subsubsection{Reorders by contact-day frequency}
Table~\ref{tab:contact-frequency-same-pet-part-reorders} applies the contact-day
frequency segments in Table~\ref{tab:aged-customer-contact-day-frequency}
to same-pet, same-product reorders.

\begin{table}[!htbp]
\centering
\caption{Same-pet, same-product-part-number reorders within """+str(days)+r""" days after aged cancellation, by customer contact-day frequency. Original CMPU vet-diet \texttt{CUSTOMER\_UPLOAD} orders were cancelled from """+first+' through '+last+r""", inclusive, UTC.}
\label{tab:contact-frequency-same-pet-part-reorders}
\begin{tabular}{@{}rrrr@{}}
\toprule
Days contacted & Segment customers & Customers reordered & Segment reordered (\%) \\
\midrule
"""+'\n'.join(rows)+r"""
\bottomrule
\end{tabular}

\begin{minipage}{\linewidth}
\footnotesize
\textit{Notes:} Segments count distinct relative 24-hour contact-day bins from
$-13$ through $+3$, pooled across each customer's qualifying aged orders.
Multiple contacts on the same relative day count as one day. Match inbound
contacts to the original aged order and its customer, across all categories.
"""+handled+r""" Reorders must match the customer, non-null \texttt{PET\_ID} and nonblank
\texttt{PRODUCT\_PART\_NUMBER}, on a different order placed strictly after
its matched aged cancellation through """+str(days)+r""" days inclusive. Apply the established
non-cancelled-order rules: exclude an entire reorder order if any line has
cancellation evidence or unknown status. Reorders may use any approval channel
or prescription source. Count each customer once in their segment if any
qualifying aged order has a matching reorder in its own follow-up window.
Percentages use all customers in the contact segment, including those missing
matching keys or without reorders; N/A denotes an empty segment. Contact-day
segments include post-cancellation contacts through day $+3$.
Observation cutoff: """+as_of+r""" 00:00 UTC.
\end{minipage}
\end{table}
"""


def publish_latex(text):
    appendix=ROOT/'src/latex/appendix';appendix.mkdir(parents=True,exist_ok=True)
    write_text(appendix/'contact_frequency_reorders.tex',text)
    parent=appendix/'contact_analysis.tex';include=r'\input{appendix/contact_frequency_reorders}'
    body=parent.read_text() if parent.exists() else r'\subsection{Contact Analysis}'+ '\n'
    if include not in body:write_text(parent,body.rstrip()+'\n\n'+include+'\n')


@click.command()
@click.option('--start-date',default='2026-05-01',show_default=True)
@click.option('--end-date',default='2026-08-01',show_default=True,help='Exclusive UTC aged cancellation end.')
@click.option('--as-of-date',default='2026-10-28',show_default=True)
@click.option('--followup-days',default=14,type=click.IntRange(min=1),show_default=True)
@click.option('--handled-only',is_flag=True)
@click.option('--write-latex',is_flag=True)
@click.option('--cached',is_flag=True)
@click.option('--print-sql',is_flag=True,help='Print the two independently executable extraction queries.')
def main(start_date,end_date,as_of_date,followup_days,handled_only,write_latex,cached,print_sql):
    params=base.parameters(start_date,end_date)
    if date.fromisoformat(as_of_date)<date.fromisoformat(end_date)+timedelta(days=max(followup_days,contacts.MAX_DAY+1)):
        raise click.ClickException('as-of must allow complete contact and reorder windows')
    sql=queries(start_date,end_date,as_of_date,followup_days)
    if print_sql:
        for name,query in sql.items():click.echo(f'-- {name}.sql (execute separately)\n{query.rstrip()};\n')
        return
    directory=ROOT/'data/opportunity/contact-frequency-reorders'/f'{start_date}_{end_date}_{followup_days}d_as-of-{as_of_date}'
    directory.mkdir(parents=True,exist_ok=True)
    manifest=directory/'source.json'
    identity=dict(version=1,**params,as_of_date=as_of_date,followup_days=followup_days,
        contact_days=[contacts.MIN_DAY,contacts.MAX_DAY],
        sql_sha256={name:hashlib.sha256(query.encode()).hexdigest() for name,query in sql.items()})
    if cached:
        meta=json.loads(manifest.read_text())
        if meta['identity']!=identity or any(meta['source_sha256'][n]!=base.digest(directory/f'{n}.parquet') for n in sql):
            raise click.ClickException('cache fingerprint differs; rerun fresh')
    else:
        manifest.unlink(missing_ok=True);engines={}
        for name,query in sql.items():
            source_dir=directory/name;source_dir.mkdir(exist_ok=True)
            write_text(source_dir/'query.sql',query+'\n')
            engines[name]=base.extract(source_dir/'query.sql',directory/f'{name}.parquet',source_dir)
        meta=dict(identity=identity,source_sha256={n:base.digest(directory/f'{n}.parquet') for n in sql},
            extracted_at_utc=datetime.now(timezone.utc).isoformat(),engines=engines)
    write_text(manifest,json.dumps(meta,indent=2)+'\n')
    frames,audit,verify=analyze(pd.read_parquet(directory/'contacts.parquet'),pd.read_parquet(directory/'reorders.parquet'),
        start_date,end_date,as_of_date,followup_days,handled_only)
    mode=directory/('handled-inbound' if handled_only else 'all-inbound');mode.mkdir(exist_ok=True)
    for name,frame in frames.items():frame.to_parquet(mode/(name.replace('_','-')+'.parquet'),index=False)
    write_text(mode/'verification.sql',verify+';\n')
    write_text(mode/'analysis.json',json.dumps(dict(source_sha256=meta['source_sha256'],audit=audit,
        exports={p.name:base.digest(p) for p in mode.glob('*.parquet')}),indent=2)+'\n')
    tables=ROOT/'outputs/tables/opportunity'/f'{start_date}_{date.fromisoformat(end_date)-timedelta(days=1)}'
    tables.mkdir(parents=True,exist_ok=True)
    shown=frames['summary'].rename(columns={'days_contacted':'Days contacted','segment_customers':'Segment customers',
        'reordered_customers':'Customers reordered','reordered_percentage':'Segment reordered (%)'}).copy()
    shown['Segment reordered (%)']=shown['Segment reordered (%)'].map(lambda n:'N/A' if pd.isna(n) else f'{n:.2f}%')
    note=(f'CMPU vet-diet CUSTOMER_UPLOAD aged cancellations [{start_date}, {end_date}) UTC; as of {as_of_date} 00:00 UTC. '
        'Segments use distinct relative 24-hour contact-day bins -13 through +3 across all aged orders per customer, not contact legs or sessions. '
        'Require inbound SESSION_INITIAL_DIRECTION, matching contact ORDER_ID and customer ID, all contact categories. '
        +('HANDLED_FLAG=TRUE only. ' if handled_only else 'Handled, unhandled and unknown-handled inbound attempts included. ')+
        f'Reorders match exact customer, non-null PET_ID and nonblank PRODUCT_PART_NUMBER, on a different order placed strictly after its matched aged cancellation through {followup_days} days inclusive. '
        'Exclude an entire reorder order if any line has cancellation evidence or unknown status; same established follow-up rules, any approval channel/source. '
        'A customer returns if any qualifying aged order has a matching non-cancelled reorder in its own window. Count each customer once per segment, pooling multiple pets/products/orders. '
        'Denominator is the entire contact-frequency segment, including customers missing match keys or without reorders; N/A denotes an empty segment. '
        'Frequency includes contacts through day +3, so these descriptive segments include post-cancellation information.\n\n')
    suffix='-handled-only' if handled_only else ''
    write_text(tables/f'contact-frequency-{followup_days}d-same-pet-part-reorders{suffix}.md',
        '# Same-pet/part reorders by contact-day frequency\n\n'+note+markdown_table(shown)+'\n')
    latex=latex_table(frames['summary'],start_date,end_date,as_of_date,followup_days,handled_only)
    write_text(mode/'reorder-table.tex',latex)
    if write_latex:publish_latex(latex)
    click.echo(shown.to_string(index=False));click.echo(f'Data and SQL: {directory}')


if __name__=='__main__':main()

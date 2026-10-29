"""Follow-up purchases after a first observed vet-diet or CUSTOMER_UPLOAD aged order."""
from datetime import date, datetime, timedelta, timezone
import hashlib
import json
import subprocess
import sys

import click
from jinja2 import Environment, StrictUndefined
import pandas as pd

from src.python import create_opportunity_aged_first_order_customers as first
from src.python import create_opportunity_aged_reorders as reorders
from src.python import create_opportunity_order_cancellation_summary as base
from src.python.markdown_tables import markdown_table, write_text
from src.python import opportunity_report_tables as report_tables

ROOT=base.ROOT
HORIZONS=list(range(7,71,7))
SCOPE='vet-diet-customer-upload'
STUDY_LABELS={'same-part-pet':'Same-pet, same-product',
              'same-pet-different-part':'Same-pet, different-product vet-diet',
              'any-vet-diet':'Any vet-diet', 'any-chewy':'All-Chewy'}
STUDY_TABLE_LABELS={'same-part-pet':'tab:financial-opportunity-new-upload-follow-up',
                    'same-pet-different-part':'tab:financial-opportunity-new-upload-same-pet-different-part',
                    'any-vet-diet':'tab:financial-opportunity-new-upload-any-vet-diet',
                    'any-chewy':'tab:financial-opportunity-new-upload-all-chewy'}


def render_sql(start,end,as_of,all_studies=False,all_chewy=False,cohort_kind="first-upload"):
    template="opportunity_new_upload_customer_chewy_follow_up.sql" if all_chewy else "opportunity_new_upload_customer_follow_up.sql"
    if cohort_kind=="first-vet-diet":template=template.replace("new_upload", "new_vet_diet")
    return Environment(undefined=StrictUndefined).from_string(
        (ROOT/'src/sql'/template).read_text()).render(
            **base.parameters(start,end),as_of_date=as_of,followup_days=max(HORIZONS),all_studies=all_studies)


def load_cohort(start,end,cached,cohort_kind="first-upload"):
    scope="vet-diet" if cohort_kind=="first-vet-diet" else SCOPE
    directory=ROOT/'data/opportunity'/first.SCOPE_FOLDERS[scope]/f'{start}_{end}'
    manifest=directory/'analysis.json'
    if not manifest.exists():
        if cached:raise click.ClickException('Missing first-order customer cohort; run without CACHED=1 first')
        subprocess.run([sys.executable,'-m','src.python.create_opportunity_aged_first_order_customers',
            '--scope',scope,'--start-date',start,'--end-date',end],cwd=ROOT,check=True)
    meta=json.loads(manifest.read_text())
    expected=first.source_identity(base.parameters(start,end),first.render_sql(start,end,scope),scope)
    if meta['identity']!=expected or meta['source_sha256']!=base.digest(directory/'source.parquet'):
        raise click.ClickException('First-order customer cohort fingerprint differs; regenerate its target')
    loaded={}
    for name in ['orders','lines','customers']:
        path=directory/(name+'.parquet')
        if base.digest(path)!=meta['exports'][path.name]:raise ValueError('cohort export fingerprint differs')
        loaded[name]=pd.read_parquet(path)
    anchors=loaded['orders'].loc[loaded['orders'].status.eq(first.SCOPE_LABELS[scope]),['order_id','customer_id']].copy()
    expected_customers=set(loaded['customers'].loc[loaded['customers'].any_new,'customer_id'])
    if set(anchors.customer_id)!=expected_customers or anchors.customer_id.duplicated().any() or anchors.order_id.duplicated().any():
        raise ValueError('first-order anchor membership differs from new-customer cohort')
    lines=loaded['lines'].merge(anchors,on=['order_id','customer_id'],validate='many_to_one')
    frozen=lines[['order_id','order_line_id','customer_id','cancelled_at_utc']].rename(columns={
        'order_id':'original_order_id','order_line_id':'original_line_id'})
    for col in reorders.KEYS+['customer_id']:frozen[col]=frozen[col].map(base.identifier)
    frozen['cancelled_at_utc']=pd.to_datetime(frozen.cancelled_at_utc,utc=True)
    if frozen.duplicated(reorders.KEYS).any():raise ValueError('duplicate frozen anchor lines')
    fingerprints=dict(cohort_source_sha256=meta['source_sha256'],cohort_exports={name+'.parquet':meta['exports'][name+'.parquet'] for name in loaded})
    return anchors,frozen,fingerprints


def analyze_windows(raw,frozen,anchors,as_of,study="same-part-pet",broad_source=False):
    rows=[];exports={};prior_customers=set();prior_orders=set();prior_lines=set()
    cohort_ids=set(anchors.customer_id)
    if set(frozen.customer_id)!=cohort_ids:raise ValueError('anchor/customer membership differs')
    for days in HORIZONS:
        results,sales=reorders.analyze(raw,frozen,days,as_of,source_days=max(HORIZONS),study=study,broad_source=broad_source)
        measures=results['summary'].set_index('measure')['count']
        r=results['reorders'];orders=set(r.reorder_order_id);customers=set(r.original_customer_id)
        line_keys=set(map(tuple,r[reorders.REORDER_KEYS].to_numpy()))
        if not (prior_customers<=customers<=cohort_ids and prior_orders<=orders and prior_lines<=line_keys):
            raise ValueError('follow-up populations do not nest')
        prior_customers,prior_orders,prior_lines=customers,orders,line_keys
        if int(measures['aged_customers'])!=len(cohort_ids):raise ValueError('follow-up cohort count differs')
        outcomes=anchors.copy()
        counts=r.groupby('reorder_customer_id').reorder_order_id.nunique().rename('qualifying_orders')
        outcomes=outcomes.merge(counts,left_on='customer_id',right_index=True,how='left')
        outcomes['qualifying_orders']=outcomes.qualifying_orders.fillna(0).astype(int)
        outcomes['returned']=outcomes.qualifying_orders.gt(0)
        if int(outcomes.returned.sum())!=len(customers) or int(outcomes.qualifying_orders.sum())!=len(orders):
            raise ValueError('customer outcomes do not reconcile')
        eligible=int(measures['eligible_aged_customers']);denominator=len(cohort_ids)
        rows.append(dict(followup_days=days,cohort_customers=denominator,eligible_customers=eligible,
            returning_customers=len(customers),return_percentage=100*len(customers)/denominator if denominator else None,
            customers_without_reorder=denominator-len(customers),orders=len(orders),matching_lines=len(r),
            actual_net_sales=base.money(sales['matching_line_net_sales']),known_net_sales=base.money(sales['known_matching_line_net_sales']),
            missing_sales_records=int(measures['missing_sales_records'])))
        exports.update({f'{days}d-{name}':frame for name,frame in results.items()})
        exports[f'{days}d-customer-outcomes']=outcomes
    return pd.DataFrame(rows),exports


def latex_table(summary,start,end,as_of,study="same-part-pet",cohort_kind="first-upload"):
    denominator=int(summary.iloc[-1].cohort_customers)
    first_day=date.fromisoformat(start).strftime('%B %-d, %Y')
    last_day=(date.fromisoformat(end)-timedelta(days=1)).strftime('%B %-d, %Y')
    rows=[]
    for r in summary.itertuples():
        percentage='N/A' if pd.isna(r.return_percentage) else f'{r.return_percentage:.2f}'+r'\%'
        sales='Incomplete' if pd.isna(r.actual_net_sales) else f'{r.actual_net_sales:,.2f}'
        rows.append(f'{r.followup_days} & {r.returning_customers:,} & {percentage} & {r.orders:,} & {sales}'+r' \\')
    text=r"""\clearpage
\subsubsection{Follow-up for first CUSTOMER\_UPLOAD vet-diet customers}
Table~\ref{tab:financial-opportunity-new-upload-follow-up} follows the
"""+f'{denominator:,}'+r""" customers whose first observed vet-diet
\texttt{CUSTOMER\_UPLOAD} order was an aged order. Original CMPU vet-diet
\texttt{CUSTOMER\_UPLOAD} aged cancellations occurred from
"""+first_day+' through '+last_day+r""", inclusive, UTC.

\begin{table}[!htbp]
\centering
\caption{Same-pet, same-product non-cancelled reorders after cancellation of a first CUSTOMER\_UPLOAD vet-diet aged order: cumulative customers, percentage of the fixed cohort, orders and matching-line net sales through 70 days.}
\label{tab:financial-opportunity-new-upload-follow-up}
\begin{tabular}{@{}rrrrr@{}}
\toprule
Follow-up (days) & Customers & Cohort (\%) & Orders & Net sales \\
\midrule
"""+'\n'.join(rows)+r"""
\bottomrule
\end{tabular}

\begin{minipage}{\linewidth}
\footnotesize
\textit{Notes:} Each customer's first qualifying aged order is the sole anchor;
later aged orders do not reset follow-up. Follow-up begins strictly after that
order's cancellation and includes the indicated day limit. Require the same
numeric customer ID, exact \texttt{PRODUCT\_PART\_NUMBER} and non-null
\texttt{PET\_ID}. Later orders may use any approval channel or prescription
source. Exclude the whole later order if any line is cancelled or has unknown
status. Count each customer, order and physical line once within each window,
regardless of multiple original lines or shipments. Every percentage uses the
same fixed denominator of """+f'{denominator:,}'+r""" customers, including those with no
qualifying reorder. All windows require complete follow-up through
"""+as_of+r""" 00:00 UTC; windows and studies overlap and should not be added.
The cohort uses exact earliest observed order IDs in linked prescription and
ECOM history, across all historical prescription sources, with current
prescription approval-channel snapshots. Original eligibility is CMPU,
vet diet and \texttt{CUSTOMER\_UPLOAD}. Current extraction statuses determine
non-cancellation. Net sales sum \texttt{ORDER\_LINE\_NET\_SALES} on matching
lines, once per shipment/line contribution; missing sales make totals incomplete.
Sales are recorded matching-line amounts, not proof of recovered revenue.
Amounts display two decimals; exports retain five.
\end{minipage}
\end{table}
"""


    if study!='same-part-pet':
        text=text.replace('tab:financial-opportunity-new-upload-follow-up',STUDY_TABLE_LABELS[study])
        text=text.replace('Follow-up for first CUSTOMER'+r'\_UPLOAD vet-diet customers',STUDY_LABELS[study]+' follow-up for first upload customers')
        text=text.replace('Same-pet, same-product non-cancelled reorders',STUDY_LABELS[study]+' non-cancelled reorders')
        matching=r"""Require the same
numeric customer ID, exact \texttt{PRODUCT\_PART\_NUMBER} and non-null
\texttt{PET\_ID}."""
        if study=='same-pet-different-part':
            note=r'Require the same numeric customer ID and non-null \texttt{PET\_ID}, a different nonblank \texttt{PRODUCT\_PART\_NUMBER} from the anchor line, and a TRUE vet-diet flag on the later line.'
        elif study=='any-vet-diet':
            note='Require the same numeric customer ID and a TRUE vet-diet flag on the later line, for any pet and product part number.'
        else:
            note='Require the same numeric customer ID; include all Chewy product categories and any pet/product, with no later prescription, approval-channel or source restriction.'
            text=text.replace(r'\texttt{ORDER\_LINE\_NET\_SALES}',r'\texttt{NET\_SALES} from \texttt{EDLDB.ECOM.ORDER\_LINE}')
            text=text.replace('once per shipment/line contribution;', 'once per physical order line;')
            text=text.replace('exports retain five.', 'ECOM supplies four decimals, retained exactly in five-decimal exports.')
        text=text.replace(matching,note)

    if cohort_kind=='first-vet-diet':
        text=text.replace('tab:financial-opportunity-new-upload','tab:financial-opportunity-new-vet-diet')
        text=text.replace('was an aged order. Original CMPU vet-diet','was an aged order.\n\nOriginal CMPU vet-diet')
        text=text.replace(r'first CUSTOMER\_UPLOAD vet-diet', 'first vet-diet').replace('first upload customers','first vet-diet customers')
        text=text.replace('first observed vet-diet\n'+r'\texttt{CUSTOMER\_UPLOAD} order','first observed vet-diet order')
        text=text.replace('The cohort uses exact earliest observed order IDs in linked prescription and\nECOM history, across all historical prescription sources, with current\nprescription approval-channel snapshots.',
            'The cohort uses earliest observed vet-diet order IDs across all historical approval channels and prescription sources, identified from RxP vet-diet lines and ECOM order history.')
    return text


def publish_latex(text,all_chewy=False,tables=None,cohort_kind="first-upload"):
    appendix=ROOT/'src/latex/appendix';appendix.mkdir(parents=True,exist_ok=True)
    filename='financial_opportunity_new_upload_chewy_follow_up.tex' if all_chewy else 'financial_opportunity_new_upload_follow_up.tex'
    if cohort_kind=='first-vet-diet':filename=filename.replace('new_upload','new_vet_diet')
    write_text(appendix/filename,text)
    if not all_chewy:
        fragments=report_tables.VET_FILES if cohort_kind=='first-vet-diet' else report_tables.UPLOAD_FILES
        for study,fragment in (tables or {}).items():write_text(appendix/(fragments[study]+'.tex'),fragment)
    report_tables.update_follow_up_inputs(appendix/'financial_opportunity.tex')


@click.command()
@click.option('--start-date',default='2026-05-01',show_default=True)
@click.option('--end-date',default='2026-08-01',show_default=True,help='Exclusive UTC aged cancellation end.')
@click.option('--as-of-date',default='2026-10-28',show_default=True)
@click.option('--cohort','cohort_kind',type=click.Choice(['first-upload','first-vet-diet']),default='first-upload')
@click.option('--all-studies',is_flag=True,help='All three RxP follow-up studies from one extract.')
@click.option('--study',type=click.Choice(list(STUDY_LABELS)),default='same-part-pet')
@click.option('--write-latex',is_flag=True)
@click.option('--cached',is_flag=True)
@click.option('--print-sql',is_flag=True)
def main(start_date,end_date,as_of_date,cohort_kind,all_studies,study,write_latex,cached,print_sql):
    if all_studies and study!="same-part-pet":raise click.UsageError("--all-studies uses the three RxP studies; use --study separately")
    all_chewy=study=="any-chewy"
    studies=reorders.STUDIES if all_studies else [study]
    params=base.parameters(start_date,end_date)
    if date.fromisoformat(as_of_date)<date.fromisoformat(end_date)+timedelta(days=max(HORIZONS)):
        raise click.ClickException('as-of must allow complete 70-day follow-up for every cancellation')
    sql=render_sql(start_date,end_date,as_of_date,all_studies=all_studies or study in ['same-pet-different-part','any-vet-diet'],all_chewy=all_chewy,cohort_kind=cohort_kind)
    if print_sql:click.echo(sql);return
    anchors,frozen,cohort=load_cohort(start_date,end_date,cached,cohort_kind)
    root_name='new-upload-customer-follow-up-studies' if all_studies else ('new-upload-customer-follow-up-chewy' if all_chewy else ('new-upload-customer-follow-up' if study=='same-part-pet' else 'new-upload-customer-follow-up-'+study))
    if cohort_kind=='first-vet-diet':root_name=root_name.replace('new-upload','new-vet-diet')
    directory=ROOT/'data/opportunity'/root_name/f'{start_date}_{end_date}_7d-70d_as-of-{as_of_date}'
    directory.mkdir(parents=True,exist_ok=True);source=directory/'source.parquet';manifest=directory/'analysis.json'
    identity=dict(version=1,**params,as_of_date=as_of_date,horizons=HORIZONS,anchor='first observed CUSTOMER_UPLOAD vet-diet aged order cancellation',
        sql_sha256=hashlib.sha256(sql.encode()).hexdigest(),**cohort)
    if cohort_kind=='first-vet-diet':identity.update(cohort_kind=cohort_kind,anchor='first observed vet-diet aged order cancellation')
    if all_studies or study!='same-part-pet':identity['studies']=studies
    if cached:
        meta=json.loads(manifest.read_text())
        if meta['identity']!=identity or meta['source_sha256']!=base.digest(source):raise click.ClickException('cache fingerprint differs; rerun fresh')
    else:
        write_text(directory/'query.sql',sql);engine=base.extract(directory/'query.sql',source,directory)
        meta=dict(identity=identity,source_sha256=base.digest(source),extracted_at_utc=datetime.now(timezone.utc).isoformat(),**engine)
    raw=pd.read_parquet(source).rename(columns=str.lower)
    if all_chewy and raw.candidate_missing_line_keys.fillna(0).gt(0).any():raise ValueError('ECOM candidate lines have missing identifiers')
    combined=[];exports={};summaries={}
    for scope in studies:
        part,details=analyze_windows(raw,frozen,anchors,as_of_date,study=scope,broad_source=all_studies or study!='same-part-pet')
        summaries[scope]=part.copy()
        if all_studies:part.insert(0,'study',scope)
        combined.append(part)
        prefix=scope+'-' if all_studies else ''
        exports.update({prefix+name:frame for name,frame in details.items()})
    summary=pd.concat(combined,ignore_index=True)
    if all_studies:
        for days in HORIZONS:
            narrow=exports[f'same-pet-different-part-{days}d-reorders']
            broad=exports[f'any-vet-diet-{days}d-reorders']
            if not set(map(tuple,narrow[reorders.REORDER_KEYS].to_numpy()))<=set(map(tuple,broad[reorders.REORDER_KEYS].to_numpy())):raise ValueError('different-part study is not a subset of any-vet-diet')
    anchors.to_parquet(directory/'cohort-customers.parquet',index=False);frozen.to_parquet(directory/'anchor-lines.parquet',index=False)
    for name,frame in exports.items():frame.to_parquet(directory/(name+'.parquet'),index=False)
    base.write_parquet(summary,directory/'summary.parquet')
    audit=dict(cohort_customers=len(anchors),anchor_orders=anchors.order_id.nunique(),anchor_lines=len(frozen),
        studies=studies,all_windows=HORIZONS,independent_verification='Existing DuckDB distinct counts and exact-decimal sales verification for each horizon; frozen first-order/customer/cancellation membership and nested populations verified; zero-inclusive customer outcomes reconcile to totals')
    write_text(directory/'audit.json',json.dumps(audit,indent=2)+'\n')
    if all_chewy:meta['source_definition']=dict(table='EDLDB.ECOM.ORDER_LINE',net_sales_field='NET_SALES',grain='physical order line',native_scale=4)
    meta.update(audit=audit,exports={p.name:base.digest(p) for p in directory.glob('*.parquet') if p!=source})
    write_text(manifest,json.dumps(meta,indent=2)+'\n')
    tables=ROOT/'outputs/tables/opportunity'/f'{start_date}_{date.fromisoformat(end_date)-timedelta(days=1)}';tables.mkdir(parents=True,exist_ok=True)
    shown=summary[(['study'] if all_studies else [])+['followup_days','cohort_customers','returning_customers','return_percentage','orders','actual_net_sales']].copy()
    shown.return_percentage=shown.return_percentage.map(lambda v:'N/A' if pd.isna(v) else f'{v:.2f}%')
    shown.actual_net_sales=shown.actual_net_sales.map(lambda v:'Incomplete' if pd.isna(v) else f'{v:,.2f}')
    text=(f'# First CUSTOMER_UPLOAD vet-diet customers: same-pet/product follow-up\n\nOriginal CMPU vet-diet CUSTOMER_UPLOAD aged cancellations [{start_date}, {end_date}) UTC; '
          f'as of {as_of_date} 00:00 UTC. Cohort: {len(anchors):,} customers whose first observed CUSTOMER_UPLOAD vet-diet order was an aged order. '
          'Only that first aged order anchors each customer, including every qualifying line on it; subsequent aged orders do not reset follow-up. '
          'Count new orders placed strictly after cancellation through each horizon inclusive, matching the same customer, exact PRODUCT_PART_NUMBER and non-null PET_ID. '
          'Later prescriptions may use any approval channel or prescription source. Exclude the whole later order if any line is cancelled or has unknown status. '
          'Customers/orders/physical lines count once per window despite multiple original lines or shipments. Percentages use the full fixed cohort denominator, including zero-return customers and customers without usable matching keys; eligibility is audited separately. '
          'All windows require complete follow-up and overlap. Source statuses reflect the extraction snapshot. Sum ORDER_LINE_NET_SALES once per distinct shipment/line contribution on matching lines, preserving zero/negative values; missing sales make totals incomplete. '
          'First-customer status is based on observed linked prescription and ECOM history, with current prescription-channel snapshots, not guaranteed complete lifetime history.\n\n'+markdown_table(shown)+'\n')
    if all_studies:
        text=text.replace('same-pet/product follow-up','vet-diet follow-up studies').replace('matching the same customer, exact PRODUCT_PART_NUMBER and non-null PET_ID.', 'using the study-specific matching rules: same-part-pet matches exact pet and part; same-pet-different-part requires the same pet, a different nonblank part and vet-diet TRUE; any-vet-diet requires vet-diet TRUE for any pet/part. Studies overlap and must not be summed.')
    elif all_chewy:
        text=text.replace('same-pet/product follow-up','all-Chewy follow-up').replace('matching the same customer, exact PRODUCT_PART_NUMBER and non-null PET_ID.', 'matching the same customer across all Chewy categories, with no later pet, product, vet-diet or prescription restriction.').replace('Sum ORDER_LINE_NET_SALES once per distinct shipment/line contribution on matching lines', 'Sum ECOM.ORDER_LINE.NET_SALES once per physical order line (native four-decimal amounts, retained exactly in five-decimal exports)')
    suffix='all-studies' if all_studies else ('all-chewy' if all_chewy else study)
    prefix='new-vet-diet-customers' if cohort_kind=='first-vet-diet' else 'new-upload-customers'
    if cohort_kind=='first-vet-diet':
        text=text.replace('# First CUSTOMER_UPLOAD vet-diet customers','# First vet-diet customers').replace('whose first observed CUSTOMER_UPLOAD vet-diet order was an aged order.', 'whose first observed vet-diet order across all historical approval channels and prescription sources was an aged order.').replace('First-customer status is based on observed linked prescription and ECOM history, with current prescription-channel snapshots, not guaranteed complete lifetime history.', 'First-customer status is based on observed RxP vet-diet lines and ECOM history, not guaranteed complete lifetime history.')
    write_text(tables/f'{prefix}-{suffix}-follow-up.md',text)
    study_tables={scope:latex_table(summaries[scope],start_date,end_date,as_of_date,scope,cohort_kind) for scope in studies}
    latex='\n'.join(study_tables.values())
    write_text(directory/'follow-up-table.tex',latex)
    if write_latex:publish_latex(latex,all_chewy=all_chewy,tables=study_tables,cohort_kind=cohort_kind)
    click.echo(summary.to_string(index=False));click.echo(f'Exports and SQL: {directory}')


if __name__=='__main__':main()

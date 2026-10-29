"""Classify the aged cohort by exact first order IDs in full ECOM order history."""
from datetime import datetime, timezone, date, timedelta
import hashlib
import json

import click
import duckdb
from jinja2 import Environment, StrictUndefined
import pandas as pd

from src.python import create_opportunity_order_cancellation_summary as base
from src.python.markdown_tables import markdown_table, write_text

ROOT=base.ROOT
KEYS=['order_id','order_line_id']
STATUSES=['First order in observed ECOM history','Existing customer','Unknown']
SCOPE_LABELS={'chewy':STATUSES[0],'vet-diet':'First order in observed vet-diet history',
              'vet-diet-customer-upload':'First observed CUSTOMER_UPLOAD vet-diet order'}
SCOPE_FOLDERS={'chewy':'aged-first-order-customers','vet-diet':'aged-first-vet-diet-order-customers',
               'vet-diet-customer-upload':'aged-first-customer-upload-vet-diet-order-customers'}
SCOPE_TEMPLATES={'chewy':'opportunity_aged_first_order_customers.sql',
                 'vet-diet':'opportunity_aged_first_vet_diet_order_customers.sql',
                 'vet-diet-customer-upload':'opportunity_aged_first_customer_upload_vet_diet_order_customers.sql'}
VERIFY_SQL="""WITH classified AS (
 SELECT order_id,customer_id,CASE
 WHEN ecom_aged_customer_id IS NULL OR ecom_aged_placed_at_utc IS NULL OR first_placed_at_utc IS NULL THEN 'Unknown'
 WHEN first_placed_at_utc<ecom_aged_placed_at_utc THEN 'Existing customer'
 WHEN order_id=first_order_id AND earliest_timestamp_ties=1 AND history_orders_missing_placement=0
 THEN 'First order in observed ECOM history' ELSE 'Unknown' END AS status FROM orders
), customers AS (
 SELECT customer_id,CASE WHEN COUNT(*) FILTER (WHERE status='First order in observed ECOM history')>0 THEN 'First order in observed ECOM history'
 WHEN COUNT(*) FILTER (WHERE status='Unknown')>0 THEN 'Unknown' ELSE 'Existing customer' END AS status
 FROM classified GROUP BY customer_id
) SELECT 'order' AS grain,order_id AS id,status FROM classified
UNION ALL SELECT 'customer',customer_id,status FROM customers"""


def render_sql(start,end,scope="chewy"):
    return Environment(undefined=StrictUndefined).from_string(
        (ROOT/'src/sql'/SCOPE_TEMPLATES[scope]).read_text()).render(**base.parameters(start,end))


def source_identity(params,sql,scope="chewy"):
    identity=dict(version=1,**params,definition='exact earliest placed ECOM order ID; all statuses',timezone='UTC',sql_sha256=hashlib.sha256(sql.encode()).hexdigest())
    if scope=='vet-diet':identity.update(scope=scope,definition='exact earliest placed vet-diet ECOM order ID; all statuses')
    if scope=='vet-diet-customer-upload':identity.update(scope=scope,definition='exact earliest placed CUSTOMER_UPLOAD vet-diet order ID; all prescription sources and statuses')
    return identity


def analyze(raw,start,end,scope="chewy"):
    statuses=STATUSES.copy()
    statuses[0]=SCOPE_LABELS[scope]
    f=raw.rename(columns=str.lower).copy()
    for col in KEYS+['customer_id','ecom_aged_customer_id','first_order_id','flagged_first_order_id']:
        f[col]=f[col].map(base.identifier)
    if f[KEYS+['customer_id']].isna().any().any():raise ValueError('missing aged cohort keys')
    for col in ['placed_at_utc','cancelled_at_utc','ecom_aged_placed_at_utc','first_placed_at_utc']:
        f[col]=pd.to_datetime(f[col],utc=True,format='mixed')
    if 'history_prescription_variants' not in f:f['history_prescription_variants']=1
    for col in ['registry_variants','history_source_variants','aged_order_source_variants','history_prescription_variants']:
        if f[col].dropna().ne(1).any():raise ValueError('conflicting source '+col)
    if not f.cancelled_at_utc.between(pd.Timestamp(start,tz='UTC'),pd.Timestamp(end,tz='UTC'),inclusive='left').all():
        raise ValueError('aged cancellation outside requested dates')
    if (f.ecom_aged_customer_id.notna() & f.ecom_aged_customer_id.ne(f.customer_id)).any():raise ValueError('ECOM aged customer differs')
    if 'vet_orders_missing_ecom_header' not in f:f['vet_orders_missing_ecom_header']=0
    per_order=[c for c in f if c not in KEYS+['cancelled_at_utc']]
    if f.groupby('order_id')[per_order].nunique(dropna=False).gt(1).any().any():raise ValueError('conflicting aged order values')
    if f.groupby(KEYS).cancelled_at_utc.nunique(dropna=False).gt(1).any():raise ValueError('conflicting aged line values')
    customer_columns=['history_prescription_variants','vet_orders_missing_ecom_header','history_identical_duplicate_rows','history_orders','history_orders_missing_placement','history_source_variants','first_order_id',
                      'first_placed_at_utc','earliest_timestamp_ties','flagged_first_orders','flagged_first_order_id']
    if f.groupby('customer_id')[customer_columns].nunique(dropna=False).gt(1).any().any():raise ValueError('conflicting customer history')
    lines=f.drop_duplicates(KEYS).copy()
    orders=lines.drop(columns=['order_line_id','cancelled_at_utc']).drop_duplicates('order_id').copy()
    orders=orders.merge(lines.groupby('order_id').size().rename('qualifying_lines'),on='order_id')
    valid=orders.ecom_aged_customer_id.notna() & orders.ecom_aged_placed_at_utc.notna() & orders.first_placed_at_utc.notna()
    orders['status']='Unknown'
    orders.loc[valid & orders.first_placed_at_utc.lt(orders.ecom_aged_placed_at_utc),'status']='Existing customer'
    new=(valid & orders.order_id.eq(orders.first_order_id) & orders.earliest_timestamp_ties.eq(1) & orders.history_orders_missing_placement.eq(0) & orders.vet_orders_missing_ecom_header.eq(0))
    orders.loc[new,'status']=statuses[0]
    orders['quality_flag']=''
    orders.loc[orders.history_orders_missing_placement.gt(0),'quality_flag']='history contains missing placement timestamps'
    orders.loc[orders.vet_orders_missing_ecom_header.gt(0),'quality_flag']='vet-diet orders have missing ECOM headers'
    orders.loc[orders.earliest_timestamp_ties.gt(1),'quality_flag']='multiple orders tied for earliest timestamp'
    orders.loc[~valid,'quality_flag']='missing aged order or first order history/timestamp'
    customers=orders.groupby('customer_id').agg(aged_orders=('order_id','nunique'),any_new=('status',lambda s:s.eq(statuses[0]).any()),
        any_unknown=('status',lambda s:s.eq('Unknown').any()),any_flagged_aged_order=('aged_order_first_placed_flag',lambda s:s.eq(True).any())).reset_index()
    for col in ['any_new','any_unknown','any_flagged_aged_order']:customers[col]=customers[col].astype(bool)
    customers['status']='Existing customer';customers.loc[customers.any_unknown,'status']='Unknown';customers.loc[customers.any_new,'status']=statuses[0]
    customers=customers.merge(orders[['customer_id']+customer_columns].drop_duplicates('customer_id'),on='customer_id')
    with duckdb.connect() as c:
        c.execute("SET TimeZone='UTC'");c.register('orders',orders)
        verification=VERIFY_SQL.replace(STATUSES[0],statuses[0]).replace('history_orders_missing_placement=0','history_orders_missing_placement=0 AND vet_orders_missing_ecom_header=0')
        independent=c.execute(verification).df()
    for grain,frame,key in [('order',orders,'order_id'),('customer',customers,'customer_id')]:
        if independent.loc[independent.grain.eq(grain)].set_index('id').status.to_dict()!=frame.set_index(key).status.to_dict():
            raise ValueError('independent classification differs')
    summaries={}
    for name,frame,label in [('customer_summary',customers,'customers'),('order_summary',orders,'orders')]:
        counts=frame.status.value_counts().reindex(statuses,fill_value=0)
        table=pd.DataFrame({'status':statuses,label:counts.values})
        table['percentage']=table[label].div(len(frame)).mul(100) if len(frame) else float('nan')
        summaries[name]=pd.concat([table,pd.DataFrame([dict(status='TOTAL',**{label:len(frame)},percentage=100.0 if len(frame) else None)])],ignore_index=True)
    audit=dict(aged_customers=len(customers),aged_orders=len(orders),aged_lines=len(lines),identical_aged_source_duplicates_collapsed=int(f.duplicated(KEYS).sum()),
        identical_history_duplicates_collapsed=int(customers.history_identical_duplicate_rows.sum()),
        customers_earliest_timestamp_ties=int(customers.earliest_timestamp_ties.gt(1).sum()),
        customers_missing_vet_order_headers=int(customers.vet_orders_missing_ecom_header.gt(0).sum()),
        customers_missing_history_timestamps=int(customers.history_orders_missing_placement.gt(0).sum()),
        aged_orders_missing_ecom_record=int(orders.ecom_aged_customer_id.isna().sum()),
        aged_order_placement_source_differences=int((orders.ecom_aged_placed_at_utc.notna() & orders.placed_at_utc.ne(orders.ecom_aged_placed_at_utc)).sum()),
        customers_with_flagged_first_aged_order=int(customers.any_flagged_aged_order.sum()),
        aged_orders_flagged_first=int(orders.aged_order_first_placed_flag.eq(True).sum()),
        customers_with_multiple_flagged_first_orders=int(customers.flagged_first_orders.gt(1).sum()),
        customers_chronological_new_but_not_flagged=int((customers.any_new & ~customers.any_flagged_aged_order).sum()),
        customers_flagged_new_but_not_chronological=int((~customers.any_new & customers.any_flagged_aged_order).sum()),
        independent_verification='DuckDB verifies every order and customer classification')
    return dict(lines=lines,orders=orders,customers=customers,**summaries),audit


@click.command()
@click.option('--start-date',default='2026-05-01',show_default=True)
@click.option('--end-date',default='2026-08-01',show_default=True,help='Exclusive UTC cancellation end.')
@click.option('--scope',type=click.Choice(list(SCOPE_LABELS)),default='chewy',show_default=True)
@click.option('--cached',is_flag=True)
@click.option('--print-sql',is_flag=True)
def main(start_date,end_date,scope,cached,print_sql):
    params=base.parameters(start_date,end_date);sql=render_sql(start_date,end_date,scope)
    if print_sql:click.echo(sql);return
    root_name=SCOPE_FOLDERS[scope]
    directory=ROOT/'data/opportunity'/root_name/f'{start_date}_{end_date}'
    directory.mkdir(parents=True,exist_ok=True);source=directory/'source.parquet';manifest=directory/'analysis.json'
    identity=source_identity(params,sql,scope)
    if cached:
        meta=json.loads(manifest.read_text())
        if meta['identity']!=identity or meta['source_sha256']!=base.digest(source):raise click.ClickException('cache fingerprint differs; rerun fresh')
    else:
        write_text(directory/'query.sql',sql);engine=base.extract(directory/'query.sql',source,directory)
        meta=dict(identity=identity,source_sha256=base.digest(source),extracted_at_utc=datetime.now(timezone.utc).isoformat(),**engine)
    frames,audit=analyze(pd.read_parquet(source),start_date,end_date,scope)
    previous=ROOT/'data/opportunity/aged-new-customers'/f'{start_date}_{end_date}'/'customers.parquet'
    if previous.exists() and scope=='chewy':
        old=pd.read_parquet(previous)[['customer_id','status']].rename(columns={'status':'same_day_status'})
        comparison=frames['customers'][['customer_id','status']].merge(old,on='customer_id',how='outer',validate='one_to_one',indicator=True)
        if not comparison._merge.eq('both').all():raise ValueError('customer cohort differs from same-day analysis')
        frames['same_day_comparison']=comparison.drop(columns='_merge')
        frames['same_day_crosstab']=comparison.groupby(['same_day_status','status']).size().rename('customers').reset_index()
        meta['same_day_reference_sha256']=base.digest(previous)
        previous_orders=previous.parent/'orders.parquet'
        if previous_orders.exists():
            dates=pd.read_parquet(previous_orders)[['customer_id','first_order_placed_utc']].drop_duplicates().rename(columns={'first_order_placed_utc':'cdm_first_order_placed_utc'})
            customers=frames['customers'].merge(dates,on='customer_id',validate='one_to_one')
            customers['cdm_first_day_precedes_first_observed']=customers.cdm_first_order_placed_utc.dt.normalize().lt(customers.first_placed_at_utc.dt.normalize())
            frames['customers']=customers
            frames['history_conflicts']=customers.loc[customers.any_new & customers.cdm_first_day_precedes_first_observed].copy()
            audit['first_observed_customers_with_earlier_cdm_date']=len(frames['history_conflicts'])
            meta['same_day_order_reference_sha256']=base.digest(previous_orders)
    for name,frame in frames.items():frame.to_parquet(directory/(name.replace('_','-')+'.parquet'),index=False)
    verification=VERIFY_SQL.replace(STATUSES[0],SCOPE_LABELS[scope]).replace('history_orders_missing_placement=0','history_orders_missing_placement=0 AND vet_orders_missing_ecom_header=0')
    write_text(directory/'verification.sql',verification+';\n');write_text(directory/'audit.json',json.dumps(audit,indent=2)+'\n')
    meta.update(audit=audit,exports={p.name:base.digest(p) for p in directory.glob('*.parquet') if p!=source})
    write_text(manifest,json.dumps(meta,indent=2)+'\n')
    tables=ROOT/'outputs/tables/opportunity'/f'{start_date}_{date.fromisoformat(end_date)-timedelta(days=1)}';tables.mkdir(parents=True,exist_ok=True)
    text=(f'# Aged-order customers: exact first order IDs\n\nCMPU vet-diet CUSTOMER_UPLOAD aged cancellations [{start_date}, {end_date}) UTC. '
          'The first order is the earliest placed order in each customer’s full EDLDB.ECOM.ORDERS history, across all categories, channels, statuses and dates, including cancelled orders. '
          'An aged order must have the exact first order ID. Do not infer chronology from the smallest order ID or the CDM customer date. '
          'Customers count once and match if any aged order is their unique earliest observed order. If an earlier order is observed, the customer was existing for that aged order. '
          'Unresolved earliest-timestamp ties, missing aged records or incomplete timestamps remain unknown unless an earlier placed order proves existing. '
          'The warehouse ORDER_FIRST_ORDER_PLACED_FLAG is audited separately; it does not override chronological order IDs. '
          'Identical duplicates collapse; conflicting source values fail validation. History coverage is limited to available ECOM records.\n\n')
    if scope in ['vet-diet','vet-diet-customer-upload']:
        text=text.replace('exact first order IDs','exact first vet-diet order IDs').replace('across all categories, channels, statuses and dates','restricted to orders with a TRUE IS_VET_DIET_FLAG line in ORDER_LINE_COST_MEASURES_RXP, across all channels, prescription sources, statuses and dates').replace('The warehouse ORDER_FIRST_ORDER_PLACED_FLAG is audited separately; it does not override chronological order IDs. ', '').replace('missing aged records or incomplete timestamps','missing aged records, missing vet-diet order headers or incomplete timestamps')
    if scope=='vet-diet-customer-upload':
        text=text.replace('exact first vet-diet order IDs','exact first CUSTOMER_UPLOAD vet-diet order IDs').replace('across all channels, prescription sources, statuses and dates', 'restricted to CUSTOMER_UPLOAD approval-channel prescriptions matched on RX_ID and numeric customer ID, across all prescription sources, statuses and dates')
    if scope=='vet-diet-customer-upload':
        text=text.replace('History coverage is limited to available ECOM records.', 'History coverage is limited to available prescription, RxP line and ECOM order records. Approval channel uses the current prescription snapshot; unlinked prescription IDs cannot identify historical CUSTOMER_UPLOAD orders.')
    for name,title in [('customer_summary','Customers'),('order_summary','Aged orders'),('same_day_crosstab','Comparison with the previous same-day rule')]:
        if name in frames:
            shown=frames[name].copy()
            if 'percentage' in shown:shown.percentage=shown.percentage.map(lambda v:'N/A' if pd.isna(v) else f'{v:.2f}%')
            text+='## '+title+'\n\n'+markdown_table(shown)+'\n\n'
    if 'first_observed_customers_with_earlier_cdm_date' in audit:
        text+=f"**Source-history conflict:** {audit['first_observed_customers_with_earlier_cdm_date']:,} customers whose aged order is earliest in ECOM have an older CDM first-order date. Earliest observed ECOM order does not establish confirmed new-to-Chewy status for these customers. Full conflicts are exported in history-conflicts.parquet.\n\n"
    if scope=='chewy':text+=f"Warehouse first-order flag: {audit['customers_with_flagged_first_aged_order']:,} customers / {audit['aged_orders_flagged_first']:,} aged orders.\n"
    write_text(tables/(root_name+'.md'),text)
    click.echo(frames['customer_summary'].to_string(index=False));click.echo(frames['order_summary'].to_string(index=False));click.echo(json.dumps(audit,indent=2));click.echo(f'Exports and SQL: {directory}')


if __name__=='__main__':main()

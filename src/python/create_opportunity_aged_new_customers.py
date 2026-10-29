"""New-to-Chewy customers when a qualifying aged order was placed."""
from datetime import datetime, timezone, date, timedelta
import hashlib
import json
from pathlib import Path

import click
import duckdb
from jinja2 import Environment, StrictUndefined
import pandas as pd

from src.python import create_opportunity_order_cancellation_summary as base
from src.python.markdown_tables import markdown_table, write_text

ROOT = base.ROOT
KEYS = ['order_id', 'order_line_id']
STATUSES = ['New on aged-order day', 'Existing customer', 'Unknown']
VERIFY_SQL = '''WITH classified AS (
 SELECT order_id,customer_id,CASE
 WHEN placed_at_utc IS NULL OR first_order_placed_utc IS NULL THEN 'Unknown'
 WHEN CAST(placed_at_utc AS DATE)=CAST(first_order_placed_utc AS DATE) THEN 'New on aged-order day'
 WHEN CAST(first_order_placed_utc AS DATE)<CAST(placed_at_utc AS DATE) THEN 'Existing customer'
 ELSE 'Unknown' END AS status FROM orders
), customers AS (
 SELECT customer_id,CASE WHEN COUNT(*) FILTER (WHERE status='New on aged-order day')>0 THEN 'New on aged-order day'
 WHEN COUNT(*) FILTER (WHERE status='Unknown')>0 THEN 'Unknown'
 ELSE 'Existing customer' END AS status FROM classified GROUP BY customer_id
) SELECT 'order' AS grain,order_id AS id,status FROM classified
UNION ALL SELECT 'customer',customer_id,status FROM customers'''


def render_sql(start, end):
    return Environment(undefined=StrictUndefined).from_string(
        (ROOT/'src/sql/opportunity_aged_new_customers.sql').read_text()).render(**base.parameters(start,end))


def analyze(raw, start, end):
    f=raw.rename(columns=str.lower).copy()
    for column in KEYS+['customer_id']:
        f[column]=f[column].map(base.identifier)
        if f[column].isna().any():raise ValueError('missing aged order/customer keys')
    for column in ['placed_at_utc','cancelled_at_utc','first_order_placed_utc']:
        f[column]=pd.to_datetime(f[column],utc=True,format='mixed')
    for column in ['registry_variants','first_order_variants']:
        if f[column].dropna().ne(1).any():raise ValueError('conflicting source '+column)
    if not f.cancelled_at_utc.between(pd.Timestamp(start,tz='UTC'),pd.Timestamp(end,tz='UTC'),inclusive='left').all():
        raise ValueError('aged cancellation outside requested dates')
    for keys,columns in [(KEYS,['customer_id','placed_at_utc','cancelled_at_utc','first_order_placed_utc']),
                         (['order_id'],['customer_id','placed_at_utc']),
                         (['customer_id'],['first_order_placed_utc','customer_source_rows','first_order_variants'])]:
        if f.groupby(keys)[columns].nunique(dropna=False).gt(1).any().any():
            raise ValueError('conflicting source values at '+','.join(keys))
    duplicate_rows=int(f.duplicated(KEYS).sum())
    lines=f.drop_duplicates(KEYS).copy()
    orders=lines[['order_id','customer_id','placed_at_utc','first_order_placed_utc','customer_source_rows']].drop_duplicates('order_id').copy()
    orders=orders.merge(lines.groupby('order_id').size().rename('qualifying_lines'),on='order_id')
    orders['same_first_order_day']=orders.placed_at_utc.dt.normalize().eq(orders.first_order_placed_utc.dt.normalize())
    orders['first_order_after_aged_day']=orders.first_order_placed_utc.dt.normalize().gt(orders.placed_at_utc.dt.normalize())
    orders['status']='Unknown'
    orders.loc[orders.first_order_placed_utc.dt.normalize().lt(orders.placed_at_utc.dt.normalize()),'status']='Existing customer'
    orders.loc[orders.same_first_order_day,'status']='New on aged-order day'
    orders['quality_flag']=''
    orders.loc[orders.customer_source_rows.isna(),'quality_flag']='missing customer record'
    orders.loc[orders.first_order_placed_utc.isna() & orders.customer_source_rows.notna(),'quality_flag']='missing first-order timestamp'
    orders.loc[orders.placed_at_utc.isna(),'quality_flag']='missing aged-order placement timestamp'
    orders.loc[orders.first_order_after_aged_day,'quality_flag']='first-order day after aged-order day'
    flags=orders.assign(is_new=orders.status.eq(STATUSES[0]),is_unknown=orders.status.eq('Unknown')).groupby('customer_id').agg(
        aged_orders=('order_id','nunique'),any_new=('is_new','any'),any_unknown=('is_unknown','any'))
    flags['status']='Existing customer'
    flags.loc[flags.any_unknown,'status']='Unknown'
    flags.loc[flags.any_new,'status']=STATUSES[0]
    customers=flags.reset_index()
    with duckdb.connect() as c:
        c.execute("SET TimeZone='UTC'")
        c.register('orders',orders[['order_id','customer_id','placed_at_utc','first_order_placed_utc']])
        independent=c.execute(VERIFY_SQL).df()
    for grain,frame,key in [('order',orders,'order_id'),('customer',customers,'customer_id')]:
        expected=independent.loc[independent.grain.eq(grain)].set_index('id').status.to_dict()
        if expected!=frame.set_index(key).status.to_dict():raise ValueError('independent '+grain+' classification differs')
    def summarize(frame):
        counts=frame.status.value_counts().reindex(STATUSES,fill_value=0)
        result=pd.DataFrame({'status':STATUSES,'count':counts.values})
        result['percentage']=result['count'].div(len(frame)).mul(100) if len(frame) else float('nan')
        return pd.concat([result,pd.DataFrame([dict(status='TOTAL',count=len(frame),percentage=100.0 if len(frame) else None)])],ignore_index=True)
    customer_summary=summarize(customers).rename(columns={'count':'customers'})
    order_summary=summarize(orders).rename(columns={'count':'orders'})
    audit=dict(aged_customers=len(customers),aged_orders=len(orders),aged_lines=len(lines),identical_source_duplicates_collapsed=duplicate_rows,
        orders_missing_customer_record=int(orders.customer_source_rows.isna().sum()),
        orders_missing_first_timestamp=int(orders.first_order_placed_utc.isna().sum()),
        orders_missing_placement_timestamp=int(orders.placed_at_utc.isna().sum()),
        orders_first_timestamp_after_aged_day=int(orders.first_order_after_aged_day.sum()),
        customers_with_new_and_multiple_aged_orders=int((flags.any_new & flags.aged_orders.gt(1)).sum()),
        independent_verification='DuckDB agrees with every order and customer classification')
    return dict(lines=lines,orders=orders,customers=customers,customer_summary=customer_summary,order_summary=order_summary),audit


@click.command()
@click.option('--start-date',default='2026-05-01',show_default=True)
@click.option('--end-date',default='2026-08-01',show_default=True,help='Exclusive UTC cancellation end.')
@click.option('--cached',is_flag=True)
@click.option('--print-sql',is_flag=True)
def main(start_date,end_date,cached,print_sql):
    params=base.parameters(start_date,end_date)
    sql=render_sql(start_date,end_date)
    if print_sql:click.echo(sql);return
    directory=ROOT/'data/opportunity/aged-new-customers'/f'{start_date}_{end_date}'
    directory.mkdir(parents=True,exist_ok=True)
    source=directory/'source.parquet';manifest=directory/'analysis.json'
    identity=dict(version=1,**params,timezone='UTC',definition='same calendar day',sql_sha256=hashlib.sha256(sql.encode()).hexdigest())
    query=directory/'query.sql'
    if cached:
        meta=json.loads(manifest.read_text())
        if meta['identity']!=identity or meta['source_sha256']!=base.digest(source):raise click.ClickException('cache fingerprint differs; rerun fresh')
    else:
        write_text(query,sql)
        engine=base.extract(query,source,directory)
        meta=dict(identity=identity,source_sha256=base.digest(source),extracted_at_utc=datetime.now(timezone.utc).isoformat(),**engine)
    frames,audit=analyze(pd.read_parquet(source),start_date,end_date)
    for name,frame in frames.items():frame.to_parquet(directory/(name.replace('_','-')+'.parquet'),index=False)
    write_text(directory/'verification.sql',VERIFY_SQL+';\n')
    write_text(directory/'audit.json',json.dumps(audit,indent=2)+'\n')
    meta.update(audit=audit,exports={p.name:base.digest(p) for p in directory.glob('*.parquet') if p!=source})
    write_text(manifest,json.dumps(meta,indent=2)+'\n')
    tables=ROOT/'outputs/tables/opportunity'/f'{start_date}_{date.fromisoformat(end_date)-timedelta(days=1)}'
    tables.mkdir(parents=True,exist_ok=True)
    note=(f'Qualifying CMPU vet-diet CUSTOMER_UPLOAD aged cancellations [{start_date}, {end_date}) UTC. '
          'Use all qualifying aged orders, without first-order or prescription-creation-date restrictions. '
          'New on aged-order day means the UTC calendar date of ORDER_LINE_COST_MEASURES_RXP.ORDER_PLACED_DTTM equals CDM.CUSTOMER.ORDER_FIRST_PLACED_DTTM. '
          'This is a same-day definition, not proof that this specific order ID was the customer’s first order. '
          'Each customer counts once: new if any aged order matches; otherwise unknown if any aged order cannot be classified; otherwise existing. '
          'Order counts classify distinct aged order IDs separately, collapsing repeated lines and shipments. '
          'Missing customer/timestamps or first-order dates after placement remain unknown and audited. '
          'Identical duplicates collapse; conflicting customer, prescription or order source values fail validation.\n\n')
    text='# Aged-order customers new to Chewy\n\n'+note
    for name,title in [('customer_summary','Customers'),('order_summary','Aged orders')]:
        shown=frames[name].copy();shown.percentage=shown.percentage.map(lambda v:'N/A' if pd.isna(v) else f'{v:.2f}%')
        text+='## '+title+'\n\n'+markdown_table(shown)+'\n\n'
    write_text(tables/'aged-new-customers.md',text)
    click.echo(frames['customer_summary'].to_string(index=False));click.echo(frames['order_summary'].to_string(index=False))
    click.echo(f'Exports and SQL: {directory}');click.echo(f'Summary: {tables/"aged-new-customers.md"}')


if __name__=='__main__':main()

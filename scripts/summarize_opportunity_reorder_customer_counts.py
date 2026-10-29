"""Distinct-order frequency per customer and per cancellation/part/pet window."""
import json
from pathlib import Path
import sys
import click
import duckdb
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from src.python import create_opportunity_order_cancellation_summary as base
from src.python.markdown_tables import markdown_table,write_text


@click.command()
@click.option('--directory',type=click.Path(path_type=Path),default=ROOT/'data/opportunity/aged-reorder-windows/2026-06-01_2026-09-01_7d-14d-21d-28d-35d-42d_as-of-2026-10-28')
@click.option('--followup-days',default=42,type=click.IntRange(min=1))
def main(directory,followup_days):
    meta=json.loads((directory/'source.json').read_text())
    loaded={}
    for name in ['reorders','matches','originals']:
        file=f'{followup_days}d-{name}.parquet'
        if base.digest(directory/file)!=meta['exports'][file]:raise ValueError('source fingerprint mismatch')
        loaded[name]=pd.read_parquet(directory/file)
    r,m,o=loaded['reorders'],loaded['matches'],loaded['originals']
    m=m.loc[m.qualifying_non_cancelled].copy()
    keys=['original_order_id','original_customer_id','original_product_part_number','original_pet_id','original_cancel_utc']
    windows=m.groupby(keys).reorder_order_id.nunique().rename('non_cancelled_orders').reset_index()
    per_customer=windows.groupby('original_customer_id').non_cancelled_orders.max().rename('max_orders_same_part_pet_one_window')
    totals=r.groupby('reorder_customer_id').reorder_order_id.nunique().rename('all_matching_orders')
    customers=pd.DataFrame({'customer_id':sorted(o.original_customer_id.unique())})
    customers=customers.merge(totals,left_on='customer_id',right_index=True,how='left').merge(
        per_customer,left_on='customer_id',right_index=True,how='left').fillna(0)
    for col in ['all_matching_orders','max_orders_same_part_pet_one_window']:customers[col]=customers[col].astype(int)
    sql='''WITH window_counts AS (
      SELECT original_order_id,original_customer_id,original_product_part_number,original_pet_id,original_cancel_utc,
             COUNT(DISTINCT reorder_order_id) AS n
      FROM matches GROUP BY ALL
    ) SELECT original_customer_id,MAX(n) FROM window_counts GROUP BY original_customer_id'''
    with duckdb.connect() as c:
        c.register('matches',m[keys+['reorder_order_id']])
        independent=dict(c.execute(sql).fetchall())
        c.register('reorders',r[['reorder_customer_id','reorder_order_id']])
        total_counts=dict(c.execute('SELECT reorder_customer_id,COUNT(DISTINCT reorder_order_id) FROM reorders GROUP BY reorder_customer_id').fetchall())
    assert independent==per_customer.to_dict() and total_counts==totals.to_dict()
    summary_path=directory/'summary.parquet'
    assert base.digest(summary_path)==meta['exports']['summary.parquet']
    expected=pd.read_parquet(summary_path).set_index('followup_days').loc[followup_days]
    assert customers.all_matching_orders.sum()==r.reorder_order_id.nunique()==int(expected.orders)
    assert int(customers.all_matching_orders.gt(0).sum())==int(expected.customers)
    def distribution(column):
        return customers.groupby(column).size().rename('customers').reset_index().rename(columns={column:'orders'})
    overall=distribution('all_matching_orders')
    same_window=distribution('max_orders_same_part_pet_one_window')
    pairs=r.groupby(['reorder_customer_id','reorder_product_part_number','reorder_pet_id']).reorder_order_id.nunique().rename('orders_across_all_original_windows').reset_index()
    paths={}
    for name,frame in [('customer-counts',customers),('cancellation-window-counts',windows),('part-pet-counts',pairs),
                       ('customer-order-distribution',overall),('same-part-pet-window-distribution',same_window)]:
        path=directory/f'{followup_days}d-{name}.parquet';frame.to_parquet(path,index=False);paths[path.name]=base.digest(path)
    metrics=dict(aged_customers=len(customers),customers_with_reorders=int(customers.all_matching_orders.gt(0).sum()),
      customers_without_reorders=int(customers.all_matching_orders.eq(0).sum()),
      customers_with_3plus_orders_overall=int(customers.all_matching_orders.ge(3).sum()),
      customers_with_3plus_same_part_pet_one_window=int(customers.max_orders_same_part_pet_one_window.ge(3).sum()),
      max_same_part_pet_one_window=int(customers.max_orders_same_part_pet_one_window.max()))
    identity=meta['identity'];end=pd.Timestamp(identity['end_date'])-pd.Timedelta(days=1)
    tables=ROOT/'outputs/tables/opportunity'/f"{identity['start_date']}_{end.date()}"
    tables.mkdir(parents=True,exist_ok=True)
    note=(f"Original aged cancellations [{identity['start_date']}, {identity['end_date']}) UTC, "
      f"{followup_days}-day follow-up, as of {identity['as_of_date']} 00:00 UTC. Same cohort and non-cancelled-order rules as the financial follow-up table. "
      'Each order counts once, regardless of lines/shipments. For same-part/pet frequency, count distinct reorders within each original cancellation/order/customer/part/pet window, '
      'then take each customer’s largest count. This prevents combining different products, pets or separate cancellation windows. '
      'The per-customer overall distribution separately combines all matched products/pets/windows. Zero means no qualifying reorder.\n\n')
    text=(f'# {followup_days}-day reorder order frequency\n\n'+note+'## All matched orders per customer\n\n'+markdown_table(overall)
      +'\n\n## Maximum orders for one matching part/pet in one follow-up window, per customer\n\n'+markdown_table(same_window)+'\n')
    write_text(tables/f'aged-{followup_days}d-reorder-customer-frequency.md',text)
    write_text(directory/f'{followup_days}d-customer-frequency-verification.sql',sql+';\n')
    write_text(directory/f'{followup_days}d-customer-frequency-analysis.json',json.dumps(dict(metrics=metrics,
        inputs={f'{followup_days}d-{name}.parquet':meta['exports'][f'{followup_days}d-{name}.parquet'] for name in loaded},
        exports=paths,independent_verification='DuckDB distinct-order counts match pandas for every customer and maximum cancellation window'),indent=2)+'\n')
    print(json.dumps(metrics,indent=2));print(overall.to_string(index=False));print(same_window.to_string(index=False))


if __name__=='__main__':main()

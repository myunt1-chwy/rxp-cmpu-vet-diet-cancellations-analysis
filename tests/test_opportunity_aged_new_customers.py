import json
import re
from pathlib import Path

from click.testing import CliRunner
import duckdb
import pandas as pd
import pytest

from src.python import create_opportunity_aged_new_customers as a
from test_opportunity_aged_reorders import sql_sources


def source():
    def row(order,customer,placed,first,**extra):
        return dict(order_id=order,order_line_id=order*10,customer_id=customer,
            placed_at_utc=placed,cancelled_at_utc='2026-06-20',first_order_placed_utc=first,
            customer_source_rows=1,first_order_variants=1,registry_variants=1,**extra)
    rows=[row(1,1,'2026-06-01 23:59:59','2026-06-01 00:01'),
          row(2,1,'2026-06-08','2026-06-01 00:01'),
          row(3,2,'2026-06-01','2020-01-01'),
          row(4,3,'2026-06-01',None),
          row(5,4,'2026-06-01','2026-06-02'),
          row(6,5,None,'2026-06-01'),
          row(7,6,'2026-06-02 00:00:00','2026-06-01 23:59:59')]
    f=pd.DataFrame(rows)
    f.loc[f.order_id.eq(4),['customer_source_rows','first_order_variants']]=None
    return pd.concat([f,f.iloc[[0]],f.iloc[[0]].assign(order_line_id=11)],ignore_index=True)


def test_same_day_distinct_customers_orders_duplicates_missing_and_later():
    frames,audit=a.analyze(source(),'2026-05-01','2026-08-01')
    assert audit['aged_customers']==6 and audit['aged_orders']==7 and audit['aged_lines']==8
    assert audit['identical_source_duplicates_collapsed']==1
    orders=frames['orders'].set_index('order_id')
    assert orders.loc['1','status']=='New on aged-order day'
    assert orders.loc['2','status']==orders.loc['7','status']=='Existing customer'
    assert orders.loc['4','status']==orders.loc['5','status']==orders.loc['6','status']=='Unknown'
    assert frames['customer_summary'].set_index('status').customers.to_dict()=={
        'New on aged-order day':1,'Existing customer':2,'Unknown':3,'TOTAL':6}
    assert audit['orders_first_timestamp_after_aged_day']==1
    assert audit['orders_missing_customer_record']==1
    assert frames['orders'].loc[frames['orders'].order_id.eq('1'),'qualifying_lines'].iloc[0]==2


@pytest.mark.parametrize('field,value',[
    ('registry_variants',2),('first_order_variants',2),('customer_id',99),
    ('placed_at_utc','2026-06-02'),('first_order_placed_utc','2026-05-01')])
def test_conflicting_sources_rejected(field,value):
    raw=source();raw.loc[raw.index[-1],field]=value
    with pytest.raises(ValueError,match='conflicting'):a.analyze(raw,'2026-05-01','2026-08-01')


def test_sql_cohort_boundaries_and_customer_duplicate_first_values():
    rx,lines=sql_sources()
    # Identical physical source records collapse after the SQL joins.
    lines=pd.concat([lines,lines.iloc[[0]],
        lines.iloc[[0]].assign(order_id=2,order_line_id=22,order_cancel_dttm=pd.Timestamp('2026-04-30 23:59:59')),
        lines.iloc[[0]].assign(order_id=3,order_line_id=33,order_cancel_dttm=pd.Timestamp('2026-08-01')),
        lines.iloc[[0]].assign(order_id=4,order_line_id=44,order_cancel_dttm=pd.Timestamp('2026-05-01'))])
    customers=pd.DataFrame({'customer_id':[7,7],'order_first_placed_dttm':pd.to_datetime(['2026-05-01','2026-05-01'])})
    sql=a.render_sql('2026-05-01','2026-08-01').replace('EDLDB.BT_HCA_HCDM.ORDER_LINE_COST_MEASURES_RXP','line_source').replace(
        'EDLDB.BT_HCA_HCDM.RXP_PRESCRIPTIONS','rx_source').replace('EDLDB.CDM.CUSTOMER','customer_source').replace('TIMESTAMP_NTZ','TIMESTAMP_NS')
    def run():
        with duckdb.connect() as c:
            c.register('line_source',lines);c.register('rx_source',rx);c.register('customer_source',customers)
            c.execute('CREATE MACRO IFF(x,a,b) AS CASE WHEN x THEN a ELSE b END')
            return c.execute(sql).df()
    raw=run();frames,audit=a.analyze(raw,'2026-05-01','2026-08-01')
    assert set(frames['orders'].order_id)=={'1','4'} and audit['aged_customers']==1
    assert frames['customer_summary'].iloc[0].customers==1
    customers.loc[1,'order_first_placed_dttm']=pd.Timestamp('2026-05-02')
    with pytest.raises(ValueError,match='first_order_variants'):a.analyze(run(),'2026-05-01','2026-08-01')
    assert 'PARSE_JSON' not in sql and 'order_first_placed_dttm_rx' not in sql.lower()


def test_fresh_cached_sql_only_and_source_hash(tmp_path,monkeypatch):
    (tmp_path/'src/sql').mkdir(parents=True)
    (tmp_path/'src/sql/opportunity_aged_new_customers.sql').write_text((a.ROOT/'src/sql/opportunity_aged_new_customers.sql').read_text())
    monkeypatch.setattr(a,'ROOT',tmp_path);calls=[]
    def extract(query,parquet,directory):
        calls.append(query);source().to_parquet(parquet,index=False);return dict(engine='fixture')
    monkeypatch.setattr(a.base,'extract',extract)
    runner=CliRunner()
    printed=runner.invoke(a.main,['--print-sql']);assert printed.exit_code==0 and not calls
    assert 'EDLDB.CDM.CUSTOMER' in printed.output
    fresh=runner.invoke(a.main,[]);assert fresh.exit_code==0,fresh.output
    cached=runner.invoke(a.main,['--cached']);assert cached.exit_code==0,cached.output
    assert len(calls)==1
    report=next((tmp_path/'outputs').rglob('aged-new-customers.md')).read_text()
    assert 'same-day definition' in report and 'TOTAL' in report
    manifest=json.loads(next((tmp_path/'data').rglob('analysis.json')).read_text())
    assert manifest['audit']['aged_customers']==6 and 'customers.parquet' in manifest['exports']
    next((tmp_path/'data').rglob('source.parquet')).write_bytes(b'broken')
    invalid=runner.invoke(a.main,['--cached']);assert invalid.exit_code!=0 and 'fingerprint differs' in invalid.output


def test_empty_cohort():
    frames,audit=a.analyze(source().iloc[:0],'2026-05-01','2026-08-01')
    assert audit['aged_customers']==audit['aged_orders']==0
    assert frames['customer_summary'].percentage.isna().all()

import json

from click.testing import CliRunner
import duckdb
import pandas as pd
import pytest

from src.python import create_opportunity_aged_first_order_customers as a
from test_opportunity_aged_reorders import sql_sources


def orders_source():
    # Later order has the smaller ID and the warehouse first-order flag.
    # The cancelled aged order is still the earliest chronological order.
    return pd.DataFrame([
        dict(order_id=1,customer_id=7,order_placed_dttm=pd.Timestamp('2026-05-01'),order_first_order_placed_flag=False),
        dict(order_id=0,customer_id=7,order_placed_dttm=pd.Timestamp('2026-05-02'),order_first_order_placed_flag=True),
        dict(order_id=9,customer_id=8,order_placed_dttm=pd.Timestamp('2010-01-01'),order_first_order_placed_flag=True)])


def execute(orders,lines=None,scope="chewy",rx=None):
    default_rx,default_lines=sql_sources();lines=default_lines if lines is None else lines
    rx=default_rx if rx is None else rx
    sql=a.render_sql('2026-05-01','2026-08-01',scope).replace('EDLDB.BT_HCA_HCDM.ORDER_LINE_COST_MEASURES_RXP','line_source').replace(
        'EDLDB.BT_HCA_HCDM.RXP_PRESCRIPTIONS','rx_source').replace('EDLDB.ECOM.ORDERS','order_source').replace('TIMESTAMP_NTZ','TIMESTAMP_NS')
    with duckdb.connect() as c:
        c.register('line_source',lines);c.register('rx_source',rx);c.register('order_source',orders)
        c.execute('CREATE MACRO IFF(x,a,b) AS CASE WHEN x THEN a ELSE b END')
        return c.execute(sql).df()


def test_exact_chronological_order_id_including_cancelled_and_duplicate_sources():
    o=orders_source();o=pd.concat([o,o.iloc[[0]]])
    _,lines=sql_sources();lines=pd.concat([lines,lines.iloc[[0]],lines.iloc[[0]].assign(order_line_id=12)])
    frames,audit=a.analyze(execute(o,lines),'2026-05-01','2026-08-01')
    assert frames['orders'].iloc[0].first_order_id=='1'
    assert frames['orders'].iloc[0].flagged_first_order_id=='0'
    assert frames['customer_summary'].iloc[0].customers==1
    assert audit['identical_aged_source_duplicates_collapsed']==1
    assert audit['identical_history_duplicates_collapsed']==1
    assert audit['customers_chronological_new_but_not_flagged']==1
    assert audit['aged_lines']==2 and audit['aged_orders']==1


def test_same_day_earlier_order_is_existing_and_history_not_date_limited():
    o=orders_source()
    _,lines=sql_sources();lines.loc[lines.order_id.eq(1),'order_placed_dttm']=pd.Timestamp('2026-05-01 23:59')
    o.loc[o.order_id.eq(1),'order_placed_dttm']=pd.Timestamp('2026-05-01 23:59')
    older=o.iloc[[0]].assign(order_id=99,order_placed_dttm=pd.Timestamp('2026-05-01 00:01'))
    frames,_=a.analyze(execute(pd.concat([o,older]),lines),'2026-05-01','2026-08-01')
    assert frames['orders'].iloc[0].first_order_id=='99' and frames['orders'].iloc[0].status=='Existing customer'
    older['order_placed_dttm']=pd.Timestamp('2010-01-01')
    frames,_=a.analyze(execute(pd.concat([o,older]),lines),'2026-05-01','2026-08-01')
    assert frames['orders'].iloc[0].status=='Existing customer'


@pytest.mark.parametrize('kind',['tie','missing-history-time','missing-aged-order'])
def test_unknown_ties_or_missing_history(kind):
    o=orders_source()
    if kind=='tie':o=pd.concat([o,o.iloc[[0]].assign(order_id=99)])
    if kind=='missing-history-time':o=pd.concat([o,o.iloc[[0]].assign(order_id=99,order_placed_dttm=pd.NaT)])
    if kind=='missing-aged-order':o=o.loc[o.order_id.ne(1)]
    frames,_=a.analyze(execute(o),'2026-05-01','2026-08-01')
    assert frames['orders'].iloc[0].status=='Unknown'


def test_earlier_order_proves_existing_despite_missing_other_timestamp():
    o=orders_source();o=pd.concat([o,o.iloc[[0]].assign(order_id=99,order_placed_dttm=pd.Timestamp('2010-01-01')),
                                  o.iloc[[0]].assign(order_id=100,order_placed_dttm=pd.NaT)])
    frames,_=a.analyze(execute(o),'2026-05-01','2026-08-01')
    assert frames['orders'].iloc[0].status=='Existing customer'


def test_conflicting_history_rows_fail():
    o=orders_source();o=pd.concat([o,o.iloc[[0]].assign(order_placed_dttm=pd.Timestamp('2026-05-02'))])
    with pytest.raises(ValueError,match='conflicting source'):a.analyze(execute(o),'2026-05-01','2026-08-01')


def test_multiple_aged_orders_count_new_customer_once():
    o=orders_source();_,lines=sql_sources()
    lines=pd.concat([lines,lines.iloc[[0]].assign(order_id=0,order_line_id=2,order_placed_dttm=pd.Timestamp('2026-05-02'))])
    frames,audit=a.analyze(execute(o,lines),'2026-05-01','2026-08-01')
    assert audit['aged_orders']==2 and audit['aged_customers']==1
    assert frames['customer_summary'].iloc[0].customers==1
    assert frames['order_summary'].set_index('status').orders['Existing customer']==1


def test_fresh_cached_sql_only_and_comparison(tmp_path,monkeypatch):
    raw=execute(orders_source())
    (tmp_path/'src/sql').mkdir(parents=True)
    (tmp_path/'src/sql/opportunity_aged_first_order_customers.sql').write_text((a.ROOT/'src/sql/opportunity_aged_first_order_customers.sql').read_text())
    previous=tmp_path/'data/opportunity/aged-new-customers/2026-05-01_2026-08-01';previous.mkdir(parents=True)
    pd.DataFrame({'customer_id':['7'],'status':['Unknown']}).to_parquet(previous/'customers.parquet',index=False)
    pd.DataFrame({'customer_id':['7'],'first_order_placed_utc':pd.to_datetime(['2020-01-01'],utc=True)}).to_parquet(previous/'orders.parquet',index=False)
    monkeypatch.setattr(a,'ROOT',tmp_path);calls=[]
    def extract(query,parquet,directory):
        calls.append(query);raw.to_parquet(parquet,index=False);return dict(engine='fixture')
    monkeypatch.setattr(a.base,'extract',extract)
    runner=CliRunner();printed=runner.invoke(a.main,['--print-sql'])
    assert printed.exit_code==0 and 'EDLDB.ECOM.ORDERS' in printed.output and not calls
    for args in [[],['--cached']]:
        result=runner.invoke(a.main,args);assert result.exit_code==0,result.output
    assert len(calls)==1
    report=next((tmp_path/'outputs').rglob('aged-first-order-customers.md')).read_text()
    assert 'including cancelled orders' in report and 'previous same-day rule' in report
    manifest=json.loads(next((tmp_path/'data').rglob('analysis.json')).read_text())
    assert 'same-day-crosstab.parquet' in manifest['exports']
    assert manifest['audit']['first_observed_customers_with_earlier_cdm_date']==1
    assert 'history-conflicts.parquet' in manifest['exports']
    assert 'Source-history conflict' in report
    next((tmp_path/'data').rglob('source.parquet')).write_bytes(b'broken')
    result=runner.invoke(a.main,['--cached']);assert result.exit_code!=0 and 'fingerprint differs' in result.output


def test_empty_cohort():
    raw=execute(orders_source()).iloc[:0]
    frames,audit=a.analyze(raw,'2026-05-01','2026-08-01')
    assert audit['aged_customers']==audit['aged_orders']==0
    assert frames['customer_summary'].percentage.isna().all()

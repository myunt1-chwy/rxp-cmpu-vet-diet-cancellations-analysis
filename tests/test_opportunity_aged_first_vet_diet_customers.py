from click.testing import CliRunner
import pandas as pd

from src.python import create_opportunity_aged_first_order_customers as a
from test_opportunity_aged_first_order_customers import execute,orders_source
from test_opportunity_aged_reorders import sql_sources


def history(vet=True):
    _,lines=sql_sources();lines=lines.iloc[[0]]
    older=lines.assign(order_id=99,order_line_id=990,order_placed_dttm=pd.Timestamp('2010-01-01'),
        order_cancel_dttm=pd.NaT,order_order_line_status='D',order_cancel_reason=None,
        rx_id='OTHER-SOURCE-CHANNEL',is_vet_diet_flag=vet)
    orders=orders_source();orders=pd.concat([orders,orders.iloc[[0]].assign(order_id=99,
        order_placed_dttm=pd.Timestamp('2010-01-01'),order_first_order_placed_flag=True)])
    return orders,pd.concat([lines,older])


def test_first_vet_diet_ignores_prior_other_categories_and_includes_all_sources():
    orders,lines=history(vet=False)
    frames,_=a.analyze(execute(orders,lines,scope='vet-diet'),'2026-05-01','2026-08-01',scope='vet-diet')
    assert frames['orders'].iloc[0].first_order_id=='1'
    assert frames['orders'].iloc[0].status=='First order in observed vet-diet history'
    # No prior customer-upload/CMPU prescription is needed for vet-diet history.
    lines.loc[lines.order_id.eq(99),'is_vet_diet_flag']=True
    frames,_=a.analyze(execute(orders,lines,scope='vet-diet'),'2026-05-01','2026-08-01',scope='vet-diet')
    assert frames['orders'].iloc[0].first_order_id=='99'
    assert frames['orders'].iloc[0].status=='Existing customer'
    assert frames['customer_summary'].set_index('status').customers['Existing customer']==1


def test_missing_vet_diet_header_prevents_unqualified_new_classification():
    orders,lines=history();orders=orders.loc[orders.order_id.ne(99)]
    frames,audit=a.analyze(execute(orders,lines,scope='vet-diet'),'2026-05-01','2026-08-01',scope='vet-diet')
    assert frames['orders'].iloc[0].status=='Unknown'
    assert audit['customers_missing_vet_order_headers']==1


def test_vet_diet_scope_fresh_cached_sql_only_separate_outputs(tmp_path,monkeypatch):
    orders,lines=history(vet=False);raw=execute(orders,lines,scope='vet-diet')
    (tmp_path/'src/sql').mkdir(parents=True)
    filename='opportunity_aged_first_vet_diet_order_customers.sql'
    (tmp_path/'src/sql'/filename).write_text((a.ROOT/'src/sql'/filename).read_text())
    monkeypatch.setattr(a,'ROOT',tmp_path);calls=[]
    def extract(query,parquet,directory):
        calls.append(query);raw.to_parquet(parquet,index=False);return dict(engine='fixture')
    monkeypatch.setattr(a.base,'extract',extract)
    runner=CliRunner()
    for args in [['--scope','vet-diet'],['--scope','vet-diet','--cached']]:
        result=runner.invoke(a.main,args);assert result.exit_code==0,result.output
    assert len(calls)==1
    result=runner.invoke(a.main,['--scope','vet-diet','--print-sql'])
    assert result.exit_code==0 and 'l.is_vet_diet_flag=TRUE' in result.output and len(calls)==1
    report=next((tmp_path/'outputs').rglob('aged-first-vet-diet-order-customers.md')).read_text()
    assert 'all channels, prescription sources, statuses and dates' in report
    assert 'Warehouse first-order flag:' not in report
    assert next((tmp_path/'data').rglob('analysis.json')).parent.parent.name=='aged-first-vet-diet-order-customers'

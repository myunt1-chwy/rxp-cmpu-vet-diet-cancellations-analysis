import json

from click.testing import CliRunner
import pandas as pd
import pytest

from src.python import create_opportunity_aged_first_order_customers as a
from test_opportunity_aged_first_order_customers import execute
from test_opportunity_aged_first_vet_diet_customers import history
from test_opportunity_aged_reorders import sql_sources

SCOPE='vet-diet-customer-upload'


def channel_history(channel='FAX',customer=7):
    orders,lines=history(vet=True)
    lines.loc[lines.order_id.eq(99),'rx_id']=' HIST-RX '
    rx,_=sql_sources()
    extra=rx.assign(rx_id='HIST-RX',customer_id=customer,approval_channel=channel,prescription_source='OTHER_SOURCE')
    return orders,lines,pd.concat([rx,extra])


def test_earlier_other_channel_does_not_block_first_customer_upload():
    orders,lines,rx=channel_history()
    frames,_=a.analyze(execute(orders,lines,scope=SCOPE,rx=rx),'2026-05-01','2026-08-01',scope=SCOPE)
    assert frames['orders'].iloc[0].first_order_id=='1'
    assert frames['orders'].iloc[0].status=='First observed CUSTOMER_UPLOAD vet-diet order'
    # Prior history counts even outside the cancellation window and from a
    # non-CMPU prescription source. The order's status is unrestricted.
    rx.loc[rx.rx_id.eq('HIST-RX'),'approval_channel']='CUSTOMER_UPLOAD'
    frames,_=a.analyze(execute(orders,lines,scope=SCOPE,rx=rx),'2026-05-01','2026-08-01',scope=SCOPE)
    assert frames['orders'].iloc[0].first_order_id=='99'
    assert frames['orders'].iloc[0].status=='Existing customer'


def test_historical_rx_match_requires_customer_and_vet_diet_flags():
    orders,lines,rx=channel_history(channel='CUSTOMER_UPLOAD',customer=8)
    for scenario in ['wrong-customer','non-vet-line','non-vet-prescription']:
        r=rx.copy();l=lines.copy()
        if scenario!='wrong-customer':r.loc[r.rx_id.eq('HIST-RX'),'customer_id']=7
        if scenario=='non-vet-line':l.loc[l.order_id.eq(99),'is_vet_diet_flag']=False
        if scenario=='non-vet-prescription':r.loc[r.rx_id.eq('HIST-RX'),'is_vet_diet_flag']=False
        frames,_=a.analyze(execute(orders,l,scope=SCOPE,rx=r),'2026-05-01','2026-08-01',scope=SCOPE)
        assert frames['orders'].iloc[0].first_order_id=='1'


def test_conflicting_historical_prescription_channel_fails():
    orders,lines,rx=channel_history(channel='CUSTOMER_UPLOAD')
    rx=pd.concat([rx,rx.loc[rx.rx_id.eq('HIST-RX')].assign(approval_channel='FAX')])
    raw=execute(orders,lines,scope=SCOPE,rx=rx)
    with pytest.raises(ValueError,match='history_prescription_variants'):
        a.analyze(raw,'2026-05-01','2026-08-01',scope=SCOPE)


def test_channel_scope_fresh_cached_sql_only_and_separate_output(tmp_path,monkeypatch):
    orders,lines,rx=channel_history();raw=execute(orders,lines,scope=SCOPE,rx=rx)
    (tmp_path/'src/sql').mkdir(parents=True)
    filename=a.SCOPE_TEMPLATES[SCOPE]
    (tmp_path/'src/sql'/filename).write_text((a.ROOT/'src/sql'/filename).read_text())
    monkeypatch.setattr(a,'ROOT',tmp_path);calls=[]
    def extract(query,parquet,directory):
        calls.append(query);raw.to_parquet(parquet,index=False);return dict(engine='fixture')
    monkeypatch.setattr(a.base,'extract',extract)
    runner=CliRunner()
    for args in [['--scope',SCOPE],['--scope',SCOPE,'--cached']]:
        result=runner.invoke(a.main,args);assert result.exit_code==0,result.output
    assert len(calls)==1
    result=runner.invoke(a.main,['--scope',SCOPE,'--print-sql'])
    assert result.exit_code==0 and "p.approval_channel='CUSTOMER_UPLOAD'" in result.output and len(calls)==1
    history_sql=result.output.split('), vet_diet_order_keys AS (')[1].split('), history_keys AS (')[0]
    assert 'prescription_source=' not in history_sql and 'order_placed_dttm' not in history_sql
    report=next((tmp_path/'outputs').rglob('aged-first-customer-upload-vet-diet-order-customers.md')).read_text()
    assert 'across all prescription sources, statuses and dates' in report
    manifest=json.loads(next((tmp_path/'data').rglob('analysis.json')).read_text())
    assert manifest['identity']['scope']==SCOPE
    assert next((tmp_path/'data').rglob('analysis.json')).parent.parent.name==a.SCOPE_FOLDERS[SCOPE]

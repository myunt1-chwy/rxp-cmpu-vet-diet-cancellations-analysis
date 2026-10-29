from datetime import datetime,timezone
import json
import re

from click.testing import CliRunner
import duckdb
import pandas as pd
import pytest

from src.python import create_opportunity_new_upload_customer_follow_up as a
from test_opportunity_aged_reorders import sources,sql_sources


def cohort_fixture(root,scope=a.SCOPE):
    d=root/'data/opportunity'/a.first.SCOPE_FOLDERS[scope]/'2026-05-01_2026-08-01';d.mkdir(parents=True)
    orders=pd.DataFrame({'order_id':['1','2','3'],'customer_id':['7','7','8'],
        'status':[a.first.SCOPE_LABELS[scope],'Existing customer','Existing customer']})
    lines=pd.DataFrame({'order_id':['1','2','3'],'order_line_id':['11','22','33'],'customer_id':['7','7','8'],
        'cancelled_at_utc':pd.to_datetime(['2026-06-01','2026-06-02','2026-06-02'],utc=True)})
    customers=pd.DataFrame({'customer_id':['7','8'],'any_new':[True,False]})
    for name,frame in [('orders',orders),('lines',lines),('customers',customers),('source',lines)]:frame.to_parquet(d/(name+'.parquet'),index=False)
    sql=a.first.render_sql('2026-05-01','2026-08-01',scope)
    meta=dict(identity=a.first.source_identity(a.base.parameters('2026-05-01','2026-08-01'),sql,scope),
        source_sha256=a.base.digest(d/'source.parquet'),exports={name+'.parquet':a.base.digest(d/(name+'.parquet')) for name in ['orders','lines','customers']})
    (d/'analysis.json').write_text(json.dumps(meta))
    return d


def test_frozen_cohort_only_first_aged_order_anchors_and_hash_validation(tmp_path,monkeypatch):
    d=cohort_fixture(tmp_path);monkeypatch.setattr(a,'ROOT',tmp_path)
    anchors,frozen,_=a.load_cohort('2026-05-01','2026-08-01',True)
    assert anchors.to_dict('records')==[{'order_id':'1','customer_id':'7'}]
    assert frozen.original_order_id.tolist()==['1']
    (d/'orders.parquet').write_bytes(b'bad')
    with pytest.raises(ValueError,match='fingerprint'):a.load_cohort('2026-05-01','2026-08-01',True)


def test_windows_fixed_denominator_missing_keys_and_zero_returns():
    raw,frozen=sources();raw=raw.iloc[[0]];frozen=frozen.iloc[[0]]
    anchors=pd.DataFrame({'order_id':['1'],'customer_id':['7']})
    summary,exports=a.analyze_windows(raw,frozen,anchors,'2026-10-28')
    assert summary.cohort_customers.eq(1).all() and summary.returning_customers.eq(1).all()
    assert summary.return_percentage.eq(100).all()
    assert len(exports['70d-customer-outcomes'])==1
    raw=raw.copy();raw['original_pet_id']=None;raw['reorder_order_id']=None
    summary,exports=a.analyze_windows(raw,frozen,anchors,'2026-10-28')
    assert summary.cohort_customers.eq(1).all() and summary.eligible_customers.eq(0).all()
    assert summary.returning_customers.eq(0).all() and summary.return_percentage.eq(0).all()
    assert not exports['70d-customer-outcomes'].returned.any()


def test_sql_first_anchor_no_later_reset_70_day_boundary_and_cancellations():
    rx,lines=sql_sources()
    original=lines.iloc[[0]]
    lines=pd.concat([lines,original.assign(order_id=2,order_line_id=22,order_placed_dttm=pd.Timestamp('2026-06-10'),
        order_cancel_dttm=pd.Timestamp('2026-06-20')),
        lines.iloc[[1]].assign(order_id=99,order_line_id=990,shipment_key=9900,order_placed_dttm=pd.Timestamp('2026-08-20')),
        lines.iloc[[1]].assign(order_id=100,order_line_id=1000,shipment_key=10000,order_placed_dttm=pd.Timestamp('2026-08-10')),
        lines.iloc[[1]].assign(order_id=101,order_line_id=1010,shipment_key=10100,order_placed_dttm=pd.Timestamp('2026-08-10')+pd.Timedelta(nanoseconds=1))])
    orders=lines[['order_id','customer_id','order_placed_dttm']].drop_duplicates().assign(order_first_order_placed_flag=False)
    sql=a.render_sql('2026-05-01','2026-08-01','2026-10-28').replace('EDLDB.BT_HCA_HCDM.ORDER_LINE_COST_MEASURES_RXP','line_source').replace(
        'EDLDB.BT_HCA_HCDM.RXP_PRESCRIPTIONS','rx_source').replace('EDLDB.ECOM.ORDERS','order_source').replace('TIMESTAMP_NTZ','TIMESTAMP_NS')
    sql=re.sub(r'DATEADD\(day,(\d+),([^\)]+)\)',lambda m:'('+m[2]+"+INTERVAL '"+m[1]+" days')",sql)
    lines=lines.copy();lines.order_line_net_sales=lines.order_line_net_sales.map(a.base.money)
    with duckdb.connect() as c:
        for name,f in [('line_source',lines),('rx_source',rx),('order_source',orders)]:c.register(name,f)
        c.execute('CREATE MACRO IFF(x,a,b) AS CASE WHEN x THEN a ELSE b END')
        c.execute('CREATE MACRO TO_CHAR(x,f) AS CAST(x AS VARCHAR)')
        raw=c.execute(sql).df()
    assert set(raw.original_order_id)=={1}
    frozen=pd.DataFrame({'original_order_id':['1'],'original_line_id':['11'],'customer_id':['7'],
        'cancelled_at_utc':pd.to_datetime(['2026-06-01'],utc=True)})
    anchors=pd.DataFrame({'order_id':['1'],'customer_id':['7']})
    summary,exports=a.analyze_windows(raw,frozen,anchors,'2026-10-28')
    selected=set(exports['70d-reorders'].reorder_order_id)
    assert '100' in selected and '101' not in selected and '99' not in selected and '2' not in selected
    assert summary.iloc[0].orders==1 and summary.iloc[-1].orders==10


def test_new_followup_fresh_cached_sql_only_and_provenance(tmp_path,monkeypatch):
    (tmp_path/'src/sql').mkdir(parents=True)
    filename='opportunity_new_upload_customer_follow_up.sql'
    (tmp_path/'src/sql'/filename).write_text((a.ROOT/'src/sql'/filename).read_text())
    cohort_fixture(tmp_path);monkeypatch.setattr(a,'ROOT',tmp_path);calls=[]
    raw,_=sources();raw=raw.iloc[[0]]
    def extract(query,parquet,directory):
        calls.append(query);raw.to_parquet(parquet,index=False);return dict(engine='fixture')
    monkeypatch.setattr(a.base,'extract',extract)
    appendix=tmp_path/'src/latex/appendix';appendix.mkdir(parents=True)
    for name in ['financial_opportunity_reorders','financial_opportunity_chewy_follow_up']:
        (appendix/(name+'.tex')).write_text('Existing table\n')
    parent=appendix/'financial_opportunity.tex'
    parent.write_text('Financial opportunity\n')
    runner=CliRunner()
    printed=runner.invoke(a.main,['--print-sql']);assert printed.exit_code==0 and not calls
    assert 'selected_aged_keys' in printed.output and 'PARSE_JSON' not in printed.output
    for args in [['--write-latex'],['--cached','--write-latex']]:
        result=runner.invoke(a.main,args);assert result.exit_code==0,result.output
    assert len(calls)==1
    d=next((tmp_path/'data/opportunity/new-upload-customer-follow-up').glob('*'))
    manifest=json.loads((d/'analysis.json').read_text())
    assert manifest['identity']['cohort_exports'] and manifest['audit']['cohort_customers']==1
    summary=pd.read_parquet(d/'summary.parquet');assert summary.followup_days.tolist()==list(range(7,71,7))
    report=next((tmp_path/'outputs').rglob('new-upload-customers-same-part-pet-follow-up.md')).read_text()
    assert 'subsequent aged orders do not reset' in report and 'PRODUCT_PART_NUMBER' in report
    latex=(appendix/'financial_opportunity_new_upload_follow_up.tex').read_text()
    assert r'\label{tab:financial-opportunity-new-upload-follow-up}' in latex and r'\caption{' in latex
    assert 'May 1, 2026 through July 31, 2026' in latex and '2026-10-28 00:00 UTC' in latex
    assert '70 & 1 & 100.00' in latex
    body=parent.read_text();include=r'\input{appendix/financial_opportunity_new_upload_follow_up_same_part_pet}'
    assert body.count(include)==1
    assert body.index('financial_opportunity_reorders')<body.index(include)<body.index('financial_opportunity_chewy_follow_up') and 'SQL for Table' not in body
    (d/'source.parquet').write_bytes(b'broken')
    result=runner.invoke(a.main,['--cached']);assert result.exit_code!=0 and 'fingerprint differs' in result.output


def test_incomplete_followup_rejected_before_query_or_cohort():
    result=CliRunner().invoke(a.main,['--as-of-date','2026-10-01','--print-sql'])
    assert result.exit_code!=0 and 'complete 70-day' in result.output

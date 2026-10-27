"""Prior history, customer grain, nested categories and reproducible extraction."""
import json
from unittest.mock import patch

from click.testing import CliRunner
import duckdb
import pandas as pd
import pytest

from src.python import create_aged_customer_prior_shipped_prescriptions as analysis
from tests.test_aged_order_all_contact_cancellation_distribution import fixtures as cohort_fixtures

START,END,ASOF='2026-08-15','2026-10-15','2026-10-27'


def fixtures():
    a,_=cohort_fixtures()
    a.loc[a.order_id.eq(103),['customer_id','rx_customer_id']]=3
    extra=a.iloc[[0]].assign(rx_id='r7',customer_id=4,rx_customer_id=4,
        order_id=104,first_order_id=104,order_line_id=6,first_order_line_id=6,first_orderitem_id='6')
    a=pd.concat([a,extra],ignore_index=True)
    rows=[]
    def add(order,customer,vet=False,source='OTHER',merch='Pharmacy',time='2026-08-10',**extra):
        row=dict(order_id=order,order_line_id=1,rx_id=f'h{order}',shipment_customer_id=customer,
            customer_variants=1,shipped_at_utc=time,shipment_rows=2,rx_customer_id=customer,
            rx_source_rows=1,is_vet_diet_flag=vet,prescription_source=source,merch_class2=merch)
        rows.append(dict(row,**extra))
    add(200,1,True,'CMPU','Prescription Food & Treats')
    add(201,1)
    add(202,2,merch='Compound')
    add(203,3,True,merch='Prescription Food & Treats')
    add(204,4,time='2026-09-01')
    add(205,4,rx_id=None,rx_source_rows=0,rx_customer_id=None)
    add(206,4,rx_customer_id=9)
    add(100,1,True,'CMPU','Prescription Food & Treats')
    add(101,1,True,'CMPU','Prescription Food & Treats')
    add(207,2,merch='Over the Counter')
    add(208,4,merch=None)
    return a,pd.DataFrame(rows,columns=analysis.HISTORY)


def summarize(a,h):
    return analysis.summarize(a,h,START,END,ASOF)


def test_customer_denominator_nested_flags_evidence_and_reference_orders():
    a,h=fixtures();out=summarize(a,h)
    assert out['summary'].customers.tolist()==[4,3,2,1]
    assert out['summary'].percent_of_aged_customers.tolist()==[100,75,50,25]
    assert out['exclusive-groups'].customers.tolist()==[1,1,1,1]
    assert len(out['reference-orders'])==5  # Two tied reference orders for customer 1.
    assert out['shipment-evidence'].loc[lambda f:f.order_id.isin([100,101]),'eligibility'].eq('Reference order').all()
    status=out['shipment-evidence'].set_index('order_id').eligibility
    assert status[204]=='At/after reference cancellation'
    assert status[205]=='Missing RX_ID' and status[206]=='RX/customer mismatch'
    assert out['customers'].customer_id.is_unique
    assert out['categories'].set_index('category').loc['Over the Counter','customers']==1
    assert out['categories'].set_index('category').loc['Other/unclassified','customers']==1
    assert len(out['associations'])==7


def test_earliest_cancellation_strict_nanoseconds_and_historical_dates():
    a,h=fixtures();a.loc[a.order_id.eq(101),'order_cancel_time']='2026-09-10'
    h=h.loc[~h.order_id.isin([100,101])].copy()
    # History after the first cancellation must not qualify using a later cancellation.
    h.loc[h.order_id.eq(200),'shipped_at_utc']='2026-09-02'
    h.loc[h.order_id.eq(201),'shipped_at_utc']='2026-09-01 00:00:00.000000001'
    assert summarize(a,h)['customers'].set_index('customer_id').loc[1,analysis.FLAGS].eq(False).all()
    h.loc[h.order_id.eq(200),'shipped_at_utc']='2026-08-31 23:59:59.999999999'
    assert summarize(a,h)['summary'].customers.tolist()==[4,3,2,1]
    h.loc[h.order_id.eq(200),'shipped_at_utc']='2019-01-01'
    assert summarize(a,h)['history-coverage'].earliest_observed_candidate_shipment_utc.iloc[0]==pd.Timestamp('2019-01-01',tz='UTC')


def test_every_aged_cancelled_order_is_excluded_even_on_another_line_before_reference():
    a,h=fixtures()
    # Order 101 is a later aged cancellation, not one of the earliest reference orders.
    a.loc[a.order_id.eq(101),'order_cancel_time']='2026-09-10'
    h=h.loc[h.shipment_customer_id.eq(1) & h.order_id.isin([100,101])].copy()
    h.loc[h.order_id.eq(101),'order_line_id']=999
    out=summarize(a,h)
    evidence=out['shipment-evidence'].set_index('order_id')
    assert evidence.loc[100,'eligibility']=='Reference order'
    assert evidence.loc[101,'eligibility']=='Other aged-cancelled order'
    assert evidence.is_aged_cancelled_order.all()
    assert not evidence.loc[101,'is_reference_order']
    assert not out['customers'][analysis.FLAGS].any().any()
    # A genuinely different order with earlier shipment still counts.
    other=h.iloc[[0]].assign(order_id=9999,rx_id='different-order')
    assert summarize(a,pd.concat([h,other]))['summary'].customers.tolist()==[4,1,1,1]


@pytest.mark.parametrize('case',['duplicate-line','source-customer','duplicate-rx','cross-rx-customer'])
def test_source_conflicts_rejected(case):
    a,h=fixtures()
    if case=='duplicate-line':h=pd.concat([h,h.iloc[[0]]],ignore_index=True)
    if case=='source-customer':h.loc[0,'customer_variants']=2
    if case=='duplicate-rx':h.loc[0,'rx_source_rows']=2
    if case=='cross-rx-customer':h=pd.concat([h,h.iloc[[0]].assign(rx_id='different',shipment_customer_id=2)],ignore_index=True)
    with pytest.raises(ValueError):summarize(a,h)


def test_empty_missing_and_unknown_history_preserves_denominators():
    a,h=fixtures()
    assert summarize(a,h.iloc[:0])['summary'].customers.tolist()==[4,0,0,0]
    empty=summarize(a.iloc[:0],h.iloc[:0])
    assert empty['summary'].customers.tolist()==[0,0,0,0]
    h['shipped_at_utc']=None
    assert summarize(a,h)['summary'].customers.tolist()==[4,0,0,0]
    h['shipped_at_utc']='2026-08-10';h['rx_source_rows']=0
    assert summarize(a,h)['summary'].customers.tolist()==[4,0,0,0]


def test_actual_sql_customer_discovery_shipment_collapse_and_both_cohort_keys():
    a,h=fixtures()
    prescriptions=a[['rx_id','rx_customer_id','first_order_id','first_orderitem_id','rx_creation_datetime']].rename(columns={'rx_customer_id':'customer_id'})
    prescriptions=prescriptions.assign(prescription_source='CMPU',is_vet_diet_flag=True,approval_channel='CUSTOMER_UPLOAD',merch_class2='Prescription Food & Treats')
    historical=h.loc[h.rx_id.notna(),['rx_id','rx_customer_id','is_vet_diet_flag','prescription_source','merch_class2']].rename(columns={'rx_customer_id':'customer_id'})
    prescriptions=pd.concat([prescriptions,historical],ignore_index=True)
    prescriptions['rx_creation_datetime']=pd.to_datetime(prescriptions.rx_creation_datetime)
    lines=a[['order_id','order_line_id','customer_id','order_cancel_reason','order_cancel_time']].drop_duplicates().rename(columns={'order_cancel_time':'order_cancel_dttm'})
    lines['rx_id']=None;lines['order_line_shipped_dttm']=None
    shipped=h[['order_id','order_line_id','rx_id','shipment_customer_id','shipped_at_utc']].rename(columns={
        'shipment_customer_id':'customer_id','shipped_at_utc':'order_line_shipped_dttm'})
    # Historical source lines on reference orders use their original keys, preventing order customer conflicts.
    shipped=shipped.loc[~shipped.order_id.isin([100,101])]
    shipped=pd.concat([shipped,shipped],ignore_index=True)
    lines=pd.concat([lines,shipped],ignore_index=True)
    for col in ['order_line_shipped_dttm','order_cancel_dttm']:lines[col]=pd.to_datetime(lines[col])
    wrong=prescriptions.iloc[[0]].assign(rx_id='wrong',first_orderitem_id='999')
    outside=prescriptions.iloc[[0]].assign(rx_id='outside',rx_creation_datetime=pd.Timestamp(END))
    prescriptions=pd.concat([prescriptions,wrong,outside],ignore_index=True)
    sql=analysis.render_sql(START,END,ASOF).split('), records AS (')[0]+') SELECT * FROM '
    sql=sql.replace('EDLDB.BT_HCA_HCDM.RXP_PRESCRIPTIONS','rx_source').replace(
        'EDLDB.BT_HCA_HCDM.ORDER_LINE_COST_MEASURES_RXP','line_source').replace('TIMESTAMP_NTZ','TIMESTAMP_NS')
    sql=sql.replace('TRY_TO_NUMBER(first_orderitem_id)','TRY_CAST(first_orderitem_id AS BIGINT)')
    with duckdb.connect() as con:
        con.register('rx_source',prescriptions);con.register('line_source',lines)
        con.execute('CREATE MACRO IFF(x,y,z) AS IF(x,y,z)')
        con.execute('CREATE MACRO REGEXP_LIKE(x,y) AS REGEXP_FULL_MATCH(x,y)')
        con.execute('CREATE MACRO TO_CHAR(x,f) AS CAST(x AS VARCHAR)')
        associations=con.execute(sql+'associations').df();history=con.execute(sql+'history').df()
    assert 'outside' not in set(associations.rx_id)
    assert associations.loc[associations.rx_id.eq('wrong'),'order_id'].isna().all()
    assert history.shipment_rows.eq(2).all()
    assert 204 not in set(history.order_id)  # Exactly at cancellation is excluded in SQL.
    assert summarize(associations,history)['summary'].customers.tolist()==[4,3,2,1]


def source():
    a,h=fixtures()
    return pd.DataFrame([dict(record_type=kind,payload=json.dumps(row),extraction_warehouse='TEST')
        for kind,frame in [('association',a),('shipment',h)]
        for row in json.loads(frame.to_json(orient='records'))])


def test_fresh_cached_sql_only_and_fingerprints(tmp_path):
    runner=CliRunner();args=['--start-date',START,'--end-date',END,'--as-of-date',ASOF]
    with patch.object(analysis,'ROOT',tmp_path):
        with patch.object(analysis.subprocess,'run') as execute:
            result=runner.invoke(analysis.main,args+['--print-sql'])
            assert result.exit_code==0,result.output
            assert 'historical_lines' in result.output
            assert not list(tmp_path.iterdir());execute.assert_not_called()
        def extract(command,**kwargs):
            assert '/src/autogenerated/' in command[2]
            source().to_parquet(tmp_path/command[command.index('--output-parquet')+1],index=False)
        with patch.object(analysis.subprocess,'run',side_effect=extract):
            result=runner.invoke(analysis.main,args)
            assert result.exit_code==0,result.output
        with patch.object(analysis.subprocess,'run') as execute:
            result=runner.invoke(analysis.main,args+['--cached'])
            assert result.exit_code==0,result.output
            execute.assert_not_called()
        assert all(p.stat().st_size<=1_000_000 for p in tmp_path.rglob('*.md'))
        manifest=next((tmp_path/'data').rglob('source.json'));meta=json.loads(manifest.read_text())
        original=meta.copy();meta['sql_sha256']='bad';manifest.write_text(json.dumps(meta))
        result=runner.invoke(analysis.main,args+['--cached'])
        assert result.exit_code!=0 and 'fingerprint' in result.output
        manifest.write_text(json.dumps(original));parquet=manifest.with_name('source.parquet')
        parquet.write_bytes(parquet.read_bytes()+b'changed')
        assert runner.invoke(analysis.main,args+['--cached']).exit_code!=0

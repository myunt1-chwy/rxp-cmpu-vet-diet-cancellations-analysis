"""Full cohort before placement: all channels, unknown references and excluded orders."""
import json
from unittest.mock import patch

from click.testing import CliRunner
import duckdb
import pandas as pd
import pytest

from src.python import create_cmpu_customer_prior_shipped_prescriptions as analysis
from tests.test_aged_customer_prior_shipped_prescriptions import fixtures as aged_fixtures

START,END,ASOF='2026-08-15','2026-10-15','2026-10-27'


def fixtures():
    a,h=aged_fixtures()
    a=a.assign(approval_channel='CUSTOMER_UPLOAD',order_placed_time='2026-08-20',
        order_placed_eastern='2026-08-19 20:00:00',placed_variants=1,eastern_variants=1)
    a.loc[a.rx_customer_id.eq(4),'approval_channel']='VERBAL'
    return a[analysis.ASSOCIATIONS],h


def summarize(a,h,channel='ALL'):
    return analysis.summarize(a,h,START,END,ASOF,channel)


def test_full_cohort_deduplication_all_channels_and_prior_distribution():
    a,h=fixtures();out=summarize(a,h)
    assert out['summary'].customers.tolist()==[4,4,3,2,1]
    assert len(out['customers'])==4 and out['customers'].customer_id.is_unique
    assert out['customers'].assessable.all()
    assert out['exclusive-groups'].customers.sum()==4
    assert len(out['orders'])==5
    assert len(out['associations'])==7
    assert out['shipment-evidence'].loc[lambda d:d.order_id.isin([100,101]),'eligibility'].eq('Analysed cohort order').all()
    assert out['customers'].reference_placed_time.eq(pd.Timestamp('2026-08-20',tz='UTC')).all()


def test_before_placement_not_cancellation_and_exclude_every_cohort_order_line():
    a,h=fixtures()
    # A shipment between placement and cancellation would qualify in REFNUM 35, but not here.
    h.loc[h.order_id.eq(200),'shipped_at_utc']='2026-08-25'
    assert summarize(a,h)['summary'].customers.tolist()==[4,4,3,1,0]
    # Earliest among a customer's multiple orders, regardless of which one later aged/reordered.
    a.loc[a.order_id.eq(101),'order_placed_time']='2026-08-25'
    a.loc[a.order_id.eq(101),'order_placed_eastern']='2026-08-24 20:00:00'
    h.loc[h.order_id.eq(201),'shipped_at_utc']='2026-08-22'
    out=summarize(a,h)
    assert out['customers'].set_index('customer_id').loc[1,'prior_inclusive_pharmacy']==False
    h.loc[h.order_id.eq(101),'order_line_id']=999
    assert summarize(a,h)['shipment-evidence'].loc[lambda d:d.order_id.eq(101),'eligibility'].eq('Analysed cohort order').all()


@pytest.mark.parametrize('offset,qualifies',[(-1,True),(0,False),(1,False)])
def test_strict_nanosecond_placement_boundary(offset,qualifies):
    a,h=fixtures();h=h.iloc[[0]].copy()
    h['shipped_at_utc']=(pd.Timestamp('2026-08-20',tz='UTC')+pd.Timedelta(nanoseconds=offset)).isoformat()
    assert summarize(a,h)['customers'].set_index('customer_id').loc[1,'prior_cmpu_vet_diet']==qualifies


@pytest.mark.parametrize('case',['missing-key','missing-placement','mismatch','future-placement'])
def test_unknown_reference_is_not_no_history_and_does_not_shift_to_another_order(case):
    a,h=fixtures();mask=a.order_id.eq(101)
    if case=='missing-key':
        a.loc[mask,'first_order_id']=None
        a.loc[mask,analysis.ASSOCIATIONS[8:]]=None
    if case=='missing-placement':a.loc[mask,['order_placed_time','order_placed_eastern']]=None
    if case=='mismatch':a.loc[mask,'customer_id']=99
    if case=='future-placement':
        a.loc[mask,'order_placed_time']='2026-10-28'
        a.loc[mask,'order_placed_eastern']='2026-10-27 20:00:00'
    out=summarize(a,h);customer=out['customers'].set_index('customer_id').loc[1]
    assert not customer.assessable and pd.isna(customer.reference_placed_time)
    assert customer[analysis.FLAGS].isna().all()
    assert customer.history_group=='Unknown reference placement'
    assert out['summary'].customers.tolist()==[4,3,2,1,0]
    assert out['exclusive-groups'].customers.sum()==4


@pytest.mark.parametrize('case',['join','duplicate-rx','timestamp-conflict','eastern','line-conflict','historical-customer'])
def test_conflicts_rejected(case):
    a,h=fixtures()
    if case=='join':a.loc[0,'first_order_id']=999
    if case=='duplicate-rx':a.loc[1,'rx_id']=a.loc[0,'rx_id']
    if case=='timestamp-conflict':a.loc[0,'placed_variants']=2
    if case=='eastern':a.loc[0,'order_placed_eastern']='2026-08-20'
    if case=='line-conflict':
        a.loc[0,'order_placed_time']='2026-08-21';a.loc[0,'order_placed_eastern']='2026-08-20 20:00:00'
    if case=='historical-customer':h.loc[0,'customer_variants']=2
    with pytest.raises(ValueError):summarize(a,h)


def test_empty_cohort_history_and_channel_validation():
    a,h=fixtures()
    assert summarize(a,h.iloc[:0])['summary'].customers.tolist()==[4,4,0,0,0]
    assert summarize(a.iloc[:0],h.iloc[:0])['summary'].customers.tolist()==[0,0,0,0,0]
    with pytest.raises(ValueError,match='channel'):summarize(a,h,'CUSTOMER_UPLOAD')
    with pytest.raises(ValueError):analysis.render_sql(START,END,ASOF,"ALL'; SELECT 1")


def test_actual_sql_all_statuses_channels_keys_and_historical_candidates():
    a,h=fixtures()
    rx=a[['rx_id','rx_customer_id','approval_channel','first_order_id','first_orderitem_id','rx_creation_datetime']].rename(columns={'rx_customer_id':'customer_id'})
    rx=rx.assign(prescription_source='CMPU',is_vet_diet_flag=True,merch_class2='Prescription Food & Treats')
    hist=h.loc[h.rx_id.notna(),['rx_id','rx_customer_id','is_vet_diet_flag','prescription_source','merch_class2']].rename(columns={'rx_customer_id':'customer_id'})
    rx=pd.concat([rx,hist],ignore_index=True);rx['rx_creation_datetime']=pd.to_datetime(rx.rx_creation_datetime)
    lines=a[['order_id','order_line_id','customer_id','order_placed_time','order_placed_eastern']].drop_duplicates().rename(columns={
        'order_placed_time':'order_placed_dttm','order_placed_eastern':'order_placed_dttm_est'})
    lines['rx_id']=None;lines['order_line_shipped_dttm']=None
    shipped=h[['order_id','order_line_id','rx_id','shipment_customer_id','shipped_at_utc']].rename(columns={
        'shipment_customer_id':'customer_id','shipped_at_utc':'order_line_shipped_dttm'})
    lines=pd.concat([lines,lines,shipped,shipped],ignore_index=True)
    for col in ['order_placed_dttm','order_placed_dttm_est','order_line_shipped_dttm']:lines[col]=pd.to_datetime(lines[col])
    sql=analysis.render_sql(START,END,ASOF).split('), records AS (')[0]+') SELECT * FROM '
    sql=sql.replace('EDLDB.BT_HCA_HCDM.RXP_PRESCRIPTIONS','rx_source').replace(
        'EDLDB.BT_HCA_HCDM.ORDER_LINE_COST_MEASURES_RXP','line_source').replace('TIMESTAMP_NTZ','TIMESTAMP_NS')
    sql=sql.replace('TRY_TO_NUMBER(first_orderitem_id)','TRY_CAST(first_orderitem_id AS BIGINT)')
    with duckdb.connect() as con:
        con.register('rx_source',rx);con.register('line_source',lines)
        con.execute('CREATE MACRO IFF(x,y,z) AS IF(x,y,z)')
        con.execute('CREATE MACRO REGEXP_LIKE(x,y) AS REGEXP_FULL_MATCH(x,y)')
        con.execute('CREATE MACRO TO_CHAR(x,f) AS CAST(x AS VARCHAR)')
        associations=con.execute(sql+'associations').df();history=con.execute(sql+'history').df()
        refs=con.execute(sql+'customers').df()
    assert len(refs)==4 and len(associations)==7
    assert history.shipment_rows.eq(2).all()
    assert not history.order_id.isin(a.first_order_id).any()
    assert summarize(associations,history)['summary'].customers.tolist()==[4,4,3,2,1]


def source():
    a,h=fixtures()
    return pd.DataFrame([dict(record_type=kind,payload=json.dumps(row),extraction_warehouse='TEST')
        for kind,frame in [('association',a),('shipment',h)]
        for row in json.loads(frame.to_json(orient='records'))])


def test_modes_exports_and_cache_fingerprints(tmp_path):
    runner=CliRunner()
    with patch.object(analysis,'ROOT',tmp_path):
        with patch.object(analysis.subprocess,'run') as execute:
            result=runner.invoke(analysis.main,['--print-sql'])
            assert result.exit_code==0,result.output
            execute.assert_not_called();assert not list(tmp_path.iterdir())
        def extract(command,**kwargs):
            assert '/src/autogenerated/' in command[2]
            source().to_parquet(tmp_path/command[command.index('--output-parquet')+1],index=False)
        with patch.object(analysis.subprocess,'run',side_effect=extract):
            result=runner.invoke(analysis.main,[])
            assert result.exit_code==0,result.output
        with patch.object(analysis.subprocess,'run') as execute:
            assert runner.invoke(analysis.main,['--cached']).exit_code==0
            execute.assert_not_called()
        assert all(p.stat().st_size<=1_000_000 for p in tmp_path.rglob('*.md'))
        manifest=next((tmp_path/'data').rglob('source.json'));original=json.loads(manifest.read_text())
        changed=dict(original,approval_channel='CUSTOMER_UPLOAD');manifest.write_text(json.dumps(changed))
        result=runner.invoke(analysis.main,['--cached'])
        assert result.exit_code!=0 and 'fingerprint' in result.output
        manifest.write_text(json.dumps(original));p=manifest.with_name('source.parquet');p.write_bytes(p.read_bytes()+b'changed')
        assert runner.invoke(analysis.main,['--cached']).exit_code!=0

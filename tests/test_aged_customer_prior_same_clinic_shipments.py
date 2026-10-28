"""Same-clinic prior experience: exact timing, customer grain, missingness and source SQL."""
import json
from unittest.mock import patch

from click.testing import CliRunner
import duckdb
import pandas as pd
import pytest

from src.python import create_aged_customer_prior_same_clinic_shipments as analysis
from tests.test_aged_customer_prior_shipped_prescriptions import fixtures as prior_fixtures

START,END,ASOF='2026-08-15','2026-10-15','2026-10-27'


def fixtures():
    a,h=prior_fixtures()
    a=a.assign(aged_clinic_id=a.customer_id*10,prescription_clinic_id=999,line_clinic_variants=1,order_placed_time='2026-08-20',
        order_placed_eastern='2026-08-19 20:00:00',placed_variants=1,eastern_variants=1)
    h=h.loc[~h.order_id.isin([205,206,208])].copy()
    h['history_clinic_id']=99.
    h.loc[h.order_id.isin([200,100,101]),'history_clinic_id']=10
    h.loc[h.order_id.eq(203),'history_clinic_id']=None
    h.loc[h.order_id.eq(204),'history_clinic_id']=40
    h['history_clinic_variants']=h.history_clinic_id.notna().astype(int)
    h['prescription_history_clinic_id']=888
    return a[analysis.ASSOCIATIONS],h[analysis.HISTORY]


def summarize(a,h):return analysis.summarize(a,h,START,END,ASOF)


def test_customer_groups_reference_dedup_and_other_clinic_history():
    a,h=fixtures();out=summarize(a,h)
    assert out['summary'].customers.tolist()==[1,1,1,1]
    assert out['summary'].percent_of_all_customers.eq(25).all()
    assert out['customers'].customer_id.is_unique and len(out['customers'])==4
    assert out['customers'].set_index('customer_id').group.to_dict()==dict(zip([1,2,3,4],
        [analysis.GROUPS[0],analysis.GROUPS[1],analysis.GROUPS[3],analysis.GROUPS[2]]))
    assert len(out['aged-orders'])==5 and len(out['aged-order-clinic-references'])==7
    assert out['shipment-evidence'].loc[lambda d:d.order_id.isin([100,101]),'eligibility'].eq('Aged-cancelled order').all()
    assert out['summary'].percent_of_assessable_customers.iloc[:3].sum()==pytest.approx(100)
    assert out['unknown-reasons'].set_index('reason').loc['Missing historical clinic ID','customers']==1
    assert out['clinic-coverage'].set_index('scope').loc['Aged-order prescription references','with_clinic_id']==7


def test_any_aged_clinic_and_its_own_placement_not_customer_earliest_or_cancellation():
    a,h=fixtures();h=h.loc[h.order_id.eq(200)].copy()
    a.loc[a.order_id.eq(101),'aged_clinic_id']=20
    a.loc[a.order_id.eq(101),'order_placed_time']='2026-08-25'
    a.loc[a.order_id.eq(101),'order_placed_eastern']='2026-08-24 20:00:00'
    h['history_clinic_id']=20;h['shipped_at_utc']='2026-08-24'
    out=summarize(a,h)
    assert out['customers'].set_index('customer_id').loc[1,'has_prior_same_clinic']
    assert set(out['aged-order-clinic-references'].loc[lambda d:d.same_clinic_prior_shipment,'order_id'])=={101}
    h['shipped_at_utc']='2026-08-26'  # Before cancellation but after both order placements.
    assert not summarize(a,h)['customers'].has_prior_same_clinic.any()


def test_prescription_clinics_do_not_override_the_shared_order_line_clinic():
    a,h=fixtures();a.loc[a.rx_id.eq('r2'),'prescription_clinic_id']=20
    h=h.loc[h.order_id.eq(200)].copy()
    out=summarize(a,h)
    refs=out['aged-order-clinic-references']
    assert set(refs.loc[refs.order_id.eq(100)&refs.order_line_id.eq(1),'aged_clinic_id'])=={10}
    assert out['customers'].set_index('customer_id').loc[1,'has_prior_same_clinic']
    # Prescription fields match, but the line clinic does not: no same-clinic match is allowed.
    h['history_clinic_id']=99
    h['prescription_history_clinic_id']=999
    assert not summarize(a,h)['customers'].has_prior_same_clinic.any()


@pytest.mark.parametrize('ns,expected',[(-1,True),(0,False),(1,False)])
def test_strict_nanosecond_cutoff(ns,expected):
    a,h=fixtures();h=h.loc[h.order_id.eq(200)].copy()
    h['shipped_at_utc']=(pd.Timestamp('2026-08-20',tz='UTC')+pd.Timedelta(nanoseconds=ns)).isoformat()
    assert summarize(a,h)['customers'].set_index('customer_id').loc[1,'has_prior_same_clinic']==expected


def test_same_clinic_different_customer_does_not_match_and_pet_product_are_unrestricted():
    a,h=fixtures();h=h.loc[h.order_id.eq(200)].copy()
    h['shipment_customer_id']=2;h['rx_customer_id']=2
    assert not summarize(a,h)['customers'].has_prior_same_clinic.any()
    h['shipment_customer_id']=1;h['rx_customer_id']=1
    h['pet_id']=999;h['product_id']=123  # These do not constrain the relationship metric.
    assert summarize(a,h)['customers'].set_index('customer_id').loc[1,'has_prior_same_clinic']


@pytest.mark.parametrize('case',['aged-clinic','placement','aged-customer','history-clinic','history-customer','unmatched-rx','missing-rx'])
def test_unknown_information_is_not_a_negative_match(case):
    a,h=fixtures();h=h.loc[h.order_id.eq(200)].copy()
    if case=='aged-clinic':
        a.loc[a.customer_id.eq(1),'aged_clinic_id']=None;a.loc[a.customer_id.eq(1),'line_clinic_variants']=0
    if case=='placement':a.loc[a.customer_id.eq(1),['order_placed_time','order_placed_eastern']]=None
    if case=='aged-customer':a.loc[a.customer_id.eq(1),'rx_customer_id']=99
    if case=='history-clinic':h['history_clinic_id']=None;h['history_clinic_variants']=0
    if case=='history-customer':h['rx_customer_id']=99
    if case=='unmatched-rx':h['rx_source_rows']=0
    if case=='missing-rx':h['rx_id']=None;h['rx_source_rows']=0
    row=summarize(a,h)['customers'].set_index('customer_id').loc[1]
    assert row.group=='Unknown' and not row.has_prior_same_clinic
    assert row.unknown_reasons


def test_positive_match_takes_precedence_and_null_clinic_ids_never_match():
    a,h=fixtures();a.loc[a.order_id.eq(101),'aged_clinic_id']=None;a.loc[a.order_id.eq(101),'line_clinic_variants']=0
    extra=h.iloc[[0]].assign(order_id=999,rx_id='unknown',history_clinic_id=None,history_clinic_variants=0)
    out=summarize(a,pd.concat([h,extra],ignore_index=True))
    row=out['customers'].set_index('customer_id').loc[1]
    assert row.has_prior_same_clinic and row.group==analysis.GROUPS[0]
    assert row.quality_reasons and not row.unknown_reasons
    a.loc[a.customer_id.eq(1),'aged_clinic_id']=None;a.loc[a.customer_id.eq(1),'line_clinic_variants']=0
    h=h.loc[h.order_id.eq(200)].copy();h['history_clinic_id']=None;h['history_clinic_variants']=0
    assert not summarize(a,h)['customers'].has_prior_same_clinic.any()


def test_aged_order_exclusion_covers_other_lines_and_other_aged_orders():
    a,h=fixtures();h=h.loc[h.order_id.isin([100,101])].copy()
    h['order_line_id']=999
    assert not summarize(a,h)['customers'].has_prior_same_clinic.any()


@pytest.mark.parametrize('case',['duplicate-rx','duplicate-history','customer-variants','history-registry','placement-variants','eastern','aged-clinic-variants','history-clinic-variants'])
def test_conflicting_sources_rejected(case):
    a,h=fixtures()
    if case=='duplicate-rx':a.loc[1,'rx_id']=a.loc[0,'rx_id']
    if case=='duplicate-history':h=pd.concat([h,h.iloc[[0]]])
    if case=='customer-variants':h.loc[h.order_id.eq(200),'customer_variants']=2
    if case=='history-registry':h.loc[h.order_id.eq(200),'rx_source_rows']=2
    if case=='placement-variants':a.loc[0,'placed_variants']=2
    if case=='eastern':a.loc[0,'order_placed_eastern']='2026-08-20'
    if case=='aged-clinic-variants':a.loc[0,'line_clinic_variants']=2
    if case=='history-clinic-variants':h.loc[h.order_id.eq(200),'history_clinic_variants']=2
    with pytest.raises(ValueError):summarize(a,h)


def test_empty_population_history_and_missing_shipment_times():
    a,h=fixtures()
    assert summarize(a,h.iloc[:0])['summary'].customers.tolist()==[0,0,4,0]
    assert summarize(a.iloc[:0],h.iloc[:0])['summary'].customers.tolist()==[0,0,0,0]
    h['shipped_at_utc']=None
    assert summarize(a,h)['summary'].customers.tolist()==[0,0,4,0]


def test_actual_sql_two_keys_dedup_clinic_fields_cutoff_and_excluded_orders():
    a,h=fixtures()
    rx=a[['rx_id','rx_customer_id','prescription_clinic_id','first_order_id','first_orderitem_id','rx_creation_datetime']].rename(columns={'rx_customer_id':'customer_id','prescription_clinic_id':'clinic_id'})
    rx=rx.assign(prescription_source='CMPU',is_vet_diet_flag=True,approval_channel='CUSTOMER_UPLOAD',merch_class2='Prescription Food & Treats')
    hist=h.loc[h.rx_id.notna(),['rx_id','rx_customer_id','prescription_history_clinic_id','prescription_source','is_vet_diet_flag','merch_class2']].rename(columns={'rx_customer_id':'customer_id','prescription_history_clinic_id':'clinic_id'})
    rx=pd.concat([rx,hist],ignore_index=True);rx['rx_creation_datetime']=pd.to_datetime(rx.rx_creation_datetime)
    lines=a[['order_id','order_line_id','customer_id','order_cancel_reason','order_cancel_time','order_placed_time','order_placed_eastern','aged_clinic_id']].drop_duplicates().rename(columns={'order_cancel_time':'order_cancel_dttm','order_placed_time':'order_placed_dttm','order_placed_eastern':'order_placed_dttm_est','aged_clinic_id':'clinic_id'})
    lines['rx_id']=None;lines['order_line_shipped_dttm']=None
    shipped=h.loc[~h.order_id.isin([100,101]),['order_id','order_line_id','rx_id','shipment_customer_id','shipped_at_utc','history_clinic_id']].rename(columns={'shipment_customer_id':'customer_id','shipped_at_utc':'order_line_shipped_dttm','history_clinic_id':'clinic_id'})
    lines=pd.concat([lines,lines,shipped,shipped],ignore_index=True)
    for col in ['order_cancel_dttm','order_placed_dttm','order_placed_dttm_est','order_line_shipped_dttm']:lines[col]=pd.to_datetime(lines[col])
    sql=analysis.render_sql(START,END,ASOF).split('), records AS (')[0]+') SELECT * FROM '
    sql=sql.replace('EDLDB.BT_HCA_HCDM.RXP_PRESCRIPTIONS','rx_source').replace('EDLDB.BT_HCA_HCDM.ORDER_LINE_COST_MEASURES_RXP','line_source').replace('TIMESTAMP_NTZ','TIMESTAMP_NS')
    sql=sql.replace('TRY_TO_NUMBER(first_orderitem_id)','TRY_CAST(first_orderitem_id AS BIGINT)')
    with duckdb.connect() as con:
        con.register('rx_source',rx);con.register('line_source',lines)
        con.execute('CREATE MACRO IFF(x,y,z) AS IF(x,y,z)')
        con.execute('CREATE MACRO REGEXP_LIKE(x,y) AS REGEXP_FULL_MATCH(x,y)')
        con.execute('CREATE MACRO TO_CHAR(x,f) AS CAST(x AS VARCHAR)')
        associations=con.execute(sql+'associations').df();history=con.execute(sql+'history').df()
    assert len(associations)==len(a)
    assert history.shipment_rows.eq(2).all()
    assert not history.order_id.isin(a.order_id).any()
    assert set(history.history_clinic_id.dropna())=={10,99}
    assert summarize(associations,history)['summary'].customers.tolist()==[1,1,1,1]


def source():
    a,h=fixtures()
    return pd.DataFrame([dict(record_type=kind,payload=json.dumps(row),extraction_warehouse='TEST')
        for kind,frame in [('association',a),('shipment',h)] for row in json.loads(frame.to_json(orient='records'))])


def test_modes_fingerprints_and_bounded_exports(tmp_path):
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
            result=runner.invoke(analysis.main,['--cached'])
            assert result.exit_code==0,result.output
            execute.assert_not_called()
        assert all(p.stat().st_size<=1_000_000 for p in tmp_path.rglob('*.md'))
        manifest=next((tmp_path/'data').rglob('source.json'));original=json.loads(manifest.read_text())
        assert original['clinic_source']==analysis.CLINIC_SOURCE
        assert 'order-line-clinic' in str(manifest)
        manifest.write_text(json.dumps(dict(original,clinic_source='EDLDB.BT_HCA_HCDM.RXP_PRESCRIPTIONS.CLINIC_ID')))
        assert runner.invoke(analysis.main,['--cached']).exit_code!=0
        manifest.write_text(json.dumps(dict(original,sql_sha256='bad')))
        result=runner.invoke(analysis.main,['--cached'])
        assert result.exit_code!=0 and 'fingerprint' in result.output
        manifest.write_text(json.dumps(original));p=manifest.with_name('source.parquet');p.write_bytes(p.read_bytes()+b'changed')
        assert runner.invoke(analysis.main,['--cached']).exit_code!=0


def test_clinic_results_use_clinic_names_without_changing_prescription_category_fields():
    a,h=fixtures();outputs=analysis.summarize(a,h,START,END,ASOF)
    assert outputs['summary'].customers.tolist()==[1,1,1,1]
    assert outputs['summary'].group.tolist()==analysis.GROUPS
    assert 'aged-order-clinic-references' in outputs and 'customer-clinic-history' in outputs
    for frame in outputs.values():
        assert not any('vet_id' in column for column in frame.columns)
    assert 'is_vet_diet_flag' in outputs['shipment-evidence']
    assert outputs['shipment-evidence'].merch_class2.equals(h.merch_class2)
    assert outputs['unknown-reasons'].reason.tolist()==['Missing historical clinic ID']
    assert outputs['customers'].customer_id.is_unique

def test_any_aged_clinic_and_no_prescription_fallback():
    a,h=fixtures();h=h.loc[h.order_id.eq(200)].copy()
    a.loc[a.order_id.eq(101),'aged_clinic_id']=20
    a.loc[a.order_id.eq(101),'order_placed_time']='2026-08-25'
    a.loc[a.order_id.eq(101),'order_placed_eastern']='2026-08-24 20:00:00'
    h['history_clinic_id']=20;h['shipped_at_utc']='2026-08-24'
    out=analysis.summarize(a,h,START,END,ASOF)
    assert out['customers'].set_index('customer_id').loc[1,'has_prior_same_clinic']
    h['history_clinic_id']=None;h['history_clinic_variants']=0
    h['prescription_history_clinic_id']=20
    out=analysis.summarize(a,h,START,END,ASOF)
    assert out['customers'].set_index('customer_id').loc[1,'group']=='Unknown'
    assert not out['customers'].has_prior_same_clinic.any()

def test_actual_sql_uses_line_clinic_not_prescription_clinic():
    a,h=fixtures()
    rx=a[['rx_id','rx_customer_id','prescription_clinic_id','first_order_id','first_orderitem_id','rx_creation_datetime']].rename(columns={'rx_customer_id':'customer_id','prescription_clinic_id':'clinic_id'})
    rx=rx.assign(prescription_source='CMPU',is_vet_diet_flag=True,approval_channel='CUSTOMER_UPLOAD',merch_class2='Prescription Food & Treats')
    hist=h[['rx_id','rx_customer_id','prescription_history_clinic_id','prescription_source','is_vet_diet_flag','merch_class2']].rename(columns={'rx_customer_id':'customer_id','prescription_history_clinic_id':'clinic_id'})
    rx=pd.concat([rx,hist],ignore_index=True);rx['rx_creation_datetime']=pd.to_datetime(rx.rx_creation_datetime)
    lines=a[['order_id','order_line_id','customer_id','order_cancel_reason','order_cancel_time','order_placed_time','order_placed_eastern','aged_clinic_id']].drop_duplicates().rename(columns={
        'order_cancel_time':'order_cancel_dttm','order_placed_time':'order_placed_dttm',
        'order_placed_eastern':'order_placed_dttm_est','aged_clinic_id':'clinic_id'})
    lines['rx_id']=None;lines['order_line_shipped_dttm']=None
    shipped=h.loc[~h.order_id.isin([100,101]),['order_id','order_line_id','rx_id','shipment_customer_id','shipped_at_utc','history_clinic_id']].rename(columns={
        'shipment_customer_id':'customer_id','shipped_at_utc':'order_line_shipped_dttm','history_clinic_id':'clinic_id'})
    lines=pd.concat([lines,lines,shipped,shipped],ignore_index=True)
    for col in ['order_cancel_dttm','order_placed_dttm','order_placed_dttm_est','order_line_shipped_dttm']:lines[col]=pd.to_datetime(lines[col])
    sql=analysis.render_sql(START,END,ASOF)
    assert 'l.clinic_id' in sql and 'l.vet_id' not in sql and 'r.vet_id' not in sql
    sql=sql.split('), records AS (')[0]+') SELECT * FROM '
    sql=sql.replace('EDLDB.BT_HCA_HCDM.RXP_PRESCRIPTIONS','rx_source').replace('EDLDB.BT_HCA_HCDM.ORDER_LINE_COST_MEASURES_RXP','line_source').replace('TIMESTAMP_NTZ','TIMESTAMP_NS')
    sql=sql.replace('TRY_TO_NUMBER(first_orderitem_id)','TRY_CAST(first_orderitem_id AS BIGINT)')
    with duckdb.connect() as con:
        con.register('rx_source',rx);con.register('line_source',lines)
        con.execute('CREATE MACRO IFF(x,y,z) AS IF(x,y,z)')
        con.execute('CREATE MACRO REGEXP_LIKE(x,y) AS REGEXP_FULL_MATCH(x,y)')
        con.execute('CREATE MACRO TO_CHAR(x,f) AS CAST(x AS VARCHAR)')
        associations=con.execute(sql+'associations').df();history=con.execute(sql+'history').df()
    assert set(history.history_clinic_id.dropna())=={10,99}
    assert set(history.prescription_history_clinic_id.dropna())=={888}
    assert analysis.summarize(associations,history,START,END,ASOF)['summary'].customers.tolist()==[1,1,1,1]

def test_fresh_cached_sql_only_separate_clinic_source_fingerprint_and_exports(tmp_path):
    runner=CliRunner()
    with patch.object(analysis,'ROOT',tmp_path):
        with patch.object(analysis.subprocess,'run') as execute:
            result=runner.invoke(analysis.main,['--print-sql'])
            assert result.exit_code==0,result.output
            assert 'l.clinic_id' in result.output
            execute.assert_not_called();assert not list(tmp_path.iterdir())
        def extract(command,**kwargs):
            assert '/src/autogenerated/' in command[2]
            source().to_parquet(tmp_path/command[command.index('--output-parquet')+1],index=False)
        with patch.object(analysis.subprocess,'run',side_effect=extract):
            result=runner.invoke(analysis.main,[])
            assert result.exit_code==0,result.output
        with patch.object(analysis.subprocess,'run') as execute:
            result=runner.invoke(analysis.main,['--cached'])
            assert result.exit_code==0,result.output
            execute.assert_not_called()
        manifest=next((tmp_path/'data').rglob('source.json'));meta=json.loads(manifest.read_text())
        assert meta['clinic_source'].endswith('.CLINIC_ID')
        assert 'order-line-clinic' in str(manifest)
        assert all(p.stat().st_size<=1_000_000 for p in tmp_path.rglob('*.md'))
        manifest.write_text(json.dumps(dict(meta,clinic_source='wrong')))
        assert runner.invoke(analysis.main,['--cached']).exit_code!=0

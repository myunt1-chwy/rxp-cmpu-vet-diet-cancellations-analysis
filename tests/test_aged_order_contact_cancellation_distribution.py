"""Signed contact timing, exact daily bins, all cohorts, and reproducible exports."""
import json
from unittest.mock import patch

from click.testing import CliRunner
import pandas as pd
import pytest

from src.python import create_aged_order_contact_cancellation_distribution as analysis
from src.python import create_aged_order_reorder_wismo as contacts_analysis
from tests.test_aged_order_reorder_wismo import fixtures as contact_fixtures, execute_sql


def fixtures():
    selected,intervals,contacts=contact_fixtures()
    output=contacts_analysis.summarize(selected,intervals,execute_sql(intervals,contacts,all_order_history=True),'UTC',all_order_history=True)
    return contacts_analysis.contact_columns(output['selected-customers'],True),output['contact-interval-associations']


def test_all_horizons_counts_negative_and_positive_times_missing_and_no_contacts():
    selected,contacts=fixtures();outputs=analysis.summarize(selected,contacts)
    assert len(outputs['contact-details'])==27
    for row in outputs['summary'].itertuples():
        assert row.reordered_customers==2 and row.customers_with_contacts==1 and row.customers_without_contacts==1
        assert row.contact_legs==9 and row.dated_contact_legs==8 and row.undated_contact_legs==1
        assert (row.contacts_before_cancellation,row.contacts_at_cancellation,row.contacts_after_cancellation)==(1,1,6)
        bins=outputs['daily-bins'].loc[lambda d:d.followup_days.eq(row.followup_days)]
        assert bins.set_index('relative_day').contact_legs.to_dict()=={-1:1,0:5,1:2}
        assert bins.share_of_dated_contacts.sum()==1
    events=outputs['contact-details']
    assert events.loc[events.missing_contact_time,'relative_day'].isna().all()
    assert not events.original_customer_id.eq(2).any()


def test_nanosecond_floor_boundaries_and_common_complete_axes():
    selected,contacts=fixtures();cancel=selected.order_cancel_time.iloc[0]
    values=[-analysis.DAY_NS-1,-analysis.DAY_NS,-1,0,analysis.DAY_NS-1,analysis.DAY_NS,3*analysis.DAY_NS]
    sample=contacts.iloc[[0]].copy()
    contacts=pd.concat([sample.assign(leg_id=str(i),contact_at_utc=cancel+pd.Timedelta(nanoseconds=value)) for i,value in enumerate(values)],ignore_index=True)
    selected.loc[selected.original_customer_id.eq(1),'contact_count']=len(values)
    outputs=analysis.summarize(selected,contacts)
    for days in analysis.HORIZONS:
        bins=outputs['daily-bins'].loc[lambda d:d.followup_days.eq(days)]
        assert bins.relative_day.tolist()==[-2,-1,0,1,2,3]
        assert bins.contact_legs.tolist()==[1,2,2,1,0,1]
        assert bins.lower_hours.tolist()==[-48,-24,0,24,48,72]
    assert outputs['contact-details'].loc[lambda d:d.followup_days.eq(7)].relative_day.tolist()==[-2,-1,-1,0,0,1,3]


def test_duplicate_leg_rows_follow_count_star_and_are_not_silently_deduplicated():
    selected,contacts=fixtures()
    contacts=pd.concat([contacts,contacts.iloc[[0]]],ignore_index=True)
    selected.loc[selected.original_customer_id.eq(1),'contact_count']+=1
    outputs=analysis.summarize(selected,contacts)
    assert outputs['summary'].contact_legs.eq(10).all()
    assert len(outputs['contact-details'].source_contact_row.unique())==len(contacts)


@pytest.mark.parametrize('case',['duplicate-customer','wrong-total','wrong-order','extra-request','unhandled','missing-cancel'])
def test_invalid_grain_source_counts_and_keys_rejected(case):
    selected,contacts=fixtures()
    if case=='duplicate-customer':selected=pd.concat([selected,selected.iloc[[0]]])
    if case=='wrong-total':selected.loc[0,'contact_count']=99
    if case=='wrong-order':contacts.loc[0,'order_id']=999
    if case=='extra-request':contacts.loc[0,'request_id']=999
    if case=='unhandled':contacts.loc[0,'handled_flag']=False
    if case=='missing-cancel':selected.loc[0,'order_cancel_time']=pd.NaT
    with pytest.raises(ValueError):analysis.summarize(selected,contacts)


def test_no_dated_contacts_and_no_population_are_retained():
    selected,contacts=fixtures();contacts['contact_at_utc']=None
    outputs=analysis.summarize(selected,contacts)
    assert outputs['summary'].undated_contact_legs.eq(9).all()
    assert outputs['daily-bins'].contact_legs.eq(0).all()
    assert outputs['daily-bins'].relative_day.eq(0).all()
    empty=analysis.summarize(selected.iloc[:0],contacts.iloc[:0])
    assert empty['summary'].reordered_customers.eq(0).all()
    assert empty['daily-bins'].share_of_dated_contacts.eq(0).all()


def test_chart_spec_is_a_histogram_with_vertical_bars_zero_baseline_and_common_scales(tmp_path):
    selected,contacts=fixtures();outputs=analysis.summarize(selected,contacts)
    meta=dict(start_date='2026-08-15',end_date_exclusive='2026-10-15',as_of_date='2026-10-27')
    specs=[]
    def inspect(chart,*args,**kwargs):specs.append(chart.to_dict())
    with patch('altair.vegalite.v6.api.LayerChart.save',inspect):
        for summary in outputs['summary'].itertuples(index=False):analysis.figure(outputs['daily-bins'],summary,meta,tmp_path/'figure.png')
    domains=[]
    for spec in specs:
        bars=spec['layer'][0]
        assert bars['mark']=={'type':'bar','orient':'vertical'}
        assert bars['encoding']['y2']['datum']==0
        assert spec['config']['background']=='transparent'
        domains.append((bars['encoding']['x']['scale']['domain'],bars['encoding']['y']['scale']['domain']))
    assert domains[0]==domains[1]==domains[2]


def test_cli_exports_and_fingerprints_without_database_access(tmp_path):
    selected,contacts=fixtures()
    meta=dict(start_date='2026-08-15',end_date_exclusive='2026-10-15',as_of_date='2026-10-27',
        parquet_sha256='source',extracted_at_utc='now',dependencies={'baseline':'frozen'})
    period='2026-08-15_2026-10-15_customer_upload_same-pet_reorders-7d-14d-21d_as-of-2026-10-27'
    def render(bins,summary,metadata,path):path.write_bytes(b'png')
    with patch.object(analysis,'ROOT',tmp_path),patch.object(analysis,'load_inputs',return_value=(selected,contacts,meta,period)), \
         patch.object(analysis,'figure',side_effect=render):
        result=CliRunner().invoke(analysis.main,[])
        assert result.exit_code==0,result.output
        assert len(list((tmp_path/'outputs/charts/2026-08-15_2026-10-14').glob('*.png')))==3
        assert len(list((tmp_path/'outputs/tables/2026-08-15_2026-10-14').glob('*.md')))==3
        manifest=json.loads(next((tmp_path/'data').rglob('manifest.json')).read_text())
        assert manifest['contact_time_scope']=='all-order-history' and manifest['contact_source_sha256']=='source'
        for file,sha in manifest['files'].items():assert analysis.digest(tmp_path/file)==sha


def test_inputs_revalidate_frozen_sources_and_require_all_history_cache():
    selected,contacts=fixtures()
    frozen=selected.drop(columns='request_id')
    source_meta=dict(parquet_sha256='contact-source',dependencies={'baseline':'b','prescription_channels':'rx'})
    with patch.object(analysis.sankeys.windows,'load_source',return_value=(pd.DataFrame(),{'parquet_sha256':'b'},'period')) as baseline, \
         patch.object(analysis.sankeys.windows,'summarize',return_value={'associations':pd.DataFrame()}), \
         patch.object(analysis.sankeys,'select_customers',return_value=pd.DataFrame()), \
         patch.object(analysis.sankeys,'load_source',return_value=(pd.DataFrame(),{'parquet_sha256':'rx'},None)) as rx, \
         patch.object(analysis.sankeys,'summarize',return_value=(frozen,None)), \
         patch.object(analysis.contacts_analysis,'load_source',return_value=(pd.DataFrame(),source_meta,None)) as source, \
         patch.object(analysis.contacts_analysis,'summarize',return_value={'selected-customers':selected,'contact-interval-associations':contacts}):
        analysis.load_inputs('2026-08-15','2026-10-15','2026-10-27')
        assert baseline.call_args.args[-1] is True and rx.call_args.args[-1] is True
        assert source.call_args.args[-1] is True
        assert source.call_args.kwargs=={'all_contacts':True,'all_order_history':True}
        source.side_effect=ValueError('fingerprint differs')
        with pytest.raises(ValueError,match='fingerprint differs'):analysis.load_inputs('2026-08-15','2026-10-15','2026-10-27')

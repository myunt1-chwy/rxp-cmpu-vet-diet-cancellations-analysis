"""Known-answer survival examples, censoring boundaries, audits and exports."""
import json
from unittest.mock import patch

from click.testing import CliRunner
import numpy as np
import pandas as pd
import pytest

from src.python import create_cmpu_first_order_line_survival as survival

ORIGIN = pd.Timestamp('2026-08-15', tz='UTC')
CUTOFF = pd.Timestamp('2026-10-26', tz='UTC')


def lines(days=(1,2,2,3), censored=(False,False,True,False)):
    # Censored lines have no event and enter at cutoff minus their follow-up duration.
    frame = pd.DataFrame([dict(order_id=100, order_line_id=i,
        order_placed_utc=CUTOFF-pd.Timedelta(days=d) if c else ORIGIN,
        event_time=pd.NaT if c else ORIGIN+pd.Timedelta(days=d),
        event_time_source='missing' if c else 'actual_upload')
        for i,(d,c) in enumerate(zip(days,censored))])
    for col in ['order_placed_utc','event_time']:
        frame[col]=pd.to_datetime(frame[col],utc=True).astype('datetime64[ns, UTC]')
    return frame


def test_known_answer_tied_event_and_censoring():
    obs=survival.observations(lines(),CUTOFF)
    curve=survival.kaplan_meier(obs)
    assert curve.elapsed_days.tolist()==[1,2,3]
    assert curve.at_risk.tolist()==[4,3,1]
    assert curve.events.tolist()==[1,1,1]
    assert curve.censored.tolist()==[0,1,0]
    assert curve.survival_probability.tolist()==[.75,.5,0]
    assert np.all(curve.ci95_lower<=curve.survival_probability)
    assert np.all(curve.survival_probability<=curve.ci95_upper)
    assert curve.ci95_lower.iloc[1]==pytest.approx(.05784708,abs=1e-7)
    assert curve.ci95_upper.iloc[1]==pytest.approx(.84486128,abs=1e-7)
    risk=survival.risk_table(obs,curve)
    assert risk.at_risk.tolist()==[4,4,1]
    assert risk.cumulative_events.tolist()==[0,1,3]


def test_zero_time_events_and_all_events_equals_empirical_survival():
    obs=survival.observations(lines((0,1,1,2),(False,)*4),CUTOFF)
    curve=survival.kaplan_meier(obs)
    assert curve.elapsed_days.tolist()==[0,1,2]
    assert curve.survival_probability.tolist()==[.75,.25,0]
    assert curve.at_risk.tolist()==[4,3,1]


def test_all_censored_and_empty():
    obs=survival.observations(lines((1,2),(True,True)),CUTOFF)
    curve=survival.kaplan_meier(obs)
    assert curve.survival_probability.eq(1).all()
    assert curve.ci95_lower.eq(1).all() and curve.ci95_upper.eq(1).all()
    assert curve.events.sum()==0 and curve.censored.sum()==2
    assert survival.kaplan_meier(obs.iloc[:0]).empty
    assert survival.risk_table(obs.iloc[:0],curve).empty


def test_cutoff_negative_missing_placement_and_sources():
    frame=lines((1,1,1,1,1,1,1,1),(False,)*8)
    frame.loc[0,'event_time']=CUTOFF
    frame.loc[1,'event_time']=CUTOFF+pd.Timedelta(nanoseconds=1)
    frame.loc[2,'event_time']=ORIGIN-pd.Timedelta(nanoseconds=1)
    frame.loc[3,'order_placed_utc']=pd.NaT
    frame.loc[4,['order_placed_utc','event_time']]=[CUTOFF+pd.Timedelta(days=1),pd.NaT]
    frame.loc[5,'event_time']=pd.NaT
    frame.loc[6,'event_time_source']='order_cancellation'
    frame.loc[7,'event_time_source']='tie'
    obs=survival.observations(frame,CUTOFF)
    assert obs.survival_eligibility.tolist()==['Included','Included','Negative event duration',
        'Missing placement','Placement after cutoff','Included','Included','Included']
    assert obs.loc[0,'event_observed'] and not obs.loc[1,'event_observed']
    assert obs.loc[0,'observation_end_utc']==obs.loc[1,'observation_end_utc']==CUTOFF
    assert obs.loc[5,'survival_outcome']=='Censored: missing event'
    assert obs.loc[6:7,'event_observed'].all()
    assert obs.loc[2:4,'duration_ns'].isna().all()
    assert obs.event_time.equals(frame.event_time)
    assert survival.kaplan_meier(obs).events.sum()==3


def test_fractional_nanoseconds_remain_distinct():
    frame=lines((0,0),(False,False))
    frame.loc[0,'event_time']=ORIGIN+pd.Timedelta(nanoseconds=12)
    frame.loc[1,'event_time']=ORIGIN+pd.Timedelta(nanoseconds=13)
    curve=survival.kaplan_meier(survival.observations(frame,CUTOFF))
    assert curve.duration_ns.tolist()==[12,13]
    assert curve.survival_probability.tolist()==[.5,0]


def test_invalid_input_keys_and_cutoff():
    frame=lines()
    with pytest.raises(ValueError,match='timezone'):
        survival.observations(frame,'2026-10-26')
    with pytest.raises(ValueError,match='unique'):
        survival.observations(pd.concat([frame,frame.iloc[[0]]]),CUTOFF)
    with pytest.raises(ValueError,match='populated'):
        survival.observations(frame.assign(order_id=None),CUTOFF)


def metadata():
    return dict(start_date='2026-08-15',end_date_exclusive='2026-10-15',upload_start_date='2026-08-01',
        upload_end_date_exclusive='2026-10-26',extracted_at_utc='2026-10-27T00:00:00Z',
        parquet_sha256='sourcefingerprint',sql_sha256='sqlfingerprint')


def test_exports_cli_and_no_eligible_chart_cleanup(tmp_path):
    m=metadata()
    period='2026-08-15_2026-10-15_uploads-2026-08-01_2026-10-26_accepted-state-change_order-placed'
    associations=pd.DataFrame({'association_state':['Matched']*4+['Missing order ID']})
    def render(curve,n,path,subtitle):
        path.write_bytes(b'png')
    with patch.object(survival,'ROOT',tmp_path), patch.object(survival,'figure',side_effect=render) as figure:
        audit,path=survival.write_outputs(lines(),associations,m,period)
        assert path.is_file() and path.parent.name=='2026-08-15_2026-10-14'
        tables=list((tmp_path/'outputs/tables/2026-08-15_2026-10-14').glob('*.md'))
        assert len(tables)==4 and all('uploads-2026-08-01_2026-10-26' in p.name for p in tables)
        note=path.with_suffix('.md').read_text()
        assert 'pointwise 95%' in note and '0.96' in note and 'Unmatched prescription associations' in note
        manifest=json.loads(next((tmp_path/'data').rglob('manifest.json')).read_text())
        assert manifest['source_parquet_sha256']==m['parquet_sha256']
        for name,sha in manifest['files'].items():
            assert survival.digest(next((tmp_path/'data').rglob(name)))==sha
        figure.assert_called_once()
        audit,path=survival.write_outputs(lines().iloc[:0],associations,m,period)
        assert not path.exists()
        assert 'No eligible lines' in path.with_suffix('.md').read_text()
    with patch.object(survival.events,'load_source') as load, patch.object(survival.events,'validate') as validate, \
            patch.object(survival,'write_outputs',return_value=(pd.DataFrame(),tmp_path/'curve.png')):
        load.return_value=(pd.DataFrame(),m,period)
        validate.return_value=(associations,lines(),pd.DataFrame())
        result=CliRunner().invoke(survival.main,[])
        assert result.exit_code==0,result.output
        load.assert_called_once_with('2026-08-15','2026-10-15','2026-08-01',cached=True)


def test_estimator_disagreement_is_rejected():
    with patch.object(survival,'SurvfuncRight') as estimator:
        estimator.return_value.surv_times=np.array([999])
        with pytest.raises(ValueError,match='reconcile'):
            survival.kaplan_meier(survival.observations(lines(),CUTOFF))


def test_cutoff_cannot_exceed_source_observation(tmp_path):
    with patch.object(survival,'ROOT',tmp_path):
        with pytest.raises(ValueError,match='later than source extraction'):
            survival.write_outputs(lines(),pd.DataFrame(),
                {**metadata(),'extracted_at_utc':'2026-10-25T00:00:00Z'},'unused')


def test_png_geometry_is_bounded_and_retains_endpoints(tmp_path):
    count=10_000
    curve=pd.DataFrame(dict(duration_ns=np.arange(count),elapsed_days=np.linspace(0,1,count),
        at_risk=count-np.arange(count),events=1,censored=0,
        survival_probability=np.linspace(1,0,count),ci95_lower=np.linspace(1,0,count),
        ci95_upper=np.linspace(1,0,count)))
    with patch.object(survival.alt.LayerChart,'save',autospec=True) as save:
        survival.figure(curve,count,tmp_path/'chart.png',['test'])
        spec=save.call_args.args[0].to_dict()
        values=spec.get('data', spec['layer'][0].get('data', {}))['values']
        assert len(values)<=4602
        assert values[0]['survival_probability']==1
        assert values[-1]['survival_probability']==0
        assert values[-1]['elapsed_days']==1
        assert spec['config']['background']=='transparent'
        assert spec['layer'][1]['mark']['interpolate']=='step-after'

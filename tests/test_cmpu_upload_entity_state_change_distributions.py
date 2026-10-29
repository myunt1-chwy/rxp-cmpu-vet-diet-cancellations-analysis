import json
from unittest.mock import patch

from click.testing import CliRunner
import duckdb
import pandas as pd
import pytest

from src.python import create_cmpu_upload_entity_state_change_distributions as a
from src.python import create_cmpu_first_order_line_event_times as events
from tests.test_cmpu_first_order_line_event_times import execute

DATES = ('2026-08-15', '2026-10-15', '2026-08-01', '2026-10-27')
PARAMS = a.parameters(*DATES)


def sources():
    p = pd.DataFrame([dict(rx_id=f'R{i}', customer_id=7, rx_creation_datetime=pd.Timestamp('2026-08-15'),
        prescription_source='CMPU', is_vet_diet_flag=True, approval_channel='CUSTOMER_UPLOAD',
        first_order_id=100+i, first_orderitem_id=str(i)) for i in range(4)])
    l = pd.DataFrame([dict(order_id=100+i, order_line_id=i, order_placed_dttm=pd.Timestamp('2026-08-01'),
        order_placed_dttm_est=pd.Timestamp('2026-07-31 20:00'), order_cancel_reason=' Aged Order ',
        order_cancel_dttm=pd.Timestamp('2026-10-27')+pd.Timedelta(nanoseconds=i-1)) for i in range(4)])
    u = pd.DataFrame([dict(upload_id=f'U{i}', customer_id='007', rx_id='{R'+str(i)+'}',
        upload_type='DIET_PRESCRIPTION', state_name=['ACCEPTED','REJECTED',None,'PENDING'][i],
        created_ts_utc=pd.Timestamp('2026-08-01'),
        state_changed_ts_utc=pd.Timestamp('2026-11-01') if i != 3 else pd.NaT) for i in range(4)])
    return p, l, u


def query(p, l, u):
    with patch.object(events, 'render_sql', return_value=a.render_sql(*DATES)):
        return execute(p, l, u)


def result(p=None, l=None, u=None):
    defaults = sources()
    return a.validate(query(*[x if x is not None else y for x,y in zip([p,l,u],defaults)]), PARAMS)


def test_multiple_rx_every_upload_duplicate_sources_and_inclusive_aged_cutoff():
    p,l,u = sources()
    u.loc[0,'rx_id'] = '{R0,R0,R2}'
    u = pd.concat([u, u.iloc[[0]], u.iloc[[0]].assign(upload_id='EXTRA')])
    l = pd.concat([l,l.iloc[[0]]])
    associations, entities, audit = result(p,l,u)
    assert len(entities) == 5 and entities.upload_id.is_unique
    assert len(associations) == 7
    assert entities.set_index('upload_id').matched_prescriptions['U0'] == 2
    assert set(entities.loc[entities.aged_entity,'upload_id']) == {'U0','U1','EXTRA'}
    assert set(entities.state_name.dropna()) == {'ACCEPTED','REJECTED','PENDING'}
    assert entities.loc[entities.upload_id.eq('U0'),'elapsed_hours'].iloc[0] == 24*92
    assert audit.set_index('measure')['count']['identical source/expansion rows collapsed'] > 0


def test_both_first_order_keys_channel_customer_and_expanded_rx_matching():
    p,l,u = sources()
    l.order_id += 1  # Line IDs alone cannot match.
    assert not result(p,l,u)[1].aged_entity.any()
    p,l,u = sources()
    l.order_line_id += 1  # Order IDs alone cannot match.
    assert not result(p,l,u)[1].aged_entity.any()
    u = pd.concat([u,u.iloc[[0]].assign(upload_id='WRONGCUSTOMER',customer_id='8'),
        u.iloc[[0]].assign(upload_id='BADNUM',customer_id='7.0'),
        u.iloc[[0]].assign(upload_id='BADRX',rx_id='{R!0}'),
        u.iloc[[0]].assign(upload_id='OTHER',upload_type='DRUG_PRESCRIPTION')])
    p.loc[1,'approval_channel'] = 'CLINIC'
    assert set(result(p,l,u)[1].upload_id) == {'U0','U2','U3'}


def test_upload_boundaries_unknown_creation_negative_and_missing_duration():
    p,l,u = sources()
    base=u.iloc[[0]]
    u=pd.concat([base.assign(upload_id='BEFORE',created_ts_utc=pd.Timestamp('2026-07-31 23:59:59.999999999')),
        base.assign(upload_id='START',created_ts_utc=pd.Timestamp('2026-08-01'), state_changed_ts_utc=pd.Timestamp('2026-07-31 23:59:59')),
        base.assign(upload_id='LAST',created_ts_utc=pd.Timestamp('2026-10-25 23:59:59.999999999')),
        base.assign(upload_id='END',created_ts_utc=pd.Timestamp('2026-10-26')),
        base.assign(upload_id='UNKNOWN',created_ts_utc=pd.NaT),
        base.assign(upload_id='MISSING',state_changed_ts_utc=pd.NaT)])
    _,e,_=result(p,l,u)
    assert set(e.upload_id)=={'START','LAST','UNKNOWN','MISSING'}
    e=e.set_index('upload_id')
    assert e.loc['START','negative_duration'] and e.loc['START','usable_duration']
    assert e.loc['START','elapsed_hours']==-1/3600
    assert e.loc['UNKNOWN','unknown_discovery_window'] and not e.loc['UNKNOWN','usable_duration']
    assert e.loc['MISSING','missing_state_change'] and not e.loc['MISSING','usable_duration']


@pytest.mark.parametrize('column,value', [('state_name','OTHER'),('state_name',None),
    ('created_ts_utc',pd.Timestamp('2026-07-01')),('state_changed_ts_utc',pd.Timestamp('2026-12-01')),
    ('state_changed_ts_utc',pd.NaT),('customer_id','8')])
def test_conflicting_entity_versions_cannot_hide_outside_window_or_customer_join(column,value):
    p,l,u=sources()
    u=pd.concat([u,u.iloc[[0]].assign(**{column:value})])
    with pytest.raises(ValueError,match='conflicting entity'):
        result(p,l,u)


def test_conflicting_line_source_values_rejected():
    p,l,u=sources()
    l=pd.concat([l,l.iloc[[0]].assign(order_cancel_dttm=pd.Timestamp('2026-10-28'))])
    with pytest.raises(ValueError,match='cancellation source'):
        result(p,l,u)


def test_quantiles_whiskers_null_state_singletons_and_empty_groups():
    _, e, _ = result()
    values=[-10,0,1,2,3,4,5,6,100]
    e=pd.concat([e.loc[e.state_label.eq('"ACCEPTED"')].assign(upload_id=str(i),elapsed_hours=v) for i,v in enumerate(values)])
    stats=a.statistics(e,['"ACCEPTED"','[NULL state]']).iloc[0]
    with duckdb.connect() as con:
        con.register('e',e)
        q=con.sql('SELECT quantile_cont(elapsed_hours,[0.25,0.5,0.75]) FROM e').fetchone()[0]
        lo,hi=con.execute('SELECT min(elapsed_hours),max(elapsed_hours) FROM e WHERE elapsed_hours BETWEEN ? AND ?',
            [q[0]-1.5*(q[2]-q[0]),q[2]+1.5*(q[2]-q[0])]).fetchone()
    assert [stats.q1,stats['median'],stats.q3]==q==[1,3,5]
    assert (stats.lower_whisker,stats.upper_whisker)==(lo,hi)==(0,6)
    assert stats.outliers==2
    spec=a.boxplot(e,a.statistics(e,['"ACCEPTED"']),['"ACCEPTED"'],[-11,110],'Test',[]).to_dict()
    assert len(spec['layer'][6]['data']['values'])==2
    _,original,_=result()
    singleton=a.statistics(original, sorted(original.state_label.unique()))
    assert singleton.entities.eq(1).all()
    assert singleton.loc[singleton.usable.eq(1),'q1'].equals(singleton.loc[singleton.usable.eq(1),'q3'])
    assert singleton.loc[singleton.state_label.eq('[NULL state]'),'usable'].iloc[0]==1
    assert a.statistics(original.iloc[:0],['EMPTY']).usable.iloc[0]==0


def test_exports_both_transparent_charts_shared_order_axis_and_all_outliers(tmp_path):
    f=query(*sources())
    metadata=dict(parameters=PARAMS,extracted_at_utc='test',parquet_sha256='test')
    a.write_outputs(f,metadata,tmp_path/'data',tmp_path/'charts',tmp_path/'tables')
    all_e=pd.read_parquet(tmp_path/'data/all-study-linked-entities.parquet')
    aged=pd.read_parquet(tmp_path/'data/aged-order-entities.parquet')
    assert set(aged.upload_id) <= set(all_e.upload_id) and len(all_e)==4 and len(aged)==2
    for population in a.POPULATIONS:
        png=(tmp_path/f'charts/{population}.png').read_bytes()
        assert png[:8]==b'\x89PNG\r\n\x1a\n' and png[25]==6  # RGBA
    manifest=json.loads((tmp_path/'data/analysis.json').read_text())
    assert manifest['symlog_constant_hours']==1/3600
    for path in (tmp_path/'tables').glob('*.md'):
        assert path.stat().st_size<=1_000_000
    chart=a.boxplot(all_e,a.statistics(all_e,manifest['shared_state_order']),manifest['shared_state_order'],
        manifest['shared_hours_domain'],'Test',[]).to_dict()
    assert chart['layer'][1]['encoding']['x']['scale']['type']=='symlog'
    assert chart['layer'][1]['encoding']['y']['sort']==manifest['shared_state_order']
    assert chart['config']['background']=='transparent'


def test_fresh_cached_fingerprint_rejection_and_sql_only(tmp_path, monkeypatch):
    monkeypatch.setattr(a,'ROOT',tmp_path)
    sql=a.render_sql(*DATES)
    frame=query(*sources())
    def extract(args,**kwargs):
        out=tmp_path/args[args.index('--output-parquet')+1]
        frame.to_parquet(out,index=False)
    with patch.object(a.subprocess,'run',side_effect=extract) as run:
        fresh,meta,directory,_=a.load_source(PARAMS,sql,False)
        cached,_,_,_=a.load_source(PARAMS,sql,True)
        assert run.call_count==1
    pd.testing.assert_frame_equal(fresh,cached)
    changed=fresh.copy()
    changed.loc[0,'state_name']='BAD'
    changed.to_parquet(directory/'source.parquet',index=False)
    with pytest.raises(ValueError,match='fingerprint'):
        a.load_source(PARAMS,sql,True)
    with patch.object(a,'load_source',side_effect=AssertionError('SQL-only performed I/O')):
        result=CliRunner().invoke(a.main,['--print-sql','--cached'])
    assert result.exit_code==0 and 'AS aged_association' in result.output


@pytest.mark.parametrize('dates',[('2026-10-15','2026-08-15','2026-08-01','2026-10-27'),
    ('2026-08-15','2026-10-15','2026-08-16','2026-10-27')])
def test_date_validation(dates):
    with pytest.raises(ValueError):
        a.parameters(*dates)


def test_all_null_states_timestamps_and_empty_population(tmp_path):
    p,l,u=sources()
    u=u.assign(state_name=None, created_ts_utc=pd.NaT, state_changed_ts_utc=pd.NaT)
    f=query(p,l,u)
    _,entities,_=a.validate(f,PARAMS)
    assert entities.state_label.eq('[NULL state]').all()
    assert not entities.usable_duration.any()
    metadata=dict(parameters=PARAMS,extracted_at_utc='test',parquet_sha256='test')
    for label,source in [('null',f),('empty',f.iloc[:0])]:
        a.write_outputs(source,metadata,tmp_path/label/'data',tmp_path/label/'charts',tmp_path/label/'tables')
        assert len(list((tmp_path/label/'charts').glob('*.png')))==2


def test_conflicting_prescription_values_and_missing_upload_id():
    p,l,u=sources()
    p=pd.concat([p,p.iloc[[0]].assign(first_order_id=999)])
    with pytest.raises(ValueError,match='prescription source'):
        result(p,l,u)
    p,l,u=sources()
    u.loc[0,'upload_id']=None
    with pytest.raises(ValueError,match='UPLOAD_ID'):
        result(p,l,u)

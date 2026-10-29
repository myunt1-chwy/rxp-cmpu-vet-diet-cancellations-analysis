import json
from unittest.mock import patch

from click.testing import CliRunner
import duckdb
import pandas as pd
import pytest

from src.python import create_cmpu_upload_entity_order_creation_distributions as a
from src.python import create_cmpu_first_order_line_event_times as events
from tests.test_cmpu_upload_entity_state_change_distributions import sources, DATES, PARAMS
from tests.test_cmpu_first_order_line_event_times import execute


def query(p,l,u):
    with patch.object(events,'render_sql',return_value=a.render_sql(*DATES)):
        return execute(p,l,u)


def test_real_sql_uses_placement_preserves_all_states_and_aged_cutoff():
    p,l,u=sources()
    l=l.assign(order_placed_dttm=pd.Timestamp('2026-08-01 01:00'),
        order_line_created_dttm=pd.Timestamp('2026-08-10'),order_line_created_dttm_est=pd.Timestamp('2026-08-09 20:00'))
    u.loc[1,'created_ts_utc']=pd.Timestamp('2026-08-01 03:00')
    u.loc[2,'created_ts_utc']=pd.Timestamp('2026-08-01 01:00')
    associations,entities,rows,stats,_=a.prepare(query(p,l,u),PARAMS)
    actual=entities.set_index('upload_id')
    assert actual.elapsed_hours.to_dict()=={'U0':-1.,'U1':2.,'U2':0.,'U3':-1.}
    assert actual.loc['U3','usable_duration']  # Missing state-change time is irrelevant.
    assert set(entities.loc[entities.aged_entity,'upload_id'])=={'U0','U1'}
    assert len(associations)==len(entities)==4 and len(rows)==6
    assert stats.set_index('population').usable.to_dict()=={'Overall':4,'Aged orders':2}


def test_multi_rx_multi_order_entities_keep_earliest_origin_and_same_aged_value():
    p,l,u=sources()
    u=u.iloc[[0]].assign(rx_id='{R0,R1,R0}')
    l.loc[0,'order_placed_dttm']=pd.Timestamp('2026-08-01 02:00')
    l.loc[1,'order_placed_dttm']=pd.Timestamp('2026-07-31 23:00')
    l.loc[1,'order_cancel_reason']='Other reason'
    l=pd.concat([l,l.iloc[[0]],l.iloc[[1]]])
    associations,entities,rows,stats,_=a.prepare(query(p,l,u),PARAMS)
    assert len(associations)==2 and len(entities)==1 and entities.multiple_orders.iloc[0]
    assert entities.elapsed_hours.iloc[0]==1
    assert entities.selected_order_id.iloc[0]==101
    assert rows.state_label.tolist()==a.GROUPS and rows.elapsed_hours.eq(1).all()
    assert stats.entities.eq(1).all()


def test_missing_origins_and_both_order_keys_excluded_only_from_plot():
    p,l,u=sources()
    l.loc[0,'order_placed_dttm']=pd.NaT
    p.loc[1,'first_order_id']=999
    p.loc[2,'first_orderitem_id']='999'
    u.loc[3,'created_ts_utc']=pd.NaT
    _,entities,_,stats,_=a.prepare(query(p,l,u),PARAMS)
    assert len(entities)==4 and not entities.usable_duration.any()
    assert stats.usable.eq(0).all()
    assert entities.missing_order_placement.sum()==3 and entities.missing_creation.sum()==1


@pytest.mark.parametrize('value',[pd.Timestamp('2026-08-02'),pd.NaT])
def test_conflicting_shipment_placement_rejected(value):
    p,l,u=sources()
    l=pd.concat([l,l.iloc[[0]].assign(order_placed_dttm=value)])
    with pytest.raises(ValueError,match='placement timestamps'):
        a.prepare(query(p,l,u),PARAMS)


def test_independent_quantiles_whiskers_and_all_outliers():
    p,l,u=sources()
    p=p.iloc[[0]]
    l=l.iloc[[0]].assign(order_placed_dttm=pd.Timestamp('2026-08-15'))
    base=u.iloc[[0]]
    values=[-10,0,1,2,3,4,5,6,100]
    u=pd.concat([base.assign(upload_id=str(i),created_ts_utc=pd.Timestamp('2026-08-15')+pd.Timedelta(hours=v)) for i,v in enumerate(values)])
    _,entities,rows,stats,_=a.prepare(query(p,l,u),PARAMS)
    with duckdb.connect() as con:
        con.register('e',entities)
        q=con.sql('SELECT quantile_cont(elapsed_hours,[0.25,0.5,0.75]) FROM e').fetchone()[0]
        whiskers=con.execute('SELECT min(elapsed_hours),max(elapsed_hours) FROM e WHERE elapsed_hours BETWEEN ? AND ?',
            [q[0]-1.5*(q[2]-q[0]),q[2]+1.5*(q[2]-q[0])]).fetchone()
    assert q==[1,3,5] and whiskers==(0,6)
    for r in stats.itertuples():
        assert [r.q1,r.median,r.q3]==q and (r.lower_whisker,r.upper_whisker)==whiskers and r.outliers==2
    spec=a.figure(rows,stats,PARAMS).to_dict()
    assert spec['layer'][1]['encoding']['y']['sort']==a.GROUPS
    assert spec['layer'][1]['encoding']['y']['title']=='Population'
    assert len(spec['layer'][6]['data']['values'])==4
    assert spec['config']['background']=='transparent'


def test_exports_stable_overwrite_empty_null_and_cache_modes(tmp_path,monkeypatch):
    frame=query(*sources())
    metadata=dict(parameters=PARAMS,extracted_at_utc='test',parquet_sha256='test')
    charts=tmp_path/'charts'
    charts.mkdir()
    (charts/'overall-and-aged-orders.png').write_bytes(b'stale figure')
    path,stats=a.write_outputs(frame,metadata,tmp_path/'exports',charts,tmp_path/'tables')
    assert path.name=='overall-and-aged-orders.png' and path.read_bytes()[:8]==b'\x89PNG\r\n\x1a\n'
    exported=pd.read_parquet(tmp_path/'exports/entities.parquet')
    assert exported.upload_id.is_unique and len(exported)==4
    assert not exported.loc[exported.upload_id.eq('U3'),'missing_order_placement'].iloc[0]
    for f in (tmp_path/'tables').glob('*.md'):
        assert f.stat().st_size<=1_000_000
    # Empty groups remain represented by zero counts in the same two-box layout.
    a.write_outputs(frame.iloc[:0],metadata,tmp_path/'empty',charts,tmp_path/'tables')
    assert len(list(charts.glob('*.png')))==1
    monkeypatch.setattr(a,'ROOT',tmp_path)
    sql=a.render_sql(*DATES)
    def extract(args,**kwargs):
        frame.to_parquet(tmp_path/args[args.index('--output-parquet')+1],index=False)
    with patch.object(a.subprocess,'run',side_effect=extract) as run:
        fresh,meta,directory=a.load_source(PARAMS,sql,False)
        cached,_,_=a.load_source(PARAMS,sql,True)
        assert run.call_count==1
    pd.testing.assert_frame_equal(fresh,cached)
    changed=fresh.copy()
    changed.loc[0,'order_placed_utc']='2026-08-20'
    changed.to_parquet(directory/'source.parquet',index=False)
    with pytest.raises(ValueError,match='fingerprint'):
        a.load_source(PARAMS,sql,True)
    with patch.object(a,'load_source',side_effect=AssertionError('SQL-only did I/O')):
        result=CliRunner().invoke(a.main,['--print-sql','--cached'])
    assert result.exit_code==0 and 'order_placed_utc' in result.output

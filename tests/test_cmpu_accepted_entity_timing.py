"""REFNUM 49: exercise real SQL selection and independent placement validation."""
from unittest.mock import patch

import pandas as pd
import pytest

from src.python import create_cmpu_first_order_line_event_times as events
from src.python import create_cmpu_first_order_line_approval_distribution as timing
from src.python import create_cmpu_first_order_line_survival as survival
from tests.test_cmpu_first_order_line_event_times import BASE, DATES, execute, sources


def test_earliest_accepted_entity_is_selected_by_creation_not_state_change():
    p,l,u=sources()
    original=u.iloc[[0]].assign(upload_id='LATER',state_changed_ts_utc=BASE+pd.Timedelta(hours=2))
    earlier=original.assign(upload_id='EARLIER',created_ts_utc=BASE+pd.Timedelta(hours=1),
                            state_changed_ts_utc=BASE+pd.Timedelta(days=80))
    rejected=original.assign(upload_id='REJECTED',created_ts_utc=BASE,state_name='REJECTED')
    unknown=original.assign(upload_id='UNKNOWN',created_ts_utc=BASE,state_name=None)
    a,lines,_=events.validate(execute(p,l,pd.concat([original,earlier,rejected,unknown])),*DATES)
    row=lines.loc[lines.order_line_id.eq(0)].iloc[0]
    assert a.loc[a.rx_id.eq('RX0'),'upload_count'].iloc[0]==2
    assert row.actual_upload_id=='EARLIER'
    assert row.actual_upload_time==pd.Timestamp(BASE+pd.Timedelta(days=80),tz='UTC')
    assert row.actual_upload_created_time==pd.Timestamp(BASE+pd.Timedelta(hours=1),tz='UTC')
    assert row.event_time_source=='order_cancellation'


def test_missing_state_change_keeps_accepted_entity_presence_and_estimation():
    p,l,u=sources()
    u=u.iloc[[0]].assign(state_changed_ts_utc=pd.NaT)
    a,lines,audit=events.validate(execute(p,l,u),*DATES)
    association=a.loc[a.rx_id.eq('RX0')].iloc[0]
    row=lines.loc[lines.order_line_id.eq(0)].iloc[0]
    assert association.upload_count==1 and pd.isna(association.association_upload_time)
    assert pd.isna(row.actual_upload_time) and row.missing_accepted_state_change
    assert row.candidate_upload_source=='estimated_upload'
    assert row.event_time_source=='order_cancellation'
    assert audit.loc[audit.measure.eq('missing_accepted_state_change'),'count'].iloc[0]==1


def test_tied_creation_selects_upload_id_and_uses_order_placement_for_event_and_survival():
    p,l,u=sources()
    l=l.assign(order_line_created_dttm=l.order_placed_dttm,
               order_line_created_dttm_est=l.order_placed_dttm_est)
    l.loc[0,'order_placed_dttm']=BASE-pd.Timedelta(hours=5)
    l.loc[0,'order_placed_dttm_est']=BASE-pd.Timedelta(hours=9)
    u=u.iloc[[0]].assign(upload_id='Z',state_changed_ts_utc=BASE+pd.Timedelta(hours=2))
    u=pd.concat([u,u.assign(upload_id='A',state_changed_ts_utc=BASE+pd.Timedelta(hours=10))])
    _,lines,_=events.validate(execute(p,l,u),*DATES)
    row=lines.loc[lines.order_line_id.eq(0)].iloc[0]
    assert row.actual_upload_id=='A' and row.elapsed_hours==15
    assert row.line_created_utc==pd.Timestamp(BASE,tz='UTC')
    assert row.estimated_upload_time==events.expected_estimate(row.order_placed_utc,row.min_approved_denied_datetime)
    observations=survival.observations(lines.loc[lines.order_line_id.eq(0)],pd.Timestamp('2026-10-26',tz='UTC'))
    assert observations.duration_ns.iloc[0]==15*3_600_000_000_000


def test_d_status_extract_uses_accepted_state_change_outside_discovery_window():
    p,l,u=sources()
    l=l.assign(max_approved_datetime=l.min_approved_denied_datetime)
    u=u.iloc[[0]].assign(state_changed_ts_utc=pd.Timestamp('2026-11-01'))
    sql=timing.render_sql(*DATES[:2],True,DATES[2])
    with patch.object(events,'render_sql',return_value=sql):
        frame=execute(p,l,u)
    selected=timing.upload_subset(frame,*DATES)
    details,_,_,_,_=timing.summarize(selected,*DATES[:2],endpoint='upload')
    assert details.upload_state_changed_at_utc.iloc[0]==pd.Timestamp('2026-11-01',tz='UTC')
    assert details.elapsed_hours.iloc[0]>24*60
    selected.loc[:,'selected_upload_state']='REJECTED'
    with pytest.raises(ValueError,match='accepted'):
        timing.upload_subset(selected,*DATES)


def test_status_presence_is_separate_from_state_time_and_exports_full_data(tmp_path):
    from src.python import create_cmpu_first_order_line_status as status
    from tests.test_cmpu_first_order_line_status import fixture
    f=fixture()
    f.loc[1,'upload_state_changed_at_utc']=pd.NaT
    f.loc[3,'upload_state_changed_at_utc']=pd.Timestamp('2026-12-01')
    _,lines,_,audit=status.summarize(f)
    assert lines.loc[1,'upload_group']=='Has matching accepted upload'
    assert pd.isna(lines.loc[1,'accepted_elapsed_hours'])
    assert lines.loc[3,'accepted_elapsed_hours']==24*91
    assert audit['missing_accepted_state_change']==1
    metadata=dict(start_date=DATES[0],end_date_exclusive=DATES[1],upload_start_date=DATES[2],
                  extracted_at_utc='fixture',parquet_sha256='fixture')
    with patch.object(status.legacy,'render_sankey'):
        status.write_outputs(f,metadata,tmp_path/'diagrams',tmp_path/'tables',data_dir=tmp_path/'data')
    exported=pd.read_parquet(tmp_path/'data/lines.parquet')
    assert len(exported)==5 and pd.isna(exported.loc[1,'accepted_elapsed_hours'])
    assert (tmp_path/'data/exports.json').is_file()
    f.loc[1,'selected_upload_state']='REJECTED'
    with pytest.raises(ValueError,match='accepted'):
        status.summarize(f)


def test_approval_and_gap_export_placement_relative_components():
    from tests.test_cmpu_first_order_line_approval_distribution import source
    f=source((10,)).assign(line_created_utc=pd.Timestamp('2026-08-15 15:00'),
                          upload_state_changed_at_utc=pd.Timestamp('2026-08-15 17:00'))
    details=timing.summarize(f,*DATES[:2])[0]
    assert details.elapsed_hours.iloc[0]==10
    assert details.accepted_elapsed_hours.iloc[0]==5
    gap=timing.summarize(f,*DATES[:2],endpoint='upload-to-approval')[0]
    assert gap.elapsed_hours.iloc[0]==gap.approval_elapsed_hours.iloc[0]-gap.accepted_elapsed_hours.iloc[0]==5

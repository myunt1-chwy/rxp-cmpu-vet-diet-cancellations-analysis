import json
from unittest.mock import patch

from click.testing import CliRunner
import pandas as pd
import pytest

from src.python import create_cmpu_first_order_line_status as analysis


def fixture():
    rows = []
    for i in range(5):
        rows.append(dict(rx_id=f'RX{i}', customer_id=1, rx_source_rows=1,
            rx_creation_datetime=pd.Timestamp('2026-09-01'), approval_channel='CUSTOMER_UPLOAD',
            first_order_id=10, first_orderitem_id=str(i), first_order_line_id=i,
            matched_order_id=10, matched_order_line_id=i, line_source_rows=3,
            duplicate_shipment_rows=0, order_status_variants=1, line_status_variants=1, cancel_reason_variants=1,
            order_status='D' if i else 'X', order_line_status='X' if i < 2 else 'D',
            order_item_block_reason='Clinic response' if i < 2 else None, block_reason_variants=1,
            order_status_description=None, order_cancel_reason='Aged Order' if i < 2 else None,
            upload_count=2 if i%2 else 0, cohort_window_upload_count=2 if i%2 else 0,
            first_upload_at_utc=pd.Timestamp('2026-09-02') if i%2 else pd.NaT,
            **{key: 0 for key in analysis.legacy.AUDIT_COLUMNS}))
    return pd.DataFrame(rows)


def test_line_grain_and_shipment_collapse():
    _, lines, groups, audit = analysis.summarize(fixture())
    assert len(lines) == groups.order_lines.sum() == 5
    assert audit['shipment_source_rows'] == 15
    assert audit['extra_shipment_rows_collapsed'] == 10
    assert audit['canceled_lines_on_uncanceled_orders'] == 1
    assert lines.order_group.tolist() == ['X','X','D','D','D']
    flows = analysis.flows_for_rendering(groups)
    assert flows.groupby('transition').prescriptions.sum().to_dict() == {1:5,2:5,3:5}
    assert abs(groups.percent_of_cohort.sum()-100) < 1e-9
    assert set(flows.loc[flows.transition.eq(1),'target']) == {
        'First order line status: X','First order line status: D'}


def test_line_status_ignores_cancel_reason_and_retains_raw_order_status():
    f=fixture()
    f.loc[0,'order_cancel_reason']='Customer Request'
    f.loc[1,'order_cancel_reason']=None
    _, lines, _, _ = analysis.summarize(f)
    assert lines.order_group.tolist() == ['X','X','D','D','D']
    assert lines.loc[1, 'order_status'] == 'D'


def test_all_raw_line_status_codes_and_unknowns():
    f=fixture()
    f['order_line_status']=[' X ','C','S','R',None]
    _, lines, _, _ = analysis.summarize(f)
    assert lines.order_group.tolist() == ['X','C','S','R','[Unknown line status]']


def test_shared_line_counted_once():
    frame = fixture()
    extra = frame.iloc[[0]].copy()
    extra['rx_id'] = 'RXother'
    _, lines, groups, audit = analysis.summarize(pd.concat([frame, extra], ignore_index=True))
    assert len(lines) == groups.order_lines.sum() == 5
    assert audit['matched_prescriptions'] == 6
    assert audit['repeated_prescription_line_associations'] == 1
    extra['approval_channel'] = 'VERBAL'
    with pytest.raises(ValueError, match='conflicting channel'):
        analysis.summarize(pd.concat([frame, extra], ignore_index=True))


def test_missing_invalid_unmatched_excluded():
    f = fixture()
    f.loc[:2, ['matched_order_id', 'matched_order_line_id']] = None
    f.loc[:2, 'line_source_rows'] = 0
    f.loc[0, 'first_order_id'] = None
    f.loc[1, ['first_order_line_id', 'first_orderitem_id']] = [None, 'invalid']
    _, lines, groups, audit = analysis.summarize(f)
    assert len(lines) == groups.order_lines.sum() == 2
    assert audit['missing_first_order_id'] == 1
    assert audit['missing_or_invalid_first_order_item_id'] == 1
    assert audit['unmatched_first_order_line'] == 1


@pytest.mark.parametrize('column,value', [('duplicate_shipment_rows',1), ('order_status_variants',2),
    ('cancel_reason_variants',2),
    ('block_reason_variants',2),
    ('line_status_variants',2), ('rx_source_rows',2), ('line_source_rows',-1),
    ('matched_order_line_id',100), ('invalid_upload_source_rows',1)])
def test_invalid_evidence_fails(column,value):
    f=fixture()
    f.loc[0,column]=value
    with pytest.raises(ValueError):
        analysis.summarize(f)


def test_sql_join_both_keys_and_collapse_shipments():
    sql = analysis.render_sql('2026-08-15','2026-10-15','2026-08-01')
    assert 'EDLDB.BT_HCA_HCDM.ORDER_LINE_COST_MEASURES_RXP' in sql
    assert 'ECOM.ORDERS' not in sql
    assert 'p.first_order_id = o.order_id' in sql
    assert 'p.first_order_line_id = o.order_line_id' in sql
    assert 'GROUP BY o.order_id, o.order_line_id' in sql
    assert "TRY_TO_NUMBER(first_orderitem_id)" in sql
    with pytest.raises(ValueError):
        analysis.render_sql('2026-08-15','2026-08-01','2026-08-01')
    with patch.object(analysis.subprocess,'run') as run:
        result = CliRunner().invoke(analysis.main,['--print-sql'])
    assert result.exit_code == 0
    run.assert_not_called()


def test_outputs_and_focus_denominator(tmp_path):
    f=fixture()
    f.loc[0,'approval_channel']='VERBAL'
    metadata=dict(start_date='2026-08-15',end_date_exclusive='2026-10-15',upload_start_date='2026-08-01',
                  extracted_at_utc='test')
    with patch.object(analysis.legacy,'render_sankey') as render:
        analysis.write_outputs(f,metadata,tmp_path/'diagrams',tmp_path/'tables')
    assert render.call_count == 3
    assert 'Denominator: 5 order lines' in render.call_args_list[0].args[-1]
    assert 'Denominator: 4 order lines' in render.call_args_list[1].args[-1]
    assert 'Denominator: 1 order lines' in render.call_args_list[2].args[-1]
    assert 'CUSTOMER_UPLOAD only' in render.call_args_list[2].args[-1]
    focused=render.call_args_list[2].args[0]
    assert len(focused.attrs['columns'])==4
    assert set(focused.attrs['node_colors'].values())=={'#AF7AA1'}
    assert len(render.call_args_list[0].args[0].attrs['columns'])==4
    assert set(focused.loc[focused.transition.eq(1),'source'])=={'Channel: CUSTOMER_UPLOAD'}
    assert focused.groupby('transition').prescriptions.sum().eq(1).all()
    assert focused.groupby('transition').percent_of_cohort.sum().eq(100).all()
    assert set(focused.transition)=={1,2,3}
    assert focused.loc[focused.transition.eq(2),'source'].str.startswith('First order line status:').all()
    assert focused.loc[focused.transition.eq(1),'target'].str.startswith('First order line status:').all()
    assert (tmp_path/'tables'/'non-d-order-lines.md').exists()
    assert (tmp_path/'tables'/'non-d-flows.md').exists()
    assert (tmp_path/'tables'/'non-d-distribution.md').exists()
    assert 'First order cancel reason:' in (tmp_path/'tables'/'non-d-flows.md').read_text()
    assert 'First order cancel reason:' in (tmp_path/'tables'/'flows.md').read_text()
    assert 'order_lines' in (tmp_path/'tables'/'flows.md').read_text()
    assert 'First order line status:' in (tmp_path/'tables'/'flows.md').read_text()
    assert 'Aged Order' in (tmp_path/'tables'/'distribution.md').read_text()


def test_empty_population():
    _, lines, groups, audit=analysis.summarize(fixture().iloc[:0])
    assert len(lines) == len(groups) == audit['distinct_order_lines'] == 0


def test_cached_sql_fingerprint_rejected(tmp_path):
    period=analysis.legacy.period_name('2026-08-15','2026-10-15','2026-08-01')+'_uploads-end-2026-10-26'
    data=tmp_path/'data'/analysis.NAME/(period+'_block-reasons')
    data.mkdir(parents=True)
    fixture().to_parquet(data/'source.parquet')
    (data/'source.json').write_text(json.dumps(dict(sql='old')))
    with patch.object(analysis,'ROOT',tmp_path):
        result=CliRunner().invoke(analysis.main,['--cached'])
    assert result.exit_code != 0
    assert 'fingerprint' in result.output


def test_block_reasons_remain_in_data_but_are_not_diagram_nodes():
    f=fixture();f.loc[1,'order_item_block_reason']=' '
    _,lines,groups,_=analysis.summarize(f)
    assert lines.block_reason.tolist()==['Clinic response','[No block reason recorded]']+['[Not applicable: status D]']*3
    assert 'block_reason' in groups
    flows=analysis.flows_for_rendering(groups)
    nodes=set(flows.source)|set(flows.target)
    assert not any('Item block reason:' in n or 'Clinic response' in n for n in nodes)
    assert flows.groupby('transition').prescriptions.sum().to_dict()=={1:5,2:5,3:5}
    assert flows.groupby('transition').percent_of_cohort.sum().eq(100).all()


def test_order_status_removed_and_uploads_split_by_cancellation_reason_presence():
    f=fixture();f.loc[2,'order_line_status']='C'
    _,_,groups,_=analysis.summarize(f)
    flows=analysis.flows_for_rendering(groups)
    assert flows.loc[flows.transition.eq(1),'target'].str.startswith('First order line status:').all()
    pairs=flows.loc[flows.transition.eq(2)]
    assert pairs.source.str.startswith('First order line status:').all()
    assert pairs.target.str.startswith('First order cancel reason:').all()
    assert not any(n.startswith('First order status:') for n in set(flows.source)|set(flows.target))
    counts=flows.loc[flows.transition.eq(3)].groupby('target').prescriptions.sum().to_dict()
    assert counts=={'Matching upload: With cancellation reason / Has matching upload':1,
        'Matching upload: With cancellation reason / No matching upload':1,
        'Matching upload: No cancellation reason / Has matching upload':1,
        'Matching upload: No cancellation reason / No matching upload':2}


@pytest.mark.parametrize('reason',[None,'','   ','Customer Request'])
def test_upload_groups_use_reason_presence_and_merge_recorded_reasons(reason):
    f=fixture();f.loc[1,'order_cancel_reason']=reason
    _,lines,groups,_=analysis.summarize(f)
    expected='No cancellation reason' if reason is None or not reason.strip() else 'With cancellation reason'
    assert lines.loc[1,'cancellation_reason_group']==expected
    # Row 1 has order status D even when it has a reason: use reason presence, not order status.
    assert lines.loc[1,'order_status']=='D'
    flows=analysis.flows_for_rendering(groups)
    targets=flows.loc[flows.transition.eq(3)].groupby('target').prescriptions.sum()
    assert f'Matching upload: {expected} / Has matching upload' in targets.index
    assert int(targets.sum())==5


def test_non_d_keeps_explicit_line_status_column_and_all_non_d_codes():
    f=fixture();f.loc[2,'order_line_status']='C'
    _,lines,_,_=analysis.summarize(f)
    selected=lines.loc[analysis.non_d(lines)]
    groups=selected.groupby(analysis.DIMENSIONS).size().reset_index(name='order_lines')
    flows=analysis.flows_for_rendering(groups)
    assert flows.groupby('transition').prescriptions.sum().to_dict()=={1:3,2:3,3:3}
    assert set(flows.loc[flows.transition.eq(1),'target'])=={'First order line status: X','First order line status: C'}
    assert [heading for _,heading in flows.attrs['columns']]==[
        'Approval channel','Order line status','Cancellation reason','Matching upload']


def test_unknown_order_and_line_statuses_reach_upload_and_cancel_reasons_stay_explicit():
    f=fixture();f.loc[1,'order_status']=None;f.loc[1,'order_line_status']=None
    f.loc[1,'order_cancel_reason']=None
    _,_,groups,_=analysis.summarize(f)
    flows=analysis.flows_for_rendering(groups)
    assert 'First order line status: [Unknown line status]' in flows.target.tolist()
    assert not any(n.startswith('First order status:') for n in set(flows.source)|set(flows.target))
    assert set(flows.loc[flows.transition.eq(2),'target'])=={
        'First order cancel reason: Aged Order','First order cancel reason: [No cancellation reason recorded]'}
    assert flows.loc[flows.transition.eq(3),'target'].str.startswith('Matching upload:').all()
    assert flows.groupby('transition').prescriptions.sum().eq(5).all()


def test_column_headers_remove_prefixes_from_visible_labels_in_all_views(tmp_path):
    import xml.etree.ElementTree as ET
    metadata=dict(start_date='2026-08-15',end_date_exclusive='2026-10-15',upload_start_date='2026-08-01',extracted_at_utc='test')
    with patch.object(analysis.legacy,'render_sankey') as render:
        analysis.write_outputs(fixture(),metadata,tmp_path/'diagrams',tmp_path/'tables')
    for call in render.call_args_list:
        flows=call.args[0]
        nodes=sorted(set(flows.source)|set(flows.target))
        svg='<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 5000 1000"><g class="node-labels">'+''.join(
            '<text>'+n+' (1; 20.00%)</text>' for n in nodes)+'</g></svg>'
        tree=ET.fromstring(analysis.legacy.add_title(svg,'Fixture',flows.attrs['columns']))
        ns={'s':'http://www.w3.org/2000/svg'}
        labels=[t.text for t in tree.findall('.//s:g[@class="node-labels"]/s:text',ns)]
        assert not any(label.startswith(tuple(prefix for prefix,_ in flows.attrs['columns'])) for label in labels)
        assert len(tree.findall('.//s:g[@class="stage-headings"]/s:text',ns))==4
    assert 'Clinic response' in (tmp_path/'tables'/'order-lines.md').read_text()
    assert 'block_reason' in (tmp_path/'tables'/'distribution.md').read_text()


@pytest.mark.parametrize('column,timestamp,allowed', [
    ('first_upload_at_utc', '2026-10-15', True),
    ('first_upload_at_utc', '2026-10-25 23:59:59.999999', True),
    ('first_upload_at_utc', '2026-10-26', False),
    ('rx_creation_datetime', '2026-10-15', False)])
def test_upload_followup_boundaries_and_separate_source_location(tmp_path, column, timestamp, allowed):
    frame=fixture()
    frame.loc[1,column]=pd.Timestamp(timestamp)
    metadata=dict(start_date='2026-08-15',end_date_exclusive='2026-10-15',
                  upload_start_date='2026-08-01',extracted_at_utc='test')
    with patch.object(analysis.legacy,'render_sankey') as render:
        if not allowed:
            with pytest.raises(ValueError, match='outside'):
                analysis.write_outputs(frame,metadata,tmp_path/'outputs',tmp_path/'tables',source_dir=tmp_path/'src')
            render.assert_not_called()
            return
        analysis.write_outputs(frame,metadata,tmp_path/'outputs',tmp_path/'tables',source_dir=tmp_path/'src')
    for call in render.call_args_list:
        _,source,png,title=call.args
        assert source.parent==tmp_path/'src'
        assert png.parent==tmp_path/'outputs'
        assert source.stem==png.stem
        assert 'uploads-2026-08-01_2026-10-25' in source.name
        assert 'Rx: 2026-08-15–2026-10-14; uploads: 2026-08-01–2026-10-25' in title


def test_cli_fresh_and_cached_paths_and_upload_sql(tmp_path):
    frame=fixture().assign(extracted_at_session_time='test',extraction_warehouse='TEST')
    sql=analysis.render_sql('2026-08-15','2026-10-15','2026-08-01')
    assert "rx_creation_datetime < '2026-10-15'::TIMESTAMP_NTZ" in sql
    assert "created_ts_utc < '2026-10-26'::TIMESTAMP_NTZ" in sql
    def extract(args, **kwargs):
        from pathlib import Path
        assert Path(args[2]).is_relative_to(tmp_path/'src/autogenerated')
        assert args[args.index('--sql-log-dir')+1].startswith('src/autogenerated/')
        frame.to_parquet(tmp_path/args[args.index('--output-parquet')+1])
    with patch.object(analysis,'ROOT',tmp_path), patch.object(analysis.subprocess,'run',side_effect=extract) as run, \
            patch.object(analysis,'write_outputs',return_value={}) as write:
        result=CliRunner().invoke(analysis.main,[])
        assert result.exit_code==0,result.output
        assert run.call_count==1
        assert write.call_args.args[2]==tmp_path/'outputs/diagrams/2026-08-15_2026-10-14'
        assert write.call_args.kwargs['source_dir']==tmp_path/'src/diagrams/2026-08-15_2026-10-14'
        result=CliRunner().invoke(analysis.main,['--cached'])
        assert result.exit_code==0,result.output
        assert run.call_count==1
    assert not list((tmp_path/'data').rglob('*.sql'))

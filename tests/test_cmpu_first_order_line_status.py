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
    assert flows.groupby('transition').prescriptions.sum().to_dict() == {1:5,2:5,3:5,4:5}
    assert abs(groups.percent_of_cohort.sum()-100) < 1e-9
    assert set(flows.loc[flows.transition.eq(2),'target']) == {
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
    assert set(focused.attrs['node_colors'].values())=={'#AF7AA1','#8CC9EE'}
    assert not render.call_args_list[0].args[0].attrs.get('columns')
    assert set(focused.loc[focused.transition.eq(1),'source'])=={'Channel: CUSTOMER_UPLOAD'}
    assert focused.groupby('transition').prescriptions.sum().eq(1).all()
    assert focused.groupby('transition').percent_of_cohort.sum().eq(100).all()
    assert set(focused.transition)=={1,2,3}
    assert not focused.source.str.startswith('First order line status:').any()
    assert not focused.target.str.startswith('First order line status:').any()
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
    period=analysis.legacy.period_name('2026-08-15','2026-10-15','2026-08-01')
    data=tmp_path/'data'/analysis.NAME/(period+'_block-reasons')
    data.mkdir(parents=True)
    fixture().to_parquet(data/'source.parquet')
    (data/'source.json').write_text(json.dumps(dict(sql='old')))
    with patch.object(analysis,'ROOT',tmp_path):
        result=CliRunner().invoke(analysis.main,['--cached'])
    assert result.exit_code != 0
    assert 'fingerprint' in result.output


def test_block_reason_stage_missingness_and_conservation():
    f=fixture()
    f.loc[1,'order_item_block_reason']=' '
    _, lines, groups, _ = analysis.summarize(f)
    assert lines.block_reason.tolist() == ['Clinic response','[No block reason recorded]']+['[Not applicable: status D]']*3
    flows=analysis.flows_for_rendering(groups)
    assert set(flows.transition) == {1,2,3,4}
    assert flows.groupby('transition').prescriptions.sum().to_dict() == {1:5,2:5,3:5,4:5}
    assert set(flows.loc[flows.source.eq('First order line status: D'),'target']) == {
        'Item block reason: D / [Not applicable: status D]'}
    source=analysis.legacy.mermaid_source(flows)
    assert 'Item block reason: X / Clinic response (1; 20.00%)' in source
    assert 'Item block reason: X / [No block reason recorded] (1; 20.00%)' in source


def test_status_branches_remain_separate_through_blocks_and_uploads():
    f=fixture()
    f.loc[2,'order_line_status']='C'
    f.loc[2,'order_item_block_reason']='Clinic response'  # Same reason as X.
    _,_,groups,_=analysis.summarize(f)
    flows=analysis.flows_for_rendering(groups)
    endpoints=flows.loc[flows.transition.eq(4)]
    for row in endpoints.itertuples():
        status=row.source.removeprefix('Item block reason: ').split(' / ',1)[0]
        assert row.target.startswith(f'Matching upload: {status} / ')
    counts=endpoints.groupby('target').prescriptions.sum().to_dict()
    assert counts['Matching upload: X / Has matching upload']==1
    assert counts['Matching upload: X / No matching upload']==1
    assert counts['Matching upload: D / Has matching upload']==1
    assert counts['Matching upload: D / No matching upload']==1
    assert counts['Matching upload: C / No matching upload']==1
    source=analysis.legacy.mermaid_source(flows)
    assert 'Matching upload: X / Has matching upload (1; 20.00%)' in source
    assert '#F28E2C' in source and '#8CC9EE' in source


def test_hidden_line_status_preserves_non_x_lines_and_status_upload_paths():
    f=fixture()
    f.loc[2,'order_line_status']='C'
    _,lines,_,_=analysis.summarize(f)
    selected=lines.loc[analysis.non_d(lines)]
    groups=selected.groupby(['channel','cancel_reason','order_group','block_reason','upload_group']).size().reset_index(name='order_lines')
    flows=analysis.flows_for_rendering(groups, show_line_status=False)
    assert flows.groupby('transition').prescriptions.sum().to_dict()=={1:3,2:3,3:3}
    assert not flows.target.str.startswith('First order line status:').any()
    assert 'Matching upload: C / No matching upload' in flows.target.tolist()


def test_d_and_unknown_statuses_use_not_applicable_then_reach_upload():
    f=fixture()
    f['order_line_status']=['D',None,'D','D','D']
    _,_,groups,_=analysis.summarize(f)
    flows=analysis.flows_for_rendering(groups)
    assert set(flows.transition)=={1,2,3,4}
    blocks=flows.loc[flows.transition.eq(3),'target']
    assert blocks.str.contains('Not applicable:',regex=False).all()
    assert flows.loc[flows.transition.eq(4),'target'].str.startswith('Matching upload:').all()
    assert flows.groupby('transition').prescriptions.sum().eq(5).all()


def test_non_d_cancel_reason_step_conservation_and_missingness():
    f=fixture()
    f.loc[1,'order_cancel_reason']=None
    _,lines,_,_=analysis.summarize(f)
    selected=lines.loc[analysis.non_d(lines)].copy()
    dimensions=['channel','cancel_reason','order_group','block_reason','upload_group']
    groups=selected.groupby(dimensions).size().reset_index(name='order_lines')
    flows=analysis.flows_for_rendering(groups)
    assert flows.groupby('transition').prescriptions.sum().to_dict()=={1:2,2:2,3:2,4:2}
    assert set(flows.loc[flows.transition.eq(1),'target'])=={
        'First order cancel reason: Aged Order',
        'First order cancel reason: [No cancellation reason recorded]'}
    assert flows.loc[flows.transition.eq(2),'target'].eq('First order line status: X').all()
    assert flows.loc[flows.transition.eq(3),'source'].eq('First order line status: X').all()
    assert flows.loc[flows.transition.eq(4),'source'].str.startswith('Item block reason:').all()
    assert flows.loc[flows.transition.eq(4),'target'].str.startswith('Matching upload:').all()
    assert flows.groupby('transition').percent_of_cohort.sum().eq(100).all()

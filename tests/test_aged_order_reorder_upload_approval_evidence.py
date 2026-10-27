"""Distinct prescription overlap counts, per-horizon line evidence and frozen inputs."""
import json
from unittest.mock import patch

from click.testing import CliRunner
import pandas as pd
import pytest

from src.python import create_aged_order_reorder_upload_approval_evidence as analysis
from tests.test_aged_order_reorder_uploads import fixtures as upload_fixtures

ASOF = '2026-10-27'


def fixtures():
    pairs, requests, source = upload_fixtures()
    pairs['reorder_approval_channel'] = requests.channel
    pairs['reorder_order_id'] = range(100, 104)
    pairs['reorder_line_id'] = range(200, 204)
    pairs = pd.concat([pairs.assign(followup_days=d) for d in [7, 14, 21]], ignore_index=True)
    pairs, requests, lines = analysis.requests_for(pairs)
    source = source.merge(lines, on=['rx_id', 'customer_id'], validate='many_to_one')
    source['line_source_rows'] = 2
    source['line_rx_id'] = source.rx_id
    source['line_rx_variants'] = 1
    source['missing_line_rx_rows'] = 0
    source['min_approved_denied_datetime'] = source.rx_id.map({'A': '2026-10-22 00:00:00.123456789', 'B': '2026-10-23'})
    source['approval_variants'] = source.min_approved_denied_datetime.notna().astype(int)
    source['populated_approval_rows'] = source.approval_variants
    return pairs, requests, lines, source


def test_distinct_rx_four_overlap_cells_file_flags_and_undated_evidence():
    outputs = analysis.summarize(*fixtures(), ASOF)
    assert len(outputs['prescriptions']) == 12
    for days, group in outputs['summary'].loc[outputs['summary'].approval_channel.eq('All channels')].groupby('followup_days'):
        counts = group.set_index('measure')['count']
        assert counts[['Both upload and decision timestamp', 'Upload only', 'Decision timestamp only', 'Neither']].tolist() == [1, 1, 1, 1]
        assert counts['Any dated entity upload'] == 2
        assert counts['Any non-null decision timestamp'] == 2
        assert counts['Upload or decision timestamp (union)'] == 3
        assert counts['Any entity including undated'] == 3
        assert counts['Undated entity only'] == 1
        assert counts['Dated entity with HAS_UPLOADED_FILE=true'] == 1
        assert group.denominator.eq(4).all()
    selected = outputs['selected-customers']
    assert selected.loc[selected.rx_id.eq('A'), 'min_approved_denied_datetime'].dt.nanosecond.eq(789).all()
    assert not selected.loc[selected.rx_id.eq('C'), 'has_dated_entity_upload'].any()
    assert len(outputs['upload-associations']) == 5


def test_decisions_are_specific_to_selected_line_in_each_horizon():
    pairs, requests, lines, source = fixtures()
    mask = pairs.followup_days.eq(14) & pairs.reorder_rx_ids.eq('A')
    pairs.loc[mask, 'reorder_order_id'] = 999
    extra = source.loc[source.rx_id.eq('A')].assign(order_id=999, min_approved_denied_datetime=None,
        approval_variants=0, populated_approval_rows=0)
    source = pd.concat([source, extra], ignore_index=True)
    pairs, requests, lines = analysis.requests_for(pairs)
    outputs = analysis.summarize(pairs, requests, lines, source, ASOF)
    rx = outputs['prescriptions'].loc[outputs['prescriptions'].rx_id.eq('A')].set_index('followup_days')
    assert rx.has_decision_timestamp.to_dict() == {7: True, 14: False, 21: True}
    assert len(outputs['upload-associations']) == 5  # extra line does not multiply uploads


def test_future_decision_is_counted_but_audited():
    pairs, requests, lines, source = fixtures()
    source.loc[source.rx_id.eq('B'), 'min_approved_denied_datetime'] = '2026-10-27 00:00:00.000000001'
    result = analysis.summarize(pairs, requests, lines, source, ASOF)
    summaries = result['summary'].loc[result['summary'].approval_channel.eq('All channels')]
    assert summaries.loc[summaries.measure.eq('Decision timestamp after cutoff'), 'count'].eq(1).all()
    assert summaries.loc[summaries.measure.eq('Any non-null decision timestamp'), 'count'].eq(2).all()


@pytest.mark.parametrize('case', ['missing-line', 'extra-line', 'duplicate-upload', 'line-rx', 'line-null-rx',
    'line-missing', 'decision-count', 'negative-count', 'inconsistent-line', 'wrong-upload-customer', 'late-upload'])
def test_inconsistent_or_wrong_cohort_evidence_rejected(case):
    pairs, requests, lines, source = fixtures()
    if case == 'missing-line': source = source.loc[source.rx_id.ne('A')]
    if case == 'extra-line': source = pd.concat([source, source.iloc[[0]].assign(order_id=999)])
    if case == 'duplicate-upload': source = pd.concat([source, source.iloc[[0]]])
    if case == 'line-rx': source.loc[0, 'line_rx_id'] = 'WRONG'
    if case == 'line-null-rx': source.loc[0, 'missing_line_rx_rows'] = 1
    if case == 'line-missing': source.loc[0, 'line_source_rows'] = 0
    if case == 'decision-count': source.loc[0, 'populated_approval_rows'] = 0
    if case == 'negative-count': source.loc[0, 'approval_variants'] = -1
    if case == 'inconsistent-line': source.loc[0, 'populated_approval_rows'] = 2
    if case == 'wrong-upload-customer': source.loc[0, 'upload_customer_id'] = 999
    if case == 'late-upload': source.loc[0, 'uploaded_at_utc'] = '2026-10-27 00:00:00.000000001'
    with pytest.raises(ValueError): analysis.summarize(pairs, requests, lines, source, ASOF)


def test_frozen_selection_different_only_and_distinct_requests():
    pairs, _, _, _ = fixtures()
    extra = pairs.iloc[[0]].assign(prescription_comparison='Same prescription', reorder_rx_ids='OTHER')
    selected, requests, lines = analysis.requests_for(pd.concat([pairs, extra]))
    assert len(selected) == 12 and len(requests) == len(lines) == 4
    with pytest.raises(ValueError, match='inconsistent customer'):
        analysis.requests_for(pd.concat([pairs, pairs.iloc[[0]].assign(original_customer_id=999)]))


def test_fresh_cached_print_sql_exports_and_fingerprint_rejection(tmp_path):
    pairs, requests, lines, source = fixtures()
    period = '2026-08-15_2026-10-15_customer_upload_same-pet_reorders-7d-14d-21d_as-of-2026-10-27'
    def extract(args, **kwargs):
        source.assign(extraction_warehouse='test').to_parquet(tmp_path / args[args.index('--output-parquet') + 1], index=False)
    with patch.object(analysis, 'ROOT', tmp_path), \
         patch.object(analysis.sankeys.windows, 'load_source', return_value=(pd.DataFrame(), {'parquet_sha256': 'baseline'}, period)), \
         patch.object(analysis.sankeys.windows, 'summarize', return_value={'associations': pd.DataFrame()}), \
         patch.object(analysis.sankeys, 'select_customers', return_value=pd.DataFrame()), \
         patch.object(analysis.sankeys, 'load_source', return_value=(pd.DataFrame(), {'parquet_sha256': 'rxsource'}, None)), \
         patch.object(analysis.sankeys, 'summarize', return_value=(pairs, None)), \
         patch.object(analysis.subprocess, 'run', side_effect=extract) as run:
        runner = CliRunner()
        result = runner.invoke(analysis.main, ['--print-sql'])
        assert result.exit_code == 0, result.output
        assert 'MIN(l.min_approved_denied_datetime)' in result.output
        assert 'k.order_id=l.order_id AND k.order_line_id=l.order_line_id' in result.output
        assert 'created_ts_utc >=' not in result.output
        run.assert_not_called()
        assert not list(tmp_path.iterdir())
        result = runner.invoke(analysis.main, [])
        assert result.exit_code == 0, result.output
        run.assert_called_once(); run.reset_mock()
        result = runner.invoke(analysis.main, ['--cached'])
        assert result.exit_code == 0, result.output
        run.assert_not_called()
        assert len(list((tmp_path / 'outputs/tables/2026-08-15_2026-10-14').glob('*.md'))) == 6
        manifest = next((tmp_path / 'data').rglob('source.json'))
        original = json.loads(manifest.read_text())
        for field in ['sql_sha256', 'parquet_sha256', 'dependencies']:
            manifest.write_text(json.dumps({**original, field: 'tampered'}))
            result = runner.invoke(analysis.main, ['--cached'])
            assert result.exit_code != 0 and 'fingerprint differs' in result.output
        exports = json.loads(next((tmp_path / 'data').rglob('exports.json')).read_text())
        for path, fingerprint in exports['files'].items(): assert analysis.digest(tmp_path / path) == fingerprint

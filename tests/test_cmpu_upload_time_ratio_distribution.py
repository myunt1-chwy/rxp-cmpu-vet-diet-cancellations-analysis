import hashlib
import json
from decimal import Decimal
from unittest.mock import patch

from click.testing import CliRunner
import numpy as np
import pandas as pd
import pytest

from src.python import create_cmpu_upload_time_ratio_distribution as ratio

DATES = ('2026-08-15', '2026-10-15', '2026-08-01')


def source(intervals=((0, 100), (25, 100), (50, 100), (100, 100), (150, 100))):
    created = pd.Timestamp('2026-08-15 12:00')
    return pd.DataFrame([dict(rx_id=f'RX{i}', rx_source_rows=1, customer_id=1,
        rx_creation_datetime='2026-08-15', approval_channel='CUSTOMER_UPLOAD',
        first_order_id=100, first_orderitem_id=str(i), first_order_line_id=i,
        order_id=100, order_line_id=i, shipment_rows=2, line_status='D', status_variants=1,
        placement_variants=1, eastern_variants=1, missing_eastern_rows=0,
        missing_approval_rows=0, approval_variants=1,
        order_placed_utc=created, order_placed_eastern=created-pd.Timedelta(hours=4),
        max_approved_datetime=created+pd.Timedelta(seconds=approval) if approval is not None else pd.NaT,
        first_upload_at_utc=created+pd.Timedelta(seconds=upload), upload_state_changed_at_utc=created+pd.Timedelta(seconds=upload),
        selected_upload_id=f'U{i}', selected_upload_state='ACCEPTED', upload_count=2,
        **{col: 0 for col in ratio.timing.AUDIT_COLUMNS})
        for i, (upload, approval) in enumerate(intervals)])


def test_ratio_quantiles_zero_one_outliers_and_counts():
    associations, lines, audit, stats, bins, cdf = ratio.summarize(source(), *DATES)
    expected = [0, .25, .5, 1, 1.5]
    assert lines.ratio.tolist() == expected
    assert stats['mean'].iloc[0] == pytest.approx(np.mean(expected))
    assert stats.N.iloc[0] == bins.order_lines.sum() == cdf.cumulative_lines.iloc[-1] == 5
    assert stats.loc[0, ['minimum', 'p25', 'median', 'p75', 'p95', 'maximum']].to_numpy(float) == pytest.approx(
        np.quantile(expected, [0, .25, .5, .75, .95, 1]))
    assert bins.bin_index.tolist() == [0, 25, 50, 100, 150]
    assert cdf.cumulative_fraction.iloc[-1] == 1
    assert 'elapsed_hours' not in associations and 'elapsed_hours' not in lines
    assert audit.loc[audit.measure.eq('Ratio above 1'), 'count'].iloc[0] == 1


def test_exclusions_missing_placement_and_upload_source_audits():
    frame = source(((-1, 10), (1, 0), (1, -10), (1, None), (0, 10), (1, 10)))
    frame.loc[5, ['order_placed_utc', 'order_placed_eastern']] = pd.NaT
    frame.loc[5, ['eastern_variants', 'missing_eastern_rows']] = [0, 2]
    associations, lines, audit, stats, bins, cdf = ratio.summarize(frame, *DATES)
    assert associations.eligibility.tolist() == [
        'Negative upload duration', 'Zero approval duration', 'Negative approval duration',
        'Missing approval timestamp', 'Eligible', 'Missing placement timestamp']
    assert lines.ratio.iloc[0] == -.1
    assert pd.isna(lines.ratio.iloc[1])
    assert stats.N.iloc[0] == bins.order_lines.sum() == cdf.cumulative_lines.iloc[-1] == 1
    assert stats.minimum.iloc[0] == 0
    for status in associations.eligibility.unique():
        assert audit.loc[audit.grain.eq('distinct matched lines') & audit.measure.eq(status), 'count'].iloc[0] == 1
    for column, value in [('invalid_upload_source_rows', 1), ('first_upload_at_utc', pd.NaT)]:
        broken = source()
        broken[column] = value
        with pytest.raises(ValueError):
            ratio.summarize(broken, *DATES)


def test_deduplicated_lines_non_d_and_no_upload_filtering():
    frame = source()
    frame.loc[1, 'line_status'] = 'X'
    frame.loc[2, ['upload_count','first_upload_at_utc','upload_state_changed_at_utc','selected_upload_id','selected_upload_state']] = [0,pd.NaT,pd.NaT,None,None]
    extra = frame.iloc[[0]].assign(rx_id='another-rx')
    associations, lines, audit, stats, _, _ = ratio.summarize(pd.concat([frame, extra]), *DATES)
    assert len(associations) == 5 and len(lines) == 4
    assert stats.N.iloc[0] == 3
    assert audit.loc[audit.measure.eq('No matching upload'), 'count'].iloc[0] == 1
    assert audit.loc[audit.measure.eq('Repeated prescription associations'), 'count'].iloc[0] == 1
    broken = frame.copy()
    broken.loc[0, 'placement_variants'] = 2
    with pytest.raises(ValueError, match='conflicting shipment'):
        ratio.summarize(broken, *DATES)


def test_integer_bins_at_boundaries_and_long_duration_overflow():
    frame = source(((0, 1),) * 4)
    created = frame.order_placed_utc.iloc[0]
    frame['upload_state_changed_at_utc'] = [created+pd.Timedelta(nanoseconds=x)
                                   for x in [290000000, 289999999, 1000000000, 1000000001]]
    _, _, _, _, bins, _ = ratio.summarize(frame, *DATES)
    assert bins.set_index('bin_index').order_lines.to_dict() == {28: 1, 29: 1, 100: 2}
    # Scaling a 100-day nanosecond interval by 100 overflows int64.
    frame = source(((100 * 86400, 200 * 86400),))
    # Upload must remain within the search window; move line creation earlier.
    frame['order_placed_utc'] -= pd.Timedelta(days=100)
    frame['order_placed_eastern'] -= pd.Timedelta(days=100)
    frame['first_upload_at_utc'] -= pd.Timedelta(days=100)
    frame['upload_state_changed_at_utc'] -= pd.Timedelta(days=100)
    frame['max_approved_datetime'] -= pd.Timedelta(days=100)
    # August is daylight time, but the moved May creation is also daylight time.
    assert ratio.summarize(frame, *DATES)[4].bin_index.iloc[0] == 50


def test_exact_cdf_groups_ties():
    _, _, _, stats, _, cdf = ratio.summarize(source(((1, 2), (2, 4), (1, 1))), *DATES)
    assert stats.N.iloc[0] == 3
    assert cdf.ratio.tolist() == [.5, 1]
    assert cdf.order_lines.tolist() == [2, 1]
    assert cdf.cumulative_fraction.tolist() == [2/3, 1]


def test_empty_or_all_excluded_removes_only_own_stale_figures(tmp_path):
    metadata = dict(start_date=DATES[0], end_date_exclusive=DATES[1], upload_start_date=DATES[2],
                    extracted_at_utc='test', parquet_sha256='hash')
    charts = tmp_path/'charts'
    charts.mkdir()
    stem = 'cmpu-d-lines_upload-time-share_uploads-2026-08-01_2026-10-25_nonnegative_accepted-state-change_order-placed'
    for frame in [source().iloc[:0], source(((-1, 10),))]:
        for suffix in ['histogram', 'cumulative']:
            (charts/f'{stem}_{suffix}.png').write_bytes(b'stale')
        scatter = charts/(stem.replace('upload-time-share', 'upload-vs-approval-times')+'_linear-fit.png')
        scatter.write_bytes(b'stale')
        log_scatter = scatter.with_name(scatter.name.replace('_linear-fit.png', '_log-log-fit.png'))
        log_scatter.write_bytes(b'stale')
        unrelated = charts/'other-analysis.png'
        unrelated.write_bytes(b'keep')
        _, stats, notes = ratio.write_outputs(frame, metadata, charts, tmp_path/'tables')
        assert stats.N.iloc[0] == 0 and pd.isna(stats.minimum.iloc[0])
        assert not list(charts.glob(f'{stem}_*.png'))
        assert not scatter.exists()
        assert not log_scatter.exists()
        assert unrelated.read_bytes() == b'keep'
        assert 'No eligible lines' in notes.read_text()


def test_chart_percent_axes_full_range_and_no_hour_references(tmp_path):
    _, _, _, _, bins, cdf = ratio.summarize(source(), *DATES)
    with patch.object(ratio.alt.TopLevelMixin, 'save', autospec=True) as save:
        ratio.figures(bins, cdf, 5, tmp_path, 'ratio', ['Test'])
    assert save.call_count == 2
    histogram, cumulative = [call.args[0].to_dict() for call in save.call_args_list]
    assert histogram['encoding']['x']['axis']['format'] == '.0%'
    assert cumulative['encoding']['x']['axis']['format'] == '.0%'
    assert cumulative['encoding']['y']['axis']['format'] == '.0%'
    assert histogram['encoding']['x']['scale']['domain'] == [0, 1.51]
    assert 'layer' not in cumulative
    assert cumulative['mark']['interpolate'] == 'step-after'


def test_print_sql_side_effect_free_and_date_boundaries(tmp_path):
    with patch.object(ratio, 'ROOT', tmp_path), patch.object(ratio.timing, 'load_source') as load:
        result = CliRunner().invoke(ratio.main, ['--print-sql'])
    assert result.exit_code == 0, result.output
    assert "rx_creation_datetime < '2026-10-15'::TIMESTAMP_NTZ" in result.output
    assert "created_ts_utc < '2026-10-26'::TIMESTAMP_NTZ" in result.output
    load.assert_not_called()
    assert not list(tmp_path.iterdir())
    with pytest.raises(ValueError, match='prescription outside'):
        ratio.summarize(source().assign(rx_creation_datetime='2026-10-15'), *DATES)
    with pytest.raises(ValueError, match='upload outside'):
        ratio.summarize(source().assign(first_upload_at_utc=pd.Timestamp('2026-10-26')), *DATES)


def test_cached_source_provenance_and_changed_dates(tmp_path):
    period = '2026-08-15_2026-10-15_with-upload_uploads-from-2026-08-01_uploads-end-2026-10-26_accepted-state-change_order-placed'
    directory = tmp_path/'data'/ratio.timing.NAME/period
    directory.mkdir(parents=True)
    parquet = directory/'source.parquet'
    source().to_parquet(parquet)
    sql = ratio.timing.render_sql(DATES[0], DATES[1], True, DATES[2])
    metadata = dict(sql=sql, sql_sha256=hashlib.sha256(sql.encode()).hexdigest(),
        parquet_sha256=ratio.timing.digest(parquet), with_upload=True, upload_start_date=DATES[2],
        upload_end_date_exclusive='2026-10-26', start_date=DATES[0], end_date_exclusive=DATES[1],
        extracted_at_utc='test')
    (directory/'source.json').write_text(json.dumps(metadata))
    with patch.object(ratio, 'ROOT', tmp_path), patch.object(ratio.timing, 'ROOT', tmp_path), \
            patch.object(ratio.timing.subprocess, 'run') as run, patch.object(ratio, 'figures'), \
            patch.object(ratio, 'time_figure'):
        result = CliRunner().invoke(ratio.main, ['--cached'])
        assert result.exit_code == 0, result.output
        run.assert_not_called()
        record = json.loads((tmp_path/'data'/ratio.NAME/period/'analysis.json').read_text())
        assert record['eligible_lines'] == 5
        assert record['source_parquet_sha256'] == ratio.timing.digest(parquet)
        notes = list((tmp_path/'outputs/charts/2026-08-15_2026-10-14').glob('*.md'))
        assert len(notes) == 1 and 'upload-time-share' in notes[0].name
        tables = tmp_path/'outputs/tables/2026-08-15_2026-10-14'
        files = list(tables.iterdir())
        assert len(files) == 8 and all(path.is_file() for path in files)
        assert all(path.name.startswith('cmpu-d-lines_') for path in files)
        assert any(path.name.endswith('_statistics.md') for path in files)
        assert any(path.name.endswith('_log-log-fit.md') for path in files)
        assert not (tmp_path/'outputs/tables'/ratio.NAME).exists()
        result = CliRunner().invoke(ratio.main, ['--cached', '--end-date', '2026-10-16'])
        assert result.exit_code != 0
        parquet.write_bytes(b'tampered')
        result = CliRunner().invoke(ratio.main, ['--cached'])
        assert result.exit_code != 0 and 'fingerprint' in result.output


def test_time_fit_recovers_line_and_excludes_ineligible_observations():
    frame = source(((5, 1), (7, 2), (9, 3), (-1, 2000)))
    _, lines, _, _, _, _ = ratio.summarize(frame, *DATES)
    fit = ratio.fit_times(lines).iloc[0]
    assert fit.N == 3
    assert fit.slope == pytest.approx(2)
    assert fit.intercept_hours == pytest.approx(3/3600)
    assert fit.r_squared == pytest.approx(1)
    assert fit.fit_status == 'Fitted'


@pytest.mark.parametrize('intervals,status', [
    ((), 'Insufficient data'), (((1, 2),), 'Insufficient data'),
    (((1, 2), (2, 2)), 'Constant approval duration')])
def test_time_fit_undefined_slope(intervals, status):
    # Preserve source columns for the empty population.
    frame = source(intervals) if intervals else source().iloc[:0]
    _, lines, _, _, _, _ = ratio.summarize(frame, *DATES)
    fit = ratio.fit_times(lines).iloc[0]
    assert pd.isna(fit.slope) and fit.fit_status == status


def test_time_fit_constant_upload_duration_has_undefined_r_squared():
    _, lines, _, _, _, _ = ratio.summarize(source(((1, 2), (1, 3))), *DATES)
    fit = ratio.fit_times(lines).iloc[0]
    assert fit.slope == 0
    assert fit.intercept_hours == pytest.approx(1/3600)
    assert pd.isna(fit.r_squared)


def test_scatter_uses_all_eligible_points_and_correct_axes(tmp_path):
    frame = source(((5, 1), (7, 2), (9, 3), (-1, 2000))).assign(order_id=Decimal('100'))
    _, lines, _, _, _, _ = ratio.summarize(frame, *DATES)
    with patch.object(ratio.alt.TopLevelMixin, 'save', autospec=True) as save:
        ratio.time_figure(lines, ratio.fit_times(lines), tmp_path/'scatter.png', ['Test'])
    spec = save.call_args.args[0].to_dict()
    observed = spec['layer'][0]
    assert observed['encoding']['x']['field'] == 'approval_duration_hours'
    assert observed['encoding']['y']['field'] == 'upload_duration_hours'
    assert len(observed['data']['values']) == 3
    assert observed['data']['values'][0]['order_id'] == '100'
    json.dumps(observed['data']['values'])
    assert spec['layer'][1]['mark']['type'] == 'line'
    assert any('R² = 1.0000' in line for line in spec['title']['subtitle'])


def test_log_fit_recovers_power_law_without_pseudocounts():
    # In hours: y = 0.5 * x**2 at x=1,2,4. Zero is ratio-eligible but not log-eligible.
    frame = source(((1800, 3600), (7200, 7200), (28800, 14400), (0, 36000), (-1, 100)))
    _, lines, _, stats, _, _ = ratio.summarize(frame, *DATES)
    fit = ratio.fit_times(lines, log=True).iloc[0]
    assert stats.N.iloc[0] == 4
    assert fit.N == 3 and fit.excluded_nonpositive_times == 1
    assert fit.slope == pytest.approx(2)
    assert fit.intercept_log_hours == pytest.approx(np.log(.5))
    assert fit.power_multiplier == pytest.approx(.5)
    assert fit.r_squared_log == pytest.approx(1)
    assert fit.log_base == 'e'


def test_log_scatter_uses_log_axes_and_back_transformed_fit(tmp_path):
    _, lines, _, _, _, _ = ratio.summarize(source(((1800, 3600), (7200, 7200), (28800, 14400), (0, 100))), *DATES)
    fit = ratio.fit_times(lines, log=True)
    with patch.object(ratio.alt.TopLevelMixin, 'save', autospec=True) as save:
        ratio.time_figure(lines, fit, tmp_path/'log-fit.png', ['Test'], log=True)
    spec = save.call_args.args[0].to_dict()
    points = spec['layer'][0]
    assert len(points['data']['values']) == 3
    for axis in ['x', 'y']:
        assert points['encoding'][axis]['scale']['type'] == 'log'
        assert points['encoding'][axis]['scale']['zero'] is False
        assert 'log scale' in points['encoding'][axis]['title']
    predicted = next(data for data in spec['datasets'].values() if len(data) == 2)
    assert [row['approval_duration_hours'] for row in predicted] == [1, 4]
    assert [row['upload_duration_hours'] for row in predicted] == pytest.approx([.5, 8])
    assert any('R² (log) = 1.0000' in line for line in spec['title']['subtitle'])


def test_all_zero_uploads_keep_ratio_population_but_remove_log_figure(tmp_path):
    metadata = dict(start_date=DATES[0], end_date_exclusive=DATES[1], upload_start_date=DATES[2],
                    extracted_at_utc='test', parquet_sha256='hash')
    charts = tmp_path/'charts'
    charts.mkdir()
    log_scatter = charts/'cmpu-d-lines_upload-vs-approval-times_uploads-2026-08-01_2026-10-25_nonnegative_accepted-state-change_order-placed_log-log-fit.png'
    log_scatter.write_bytes(b'stale')
    frame = source(((0, 100), (0, 200)))
    with patch.object(ratio, 'figures'), patch.object(ratio, 'time_figure') as time_figure:
        _, stats, notes = ratio.write_outputs(frame, metadata, charts, tmp_path/'tables')
    assert stats.N.iloc[0] == 2
    assert time_figure.call_count == 1 and not time_figure.call_args.kwargs.get('log')
    assert not log_scatter.exists()
    assert 'No strictly positive time pairs' in notes.read_text()
    _, lines, _, _, _, _ = ratio.summarize(frame, *DATES)
    fit = ratio.fit_times(lines, log=True).iloc[0]
    assert fit.N == 0 and fit.excluded_nonpositive_times == 2 and pd.isna(fit.slope)


@pytest.mark.parametrize('intervals', [((1, 2),), ((1, 2), (2, 2)), ((1, 2), (1, 3))])
def test_log_fit_single_and_constant_times(intervals):
    _, lines, _, _, _, _ = ratio.summarize(source(intervals), *DATES)
    fit = ratio.fit_times(lines, log=True).iloc[0]
    if len(intervals) == 1 or intervals[0][1] == intervals[1][1]:
        assert pd.isna(fit.slope)
    else:
        assert fit.slope == 0 and pd.isna(fit.r_squared_log)

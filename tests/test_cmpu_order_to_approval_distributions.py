import json
from unittest.mock import patch

from click.testing import CliRunner
import pandas as pd
import pytest

from src.python import create_cmpu_order_to_approval_distributions as analysis

DATES = ('2026-08-15', '2026-10-15', '2026-08-01')


def source(hours=(0, 1, -1, 2)):
    rows = []
    for index, hours_value in enumerate(hours):
        row = dict(rx_id=f'DT{index}', customer_id=10, rx_source_rows=1,
                   rx_creation_datetime='2026-08-15', approval_channel='CUSTOMER_UPLOAD',
                   first_order_id=100, order_source_rows=1, order_status=' C ',
                   order_placed_at_utc=pd.Timestamp('2026-08-15 12:00'),
                   order_placed_at_eastern=pd.Timestamp('2026-08-15 08:00'),
                   first_usage_approved_datetime=pd.Timestamp('2026-08-15 12:00') + pd.Timedelta(hours=hours_value),
                   upload_count=2 if index % 2 == 0 else 0,
                   first_upload_at_utc=pd.Timestamp('2026-08-01') if index % 2 == 0 else pd.NaT)
        row.update({col: 0 for col in analysis.AUDIT_COLUMNS})
        rows.append(row)
    return pd.DataFrame(rows)


def test_hour_boundaries_negatives_quantiles_and_repeated_uploads():
    details, audit, stats, bins = analysis.summarize(source(), *DATES)
    assert len(details) == 4  # Repeated uploads never multiply observations.
    assert audit.Eligible.tolist() == [2, 2]
    assert audit.negative_durations.tolist() == [1, 0]
    assert stats.loc[0, 'p25'] == -.75
    assert stats.loc[1, 'median'] == 1.5
    assert bins.groupby('upload_group').prescriptions.sum().to_dict() == dict.fromkeys(analysis.GROUPS, 2)
    assert bins.loc[(bins.upload_group == analysis.GROUPS[1]) & (bins.lower_hours == 2), 'prescriptions'].iloc[0] == 1
    assert bins.lower_hours.min() == -1
    assert bins.upper_hours.max() == 3


def test_exclusions_and_reconciliation():
    frame = source(tuple(range(9)))
    frame.loc[0, ['first_order_id', 'order_source_rows']] = [None, 0]
    frame.loc[1, 'order_source_rows'] = 0
    frame.loc[2, 'order_status'] = ' '
    frame.loc[3, 'order_status'] = 'x'
    frame.loc[4, ['order_placed_at_utc', 'first_usage_approved_datetime']] = pd.NaT
    frame.loc[5, 'order_placed_at_utc'] = pd.NaT
    frame.loc[6, 'first_usage_approved_datetime'] = pd.NaT
    details, audit, stats, bins = analysis.summarize(frame, *DATES)
    assert details.eligibility.tolist() == analysis.STATES[:-1] + ['Eligible', 'Eligible']
    assert audit.cohort.sum() == 9
    assert stats.N.sum() == bins.prescriptions.sum() == 2


@pytest.mark.parametrize('column,value', [('rx_source_rows', 2), ('order_source_rows', 2),
    ('invalid_upload_source_rows', 1), ('upload_count', -1),
    ('order_placed_at_eastern', pd.Timestamp('2026-08-15 12:00')),
    ('rx_creation_datetime', '2026-10-15'),
    ('first_upload_at_utc', pd.Timestamp('2026-07-31'))])
def test_invalid_source(column, value):
    frame = source((1,))
    frame.loc[0, column] = value
    with pytest.raises(ValueError):
        analysis.summarize(frame, *DATES)


def test_duplicate_rx_rejected():
    frame = source()
    with pytest.raises(ValueError):
        analysis.summarize(pd.concat([frame, frame]), *DATES)


def test_empty_groups():
    for frame in [source((1,)), source().iloc[:0]]:
        _, audit, stats, bins = analysis.summarize(frame, *DATES)
        assert stats.loc[1, 'N'] == 0
        assert pd.isna(stats.loc[1, 'median'])
        assert stats.N.sum() == bins.prescriptions.sum() == len(frame)


def test_figure_spec_uses_vertical_bars_and_zero_baseline(tmp_path):
    _, _, stats, bins = analysis.summarize(source((1,)), *DATES)
    with patch.object(analysis.alt.TopLevelMixin, 'save') as save:
        analysis.figures(stats, bins, tmp_path, ['Test cohort'])
    assert save.call_count == 2
    # Compile the real charts, including the empty-group layer, without writing images.
    with patch.object(analysis.alt.TopLevelMixin, 'save', autospec=True) as save:
        analysis.figures(stats, bins, tmp_path, ['Test cohort'])
    spec = save.call_args_list[0].args[0].to_dict()
    assert spec['vconcat'][0]['mark']['orient'] == 'vertical'
    assert spec['vconcat'][0]['encoding']['y2'] == {'datum': 0}
    assert 'layer' in spec['vconcat'][1]


def test_sql_bounds_and_print_only():
    sql = analysis.render_sql(*DATES)
    assert "rx_creation_datetime >= '2026-08-15'" in sql
    assert "rx_creation_datetime < '2026-10-15'" in sql
    assert "created_ts_utc >= '2026-08-01'" in sql
    assert "approval_channel = 'CUSTOMER_UPLOAD'" in sql
    with pytest.raises(ValueError):
        analysis.render_sql('2026-08-15', '2026-08-15', '2026-08-01')
    with patch.object(analysis.subprocess, 'run') as run:
        result = CliRunner().invoke(analysis.main, ['--print-sql'])
        assert result.exit_code == 0
        run.assert_not_called()


def test_cached_fingerprint_rejected(tmp_path):
    directory = tmp_path / 'data' / analysis.NAME / analysis.period_name(*DATES)
    directory.mkdir(parents=True)
    frame = source()
    frame.to_parquet(directory / 'source.parquet')
    metadata = dict(sql=analysis.render_sql(*DATES), parquet_sha256='wrong', start_date=DATES[0],
                    end_date_exclusive=DATES[1], upload_start_date=DATES[2])
    (directory / 'source.json').write_text(json.dumps(metadata))
    with patch.object(analysis, 'ROOT', tmp_path):
        result = CliRunner().invoke(analysis.main, ['--cached'])
    assert result.exit_code != 0
    assert 'fingerprint' in result.output


def test_entirely_empty_population_removes_stale_figures(tmp_path):
    charts, tables = tmp_path / 'charts', tmp_path / 'tables'
    charts.mkdir()
    for name in ['distributions.png', 'statistics.png']:
        (charts / name).write_bytes(b'stale')
    metadata = dict(start_date=DATES[0], end_date_exclusive=DATES[1], upload_start_date=DATES[2],
                    extracted_at_utc='2026-10-26T00:00:00Z')
    audit, stats = analysis.write_outputs(source().iloc[:0], metadata, charts, tables)
    assert stats.N.sum() == audit.cohort.sum() == 0
    assert not list(charts.glob('*.png'))
    assert 'No eligible prescriptions' in (charts / 'README.md').read_text()

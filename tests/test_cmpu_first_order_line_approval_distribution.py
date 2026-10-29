import json
from pathlib import Path
from unittest.mock import patch

from click.testing import CliRunner
import duckdb
import numpy as np
import pandas as pd
import pytest

from src.python import create_cmpu_first_order_line_approval_distribution as analysis

DATES = ('2026-08-15', '2026-10-15')


def source(hours=(0, 1, -1, 2)):
    return pd.DataFrame([dict(rx_id=f'RX{i}', rx_source_rows=1,
        rx_creation_datetime='2026-08-15', approval_channel='CUSTOMER_UPLOAD',
        first_order_id=100, first_orderitem_id=str(i), first_order_line_id=i,
        order_id=100, order_line_id=i, shipment_rows=2, line_status='D',
        status_variants=1, placement_variants=1, eastern_variants=1,
        missing_eastern_rows=0, missing_approval_rows=1, approval_variants=1,
        order_placed_utc=pd.Timestamp('2026-08-15 12:00'),
        order_placed_eastern=pd.Timestamp('2026-08-15 08:00'),
        max_approved_datetime=pd.Timestamp('2026-08-15 12:00') + pd.Timedelta(hours=h))
        for i, h in enumerate(hours)])


def test_hour_boundaries_negatives_outliers_quantiles_and_repeated_associations():
    frame = source((-1.01, -1, 0, .999, 1, 2, 2000))
    repeated = frame.iloc[[0]].assign(rx_id='another')
    associations, lines, audit, stats, bins = analysis.summarize(pd.concat([frame, repeated]), *DATES)
    assert len(associations) == 8 and len(lines) == 7
    assert stats.N.iloc[0] == bins.order_lines.sum() == 7
    assert stats.loc[0, 'median'] == .999
    assert stats.loc[0, 'p95'] == pytest.approx(np.quantile(frame.max_approved_datetime.sub(
        frame.order_placed_utc).dt.total_seconds() / 3600, .95))
    assert bins.lower_hours.min() == -2 and bins.upper_hours.max() == 2001
    assert bins.loc[bins.lower_hours.eq(0), 'order_lines'].iloc[0] == 2
    assert audit.loc[audit.measure.eq('Negative durations'), 'count'].iloc[0] == 2


def test_exclusions():
    frame = source(tuple(range(9)))
    for i in range(4):
        frame.loc[i, ['order_id', 'order_line_id']] = None
    frame.loc[0, 'first_order_id'] = None
    frame.loc[1, 'first_orderitem_id'] = ''
    frame.loc[1:2, 'first_order_line_id'] = None
    frame.loc[2, 'first_orderitem_id'] = 'bad'
    frame.loc[4, 'line_status'] = 'X'
    frame.loc[5, ['order_placed_utc', 'max_approved_datetime']] = pd.NaT
    frame.loc[6, 'order_placed_utc'] = pd.NaT
    frame.loc[7, 'max_approved_datetime'] = pd.NaT
    associations, lines, audit, stats, bins = analysis.summarize(frame, *DATES)
    assert associations.eligibility.tolist() == analysis.STATES
    assert stats.N.iloc[0] == bins.order_lines.sum() == 1
    assert len(lines) == 5


@pytest.mark.parametrize('column,value', [('status_variants', 2), ('placement_variants', 2),
    ('eastern_variants', 2), ('rx_source_rows', 2), ('rx_id', None),
    ('order_line_id', 99), ('order_placed_eastern', pd.Timestamp('2026-08-15 12:00')),
    ('rx_creation_datetime', '2026-10-15')])
def test_invalid_sources(column, value):
    frame = source((1,))
    frame.loc[0, column] = value
    with pytest.raises(ValueError):
        analysis.summarize(frame, *DATES)


def test_duplicates_and_disagreeing_associations_rejected():
    frame = source((1,))
    with pytest.raises(ValueError, match='duplicate'):
        analysis.summarize(pd.concat([frame, frame]), *DATES)
    with pytest.raises(ValueError, match='inconsistent'):
        analysis.summarize(pd.concat([frame, frame.assign(rx_id='other', shipment_rows=3)]), *DATES)


def test_empty_and_missing_approval_and_companion(tmp_path):
    for frame in [source().iloc[:0], source().assign(max_approved_datetime=pd.NaT)]:
        charts = tmp_path / 'charts'
        charts.mkdir(exist_ok=True)
        (charts / (analysis.chart_stem({}) + '_histogram.png')).write_bytes(b'stale')
        _, stats = analysis.write_outputs(frame, dict(start_date=DATES[0], end_date_exclusive=DATES[1],
            extracted_at_utc='now'), charts, tmp_path / 'tables')
        assert stats.N.iloc[0] == 0 and pd.isna(stats.loc[0, 'median'])
        assert not (charts / (analysis.chart_stem({}) + '_histogram.png')).exists()
    _, _, audit, stats, _ = analysis.summarize(source((1,)).assign(
        order_placed_eastern=pd.NaT, eastern_variants=0, missing_eastern_rows=2), *DATES)
    assert stats.N.iloc[0] == 1
    assert audit.loc[audit.measure.eq('UTC/Eastern pairs checked'), 'count'].iloc[0] == 0


def test_sql_shipment_collapse_latest_populated_approval_and_both_keys():
    prescriptions = pd.DataFrame([dict(rx_id='RX', rx_creation_datetime=pd.Timestamp('2026-08-15'),
        approval_channel='CUSTOMER_UPLOAD', prescription_source='CMPU', is_vet_diet_flag=True,
        first_order_id=100, first_orderitem_id='001')])
    lines = pd.DataFrame([dict(order_id=order, order_line_id=line, order_order_line_status='D',
        order_placed_dttm=pd.Timestamp('2026-08-15 12:00'),
        order_placed_dttm_est=pd.Timestamp('2026-08-15 08:00'), max_approved_datetime=approval)
        for order, line, approval in [(100, 1, None), (100, 1, pd.Timestamp('2026-10-20')),
            (100, 1, pd.Timestamp('2026-08-16')), (101, 1, pd.Timestamp('2026-10-25')),
            (100, 2, pd.Timestamp('2026-10-25'))]])
    with duckdb.connect() as con:
        con.register('prescriptions_source', prescriptions)
        lines=lines.assign(order_line_created_dttm=lines.order_placed_dttm, order_line_created_dttm_est=lines.order_placed_dttm_est)
        con.register('lines_source', lines)
        con.execute('CREATE MACRO TRY_TO_NUMBER(x) AS TRY_CAST(x AS DECIMAL(38,0))')
        con.execute('CREATE MACRO REGEXP_LIKE(x, p) AS regexp_full_match(x, p)')
        sql = analysis.render_sql(*DATES).replace('EDLDB.BT_HCA_HCDM.RXP_PRESCRIPTIONS',
            'prescriptions_source').replace('EDLDB.BT_HCA_HCDM.ORDER_LINE_COST_MEASURES_RXP',
            'lines_source').replace('TIMESTAMP_NTZ', 'TIMESTAMP').replace('CURRENT_WAREHOUSE()', "'test'")
        result = con.execute(sql).df()
    assert len(result) == 1
    assert result.shipment_rows.iloc[0] == 3
    assert result.max_approved_datetime.iloc[0] == pd.Timestamp('2026-10-20')
    _, _, _, stats, bins = analysis.summarize(result, *DATES)
    assert stats.N.iloc[0] == bins.order_lines.sum() == 1


def test_print_only_dates_and_cache(tmp_path):
    with patch.object(analysis, 'ROOT', tmp_path), patch.object(analysis.subprocess, 'run') as run:
        result = CliRunner().invoke(analysis.main, ['--print-sql'])
        assert result.exit_code == 0
        run.assert_not_called()
        assert not list(tmp_path.iterdir())
    with pytest.raises(ValueError):
        analysis.render_sql(DATES[0], DATES[0])
    directory = tmp_path / 'data' / analysis.NAME / ('_'.join(DATES)+'_'+analysis.TIMING_VARIANT)
    directory.mkdir(parents=True)
    parquet = directory / 'source.parquet'
    source().to_parquet(parquet)
    metadata = dict(sql=analysis.render_sql(*DATES), parquet_sha256=analysis.digest(parquet),
        start_date=DATES[0], end_date_exclusive=DATES[1], extracted_at_utc='now')
    (directory / 'source.json').write_text(json.dumps(metadata))
    with patch.object(analysis, 'ROOT', tmp_path), patch.object(analysis.subprocess, 'run') as run:
        result = CliRunner().invoke(analysis.main, ['--cached'])
        assert result.exit_code == 0, result.output
        run.assert_not_called()
        parquet.write_bytes(b'tampered')
        result = CliRunner().invoke(analysis.main, ['--cached'])
        assert result.exit_code != 0 and 'fingerprint' in result.output


def uploads_source():
    frame = source((0, 1, -1, 2)).assign(upload_count=[2, 0, 1, 0],
        first_upload_at_utc=[pd.Timestamp('2026-08-01'), pd.NaT, pd.Timestamp('2026-08-15'), pd.NaT])
    frame['selected_upload_id']=frame.upload_count.gt(0).map({True:'U',False:None})
    frame['selected_upload_state']=frame.upload_count.gt(0).map({True:'ACCEPTED',False:None})
    frame['upload_state_changed_at_utc']=frame.first_upload_at_utc
    for col in analysis.AUDIT_COLUMNS:
        frame[col] = 0
    return frame


def test_upload_subset_repeated_uploads_and_missing_approval(tmp_path):
    frame = uploads_source()
    frame.loc[2, 'max_approved_datetime'] = pd.NaT
    selected = analysis.upload_subset(frame, *DATES, '2026-08-01')
    assert selected.rx_id.tolist() == ['RX0', 'RX2']
    metadata = dict(start_date=DATES[0], end_date_exclusive=DATES[1], with_upload=True,
                    upload_start_date='2026-08-01', extracted_at_utc='now')
    audit, stats = analysis.write_outputs(frame, metadata, tmp_path/'charts', tmp_path/'tables')
    assert stats.N.iloc[0] == 1
    assert audit.loc[audit.measure.eq('No matching upload'), 'count'].iloc[0] == 2
    assert audit.loc[(audit.grain == 'distinct matched lines') &
                     (audit.measure == 'Missing approval timestamp'), 'count'].iloc[0] == 1
    assert 'Has matching upload' in (tmp_path/'charts'/(analysis.chart_stem(metadata)+'.md')).read_text()


@pytest.mark.parametrize('column,value', [('upload_count', -1), ('invalid_upload_source_rows', 1),
    ('first_upload_at_utc', pd.Timestamp('2026-07-31')),
    ('first_upload_at_utc', pd.Timestamp('2026-10-26')), ('first_upload_at_utc', pd.NaT)])
def test_invalid_upload_evidence(column, value):
    frame = uploads_source()
    frame.loc[0, column] = value
    with pytest.raises(ValueError):
        analysis.upload_subset(frame, *DATES, '2026-08-01')


def test_upload_sql_dates_print_and_no_matches(tmp_path):
    sql = analysis.render_sql(*DATES, True, '2026-08-01')
    assert "created_ts_utc >= '2026-08-01'" in sql
    assert 't.rx_id = u.rx_id AND p.customer_id = u.customer_id' in sql
    assert "upload_type = 'DIET_PRESCRIPTION'" in sql
    with pytest.raises(ValueError):
        analysis.render_sql(*DATES, True, '2026-08-16')
    with patch.object(analysis, 'ROOT', tmp_path), patch.object(analysis.subprocess, 'run') as run:
        result = CliRunner().invoke(analysis.main, ['--with-upload', '--print-sql'])
        assert result.exit_code == 0
        run.assert_not_called()
        assert not list(tmp_path.iterdir())
    frame = uploads_source().assign(upload_count=0, first_upload_at_utc=pd.NaT, upload_state_changed_at_utc=pd.NaT, selected_upload_id=None, selected_upload_state=None)
    selected = analysis.upload_subset(frame, *DATES, '2026-08-01')
    assert selected.empty
    assert analysis.summarize(selected, *DATES)[3].N.iloc[0] == 0


def test_upload_elapsed_uses_earliest_entity_and_does_not_require_approval():
    frame = uploads_source()
    frame.loc[0, 'max_approved_datetime'] = pd.NaT
    selected = analysis.upload_subset(frame, *DATES, '2026-08-01')
    details, lines, audit, stats, bins = analysis.summarize(selected, *DATES, endpoint='upload')
    assert stats.N.iloc[0] == bins.order_lines.sum() == 2
    assert details.elapsed_hours.tolist() == [-348, -12]
    assert stats.loc[0, 'median'] == -180
    assert bins.lower_hours.min() == -348 and bins.upper_hours.max() == -11
    assert audit.loc[audit.measure.eq('Negative durations'), 'count'].iloc[0] == 2
    assert 'Missing upload timestamp' in audit.measure.tolist()
    frame.loc[0, 'upload_state_changed_at_utc'] = pd.Timestamp('2026-08-15 13:00')
    _, _, _, stats, bins = analysis.summarize(frame.iloc[[0]], *DATES, endpoint='upload')
    assert stats.N.iloc[0] == 1 and bins.lower_hours.iloc[0] == 1


def test_upload_endpoint_missing_timestamp_and_empty():
    for frame in [uploads_source().iloc[:0], uploads_source().assign(upload_state_changed_at_utc=pd.NaT)]:
        _, _, _, stats, bins = analysis.summarize(frame, *DATES, endpoint='upload')
        assert stats.N.iloc[0] == bins.order_lines.sum() == 0


def test_upload_endpoint_cache_separate_outputs_and_labels(tmp_path):
    directory = tmp_path/'data'/analysis.NAME/('_'.join(DATES)+'_with-upload_uploads-from-2026-08-01_uploads-end-2026-10-26_'+analysis.TIMING_VARIANT)
    directory.mkdir(parents=True)
    frame = uploads_source()
    frame.to_parquet(directory/'source.parquet')
    metadata = dict(sql=analysis.render_sql(*DATES, True), parquet_sha256=analysis.digest(directory/'source.parquet'),
        start_date=DATES[0], end_date_exclusive=DATES[1], extracted_at_utc='now', with_upload=True,
        upload_start_date='2026-08-01')
    (directory/'source.json').write_text(json.dumps(metadata))
    with patch.object(analysis, 'ROOT', tmp_path), patch.object(analysis.subprocess, 'run') as run:
        result = CliRunner().invoke(analysis.main, ['--endpoint', 'upload', '--cached'])
        assert result.exit_code == 0, result.output
        run.assert_not_called()
    output = tmp_path/'outputs/charts/2026-08-15_2026-10-14'
    notes = output/(analysis.chart_stem(dict(metadata, endpoint='upload'))+'.md')
    assert 'Approval timestamp is not required' in notes.read_text()
    assert all(path.is_file() for path in output.iterdir())
    assert not (tmp_path/'outputs/charts'/analysis.NAME).exists()
    tables = tmp_path/'outputs/tables/2026-08-15_2026-10-14'
    assert len(list(tables.glob('*.md'))) == 6
    assert all(path.name.startswith(analysis.chart_stem(dict(metadata, endpoint='upload')))
               for path in tables.iterdir())
    assert not (tmp_path/'outputs/tables'/analysis.NAME).exists()
    with patch.object(analysis.alt.TopLevelMixin, 'save', autospec=True) as save:
        _, _, _, stats, bins = analysis.summarize(frame.iloc[[0]], *DATES, endpoint='upload')
        analysis.figure(bins, int(stats.N.iloc[0]), None, ['Test'], endpoint='upload')
    spec=save.call_args.args[0].to_dict()
    assert 'accepted entity state change' in spec['title']['text']
    assert 'accepted entity state change' in spec['encoding']['x']['title']


def test_exclude_negative_keeps_zero_and_reconciles_details_bins_quantiles():
    frame = uploads_source().assign(upload_state_changed_at_utc=[pd.Timestamp('2026-08-15 11:59:59'),
        pd.Timestamp('2026-08-15 12:00'), pd.Timestamp('2026-08-15 13:00'), pd.Timestamp('2026-08-15 14:00')])
    details, lines, audit, stats, bins = analysis.summarize(frame, *DATES, endpoint='upload', exclude_negative=True)
    assert details.eligibility.tolist() == ['Negative duration', 'Eligible', 'Eligible', 'Eligible']
    assert len(lines) == 4
    assert stats.N.iloc[0] == bins.order_lines.sum() == 3
    assert stats.loc[0, 'minimum'] == bins.lower_hours.min() == 0
    assert stats.loc[0, 'median'] == 1
    assert stats.loc[0, 'p95'] == pytest.approx(1.9)
    assert audit.loc[(audit.grain == 'distinct matched lines') &
                     (audit.measure == 'Negative duration'), 'count'].iloc[0] == 1


def test_all_negative_population_is_empty_after_exclusion():
    _, _, _, stats, bins = analysis.summarize(uploads_source().iloc[[0]], *DATES,
                                             endpoint='upload', exclude_negative=True)
    assert stats.N.iloc[0] == bins.order_lines.sum() == 0
    assert pd.isna(stats.loc[0, 'median'])


def test_exact_cumulative_distribution_ties_and_exclusions():
    lines = pd.DataFrame({'elapsed_hours': [-1, 0, .5, .5, 10],
                          'eligibility': ['Negative duration'] + ['Eligible']*4})
    cdf = analysis.cumulative_distribution(lines)
    assert cdf.elapsed_hours.tolist() == [0, .5, 10]
    assert cdf.order_lines.tolist() == [1, 2, 1]
    assert cdf.cumulative_lines.tolist() == [1, 3, 4]
    assert cdf.cumulative_fraction.tolist() == [.25, .75, 1.]
    assert analysis.cumulative_distribution(lines.iloc[:0]).empty


def test_upload_to_approval_baseline_missing_endpoints_and_negative_exclusion():
    frame = source((3, 0, 1, 2)).assign(upload_state_changed_at_utc=[pd.Timestamp('2026-08-15 13:00'),
        pd.Timestamp('2026-08-15 12:00'), pd.Timestamp('2026-08-15 14:00'), pd.Timestamp('2026-08-15 13:00')])
    frame.loc[0, 'order_placed_utc'] = pd.NaT  # This metric requires upload and approval, not line creation.
    frame.loc[3, 'max_approved_datetime'] = pd.NaT
    details, lines, audit, stats, bins = analysis.summarize(frame, *DATES,
        endpoint='upload-to-approval', exclude_negative=True)
    assert details.eligibility.tolist() == ['Eligible', 'Eligible', 'Negative duration', 'Missing approval timestamp']
    assert details.elapsed_hours.iloc[:3].tolist() == [2, 0, -1]
    assert stats.N.iloc[0] == bins.order_lines.sum() == 2
    assert stats.loc[0, 'minimum'] == 0 and stats.loc[0, 'median'] == 1
    frame.loc[0, 'upload_state_changed_at_utc'] = pd.NaT
    assert analysis.summarize(frame, *DATES, endpoint='upload-to-approval')[0].eligibility.iloc[0] == 'Missing upload timestamp'
    assert analysis.summarize(frame.iloc[:0], *DATES, endpoint='upload-to-approval')[3].N.iloc[0] == 0


def test_upload_to_approval_chart_labels():
    cdf = pd.DataFrame({'elapsed_hours': [0, 1], 'order_lines': [1, 1],
                        'cumulative_lines': [1, 2], 'cumulative_fraction': [.5, 1.]})
    with patch.object(analysis.alt.TopLevelMixin, 'save', autospec=True) as save:
        analysis.cumulative_figure(cdf, 2, None, ['Test'], endpoint='upload-to-approval')
    spec = save.call_args.args[0].to_dict()
    assert 'accepted entity state change to latest approval' in spec['title']['text']
    assert spec['layer'][1]['encoding']['x']['title'] == 'Hours from accepted entity state change to latest approval'


@pytest.mark.parametrize('with_upload', [False, True])
def test_fresh_queries_and_history_stay_under_src_autogenerated(tmp_path, with_upload):
    frame = uploads_source() if with_upload else source()
    frame = frame.assign(extracted_at_session_time='2026-10-26', extraction_warehouse='TEST')

    def extract(args, **kwargs):
        query = Path(args[2])
        assert str(query).startswith(str(tmp_path / 'src/autogenerated'))
        assert query.name == ('cmpu_upload_to_max_approval_extract.sql' if with_upload
                              else 'cmpu_first_order_line_approval_extract.sql')
        assert query.read_text().strip() == analysis.render_sql(*DATES, with_upload).strip()
        assert args[args.index('--sql-log-dir') + 1].startswith('src/autogenerated/')
        frame.to_parquet(tmp_path / args[args.index('--output-parquet') + 1])

    with patch.object(analysis, 'ROOT', tmp_path), patch.object(analysis.subprocess, 'run', side_effect=extract), \
            patch.object(analysis, 'write_outputs', return_value=(pd.DataFrame(), pd.DataFrame())):
        result = CliRunner().invoke(analysis.main, ['--with-upload'] if with_upload else [])
    assert result.exit_code == 0, result.output
    assert not list((tmp_path / 'data').rglob('*.sql'))


def test_upload_followup_boundaries_keep_prescription_window_unchanged():
    frame = uploads_source().iloc[[0]].copy()
    for timestamp in ['2026-10-15', '2026-10-25 23:59:59.999999']:
        frame['first_upload_at_utc'] = pd.Timestamp(timestamp)
        assert len(analysis.upload_subset(frame, *DATES, '2026-08-01')) == 1
    frame['first_upload_at_utc'] = pd.Timestamp('2026-10-26')
    with pytest.raises(ValueError, match='upload outside search window'):
        analysis.upload_subset(frame, *DATES, '2026-08-01')
    frame['first_upload_at_utc'] = pd.Timestamp('2026-10-25')
    frame['rx_creation_datetime'] = '2026-10-15'
    with pytest.raises(ValueError, match='prescription outside cohort window'):
        analysis.upload_subset(frame, *DATES, '2026-08-01')
    sql = analysis.render_sql(*DATES, True)
    assert "rx_creation_datetime < '2026-10-15'::TIMESTAMP_NTZ" in sql
    assert "created_ts_utc < '2026-10-26'::TIMESTAMP_NTZ" in sql


def test_followup_subtitle_separates_prescription_and_upload_dates(tmp_path):
    metadata = dict(start_date=DATES[0], end_date_exclusive=DATES[1], with_upload=True,
                    upload_start_date='2026-08-01', extracted_at_utc='test', endpoint='upload-to-approval')
    with patch.object(analysis, 'figure'), patch.object(analysis, 'cumulative_figure'):
        analysis.write_outputs(uploads_source(), metadata, tmp_path/'charts', tmp_path/'tables')
    text = (tmp_path/'charts'/(analysis.chart_stem(metadata)+'.md')).read_text()
    assert 'Rx created 2026-08-15–2026-10-14' in text
    assert 'Uploads 2026-08-01–2026-10-25' in text


def test_chart_names_distinguish_measure_upload_window_and_negative_filter():
    metadata = dict(end_date_exclusive='2026-10-15', with_upload=True,
                    upload_start_date='2026-08-01', endpoint='upload-to-approval', exclude_negative=True)
    stem = analysis.chart_stem(metadata)
    assert stem == 'cmpu-d-lines_upload-to-max-approval_uploads-2026-08-01_2026-10-25_nonnegative_accepted-state-change_order-placed'
    variants = [metadata, dict(metadata, endpoint='upload'), dict(metadata, endpoint='approval'),
                dict(metadata, exclude_negative=False), dict(metadata, with_upload=False),
                dict(metadata, upload_end_date_exclusive='2026-10-15')]
    assert len({analysis.chart_stem(item) for item in variants}) == len(variants)


def test_short_gap_plot_keeps_exactly_sixty_seconds_and_reconciles_subset():
    seconds=[0,59.999999999,60,60.000000001,3600,-1]
    frame=pd.DataFrame({'elapsed_hours':np.array(seconds)/3600,
                        'eligibility':['Eligible']*5+['Negative duration']})
    bins,cdf,counts=analysis.short_gap_data(frame)
    assert bins.order_lines.sum()==3
    assert bins.loc[bins.lower_seconds.eq(59),'order_lines'].iloc[0]==2
    assert cdf.elapsed_seconds.max()==60 and cdf.cumulative_fraction.iloc[-1]==1
    assert counts.order_lines.tolist()==[5,3,2]


def test_short_gap_plots_use_seconds_and_no_day_reference_lines():
    frame=pd.DataFrame({'elapsed_hours':[0,5/3600,60/3600], 'eligibility':['Eligible']*3})
    bins,cdf,_=analysis.short_gap_data(frame)
    with patch.object(analysis.alt.TopLevelMixin,'save',autospec=True) as save:
        analysis.figure(bins,3,None,['Fixture'],endpoint='upload-to-approval',seconds=True)
    spec=save.call_args.args[0].to_dict()
    assert spec['encoding']['x']['scale']['domain']==[0,60]
    assert spec['encoding']['x']['title'].startswith('Seconds')
    with patch.object(analysis.alt.TopLevelMixin,'save',autospec=True) as save:
        analysis.cumulative_figure(cdf,3,None,['Fixture'],endpoint='upload-to-approval',seconds=True)
    spec=save.call_args.args[0].to_dict()
    assert 'layer' not in spec
    assert spec['encoding']['x']['scale']['domain']==[0,60]
    assert spec['encoding']['x']['field']=='elapsed_seconds'


def test_sixty_second_chart_filter_preserves_full_statistics_and_data(tmp_path):
    frame=source((1,1,1,1))
    gaps=[0,60,61,3600]
    frame['upload_state_changed_at_utc']=[t-pd.Timedelta(seconds=g) for t,g in zip(frame.max_approved_datetime,gaps)]
    metadata=dict(start_date=DATES[0],end_date_exclusive=DATES[1],extracted_at_utc='fixture',
                  endpoint='upload-to-approval',exclude_negative=True)
    with patch.object(analysis,'figure') as histogram,patch.object(analysis,'cumulative_figure') as cumulative:
        _,stats=analysis.write_outputs(frame,metadata,tmp_path/'charts',tmp_path/'tables',data_dir=tmp_path/'data')
    assert stats.N.iloc[0]==4
    assert histogram.call_args.args[1]==cumulative.call_args.args[1]==2
    assert histogram.call_args.kwargs['seconds'] and cumulative.call_args.kwargs['seconds']
    assert pd.read_parquet(tmp_path/'data/lines.parquet').elapsed_hours.max()==1
    assert pd.read_parquet(tmp_path/'data/cdf.parquet').cumulative_lines.iloc[-1]==4
    assert pd.read_parquet(tmp_path/'data/plot-cdf.parquet').cumulative_lines.iloc[-1]==2

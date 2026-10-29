"""Overall first-order placement to latest approval distribution (REFNUM 16)."""
from datetime import date, datetime, timedelta, timezone
import hashlib
import json
import subprocess
import sys

import altair as alt
import click
from jinja2 import Environment, StrictUndefined
import numpy as np
import pandas as pd

from src.python.create_cmpu_prescription_first_order_status import ROOT, RUNNER, TIMING_VARIANT, digest, AUDIT_COLUMNS
from src.python.create_cmpu_prescription_first_order_status import validate_accepted_uploads
from src.python.markdown_tables import markdown_table
from src.python.markdown_tables import write_text

NAME = 'cmpu-first-order-line-approval-distribution'
TEMPLATE = ROOT / 'src/sql/cmpu_first_order_line_approval_distribution.sql'
UPLOAD_FOLLOWUP_DAYS = 11
STATES = ['Missing order ID', 'Missing line ID', 'Invalid line ID', 'Unmatched line',
          'Non-D status', 'Missing both timestamps', 'Missing placement timestamp',
          'Missing approval timestamp', 'Eligible']


def render_sql(start, end, with_upload=False, upload_start='2026-08-01'):
    start, end = map(date.fromisoformat, [start, end])
    if start >= end:
        raise ValueError('require start < exclusive end')
    sql = Environment(undefined=StrictUndefined).from_string(TEMPLATE.read_text()).render(
        start_date=start.isoformat(), end_date=end.isoformat())
    if with_upload:
        upload_start = date.fromisoformat(upload_start)
        if upload_start > start:
            raise ValueError('require upload start <= prescription start')
        sql = Environment(undefined=StrictUndefined).from_string(
            (TEMPLATE.parent / 'cmpu_upload_to_max_approval_extract.sql').read_text()).render(
                timing_sql=sql, upload_start_date=upload_start.isoformat(),
                upload_end_date=(end + timedelta(days=UPLOAD_FOLLOWUP_DAYS)).isoformat())
    return sql


def upload_subset(frame, start, end, upload_start):
    """Validate the full timing cohort before restricting it to matching uploads."""
    frame = frame.rename(columns=str.lower).copy()
    summarize(frame.drop(columns=['upload_count', 'first_upload_at_utc', *AUDIT_COLUMNS]), start, end)
    for col in AUDIT_COLUMNS:
        if frame[col].isna().any() or frame[col].nunique() > 1:
            raise ValueError('inconsistent upload source audit')
    if len(frame) and frame.invalid_upload_source_rows.iloc[0]:
        raise ValueError('missing or duplicate upload source IDs')
    if (frame.upload_count.isna().any() or frame.upload_count.lt(0).any()
            or frame.upload_count.mod(1).ne(0).any()):
        raise ValueError('invalid upload counts')
    frame = validate_accepted_uploads(frame)
    uploaded = frame.first_upload_at_utc
    if frame.upload_count.gt(0).ne(uploaded.notna()).any():
        raise ValueError('upload counts and timestamps disagree')
    if not uploaded.dropna().between(pd.Timestamp(upload_start, tz='UTC'),
                                    pd.Timestamp(end, tz='UTC') + pd.Timedelta(days=UPLOAD_FOLLOWUP_DAYS),
                                    inclusive='left').all():
        raise ValueError('upload outside search window')
    return frame.loc[frame.upload_count.gt(0)].copy()


def summarize(frame, start, end, endpoint='approval', exclude_negative=False):
    frame = frame.rename(columns=str.lower).copy()
    endpoint_column = 'upload_state_changed_at_utc' if endpoint == 'upload' else 'max_approved_datetime'
    baseline_column = 'upload_state_changed_at_utc' if endpoint == 'upload-to-approval' else 'order_placed_utc'
    states = [state.replace('approval timestamp', 'upload timestamp') if endpoint == 'upload' else state
              for state in STATES]
    if endpoint == 'upload-to-approval':
        states = [state.replace('placement timestamp', 'upload timestamp') for state in states]
    if frame.rx_id.isna().any() or frame.rx_id.duplicated().any() or not frame.rx_source_rows.eq(1).all():
        raise ValueError('missing or duplicate prescription source IDs')
    if not frame.approval_channel.eq('CUSTOMER_UPLOAD').all():
        raise ValueError('unexpected approval channel')
    for col in ['rx_creation_datetime', 'order_placed_utc', 'order_placed_eastern', 'max_approved_datetime']:
        frame[col] = pd.to_datetime(frame[col], utc=True, errors='raise')
    if endpoint in ['upload', 'upload-to-approval']:
        frame['upload_state_changed_at_utc'] = pd.to_datetime(frame.upload_state_changed_at_utc, utc=True, errors='raise')
    if frame.rx_creation_datetime.isna().any() or not frame.rx_creation_datetime.between(
            pd.Timestamp(start, tz='UTC'), pd.Timestamp(end, tz='UTC'), inclusive='left').all():
        raise ValueError('prescription outside cohort window')
    matched = frame.order_id.notna()
    if (matched & (frame.order_id.ne(frame.first_order_id) | frame.order_line_id.ne(frame.first_order_line_id))).any():
        raise ValueError('first-order keys disagree')
    if (frame.loc[matched, ['status_variants', 'placement_variants']].ne(1).any().any()
            or frame.loc[matched, 'eastern_variants'].gt(1).any()):
        raise ValueError('conflicting shipment statuses or placement timestamps')
    eastern = frame.order_placed_utc.dt.tz_convert('America/New_York').dt.tz_localize(None)
    companion = frame.order_placed_eastern.dt.tz_localize(None)
    frame['timezone_checked'] = eastern.notna() & companion.notna()
    if (frame.timezone_checked & (eastern - companion).abs().gt(pd.Timedelta(seconds=1))).any():
        raise ValueError('UTC/Eastern placement timestamp disagreement')
    missing_line = frame.first_orderitem_id.astype('string').str.strip().fillna('').eq('')
    missing_placement, missing_endpoint = frame[baseline_column].isna(), frame[endpoint_column].isna()
    frame['eligibility'] = np.select([
        frame.first_order_id.isna(), missing_line, frame.first_order_line_id.isna(), ~matched,
        frame.line_status.ne('D').fillna(True).to_numpy(dtype=bool),
        missing_placement & missing_endpoint, missing_placement, missing_endpoint], states[:-1], default='Eligible')
    frame['approval_elapsed_hours'] = (frame.max_approved_datetime-frame.order_placed_utc).dt.total_seconds()/3600
    if 'upload_state_changed_at_utc' in frame:
        frame['accepted_elapsed_hours'] = (pd.to_datetime(frame.upload_state_changed_at_utc,utc=True)-frame.order_placed_utc).dt.total_seconds()/3600
    frame['elapsed_hours'] = (frame[endpoint_column] - frame[baseline_column]).dt.total_seconds() / 3600
    if exclude_negative:
        frame.loc[frame.eligibility.eq('Eligible') & frame.elapsed_hours.lt(0), 'eligibility'] = 'Negative duration'
        states.insert(-1, 'Negative duration')
    # Several prescriptions may refer to the same line; retain all associations separately.
    lines = frame.loc[matched].drop(columns=['rx_id', 'rx_source_rows', 'rx_creation_datetime',
        'approval_channel', 'first_order_id', 'first_orderitem_id', 'first_order_line_id']).copy()
    if lines.groupby(['order_id', 'order_line_id'], dropna=False).nunique(dropna=False).gt(1).any().any():
        raise ValueError('inconsistent repeated line associations')
    lines = lines.drop_duplicates(['order_id', 'order_line_id'])
    values = lines.loc[lines.eligibility.eq('Eligible'), 'elapsed_hours']
    if not np.isfinite(values).all():
        raise ValueError('nonfinite eligible durations')
    audit = [('prescription associations', 'Cohort', len(frame))]
    audit += [('prescription associations', state, int(frame.eligibility.eq(state).sum())) for state in states]
    audit += [('distinct matched lines', state, int(lines.eligibility.eq(state).sum())) for state in states[4:]]
    audit += [('distinct matched lines', 'Matched', len(lines)),
              ('distinct matched lines', 'Shipment rows', int(lines.shipment_rows.sum())),
              ('distinct matched lines', 'Repeated prescription associations', int(matched.sum() - len(lines))),
              ('distinct matched lines', 'UTC/Eastern pairs checked', int(lines.timezone_checked.sum())),
              ('distinct matched lines', 'Missing Eastern companion rows', int(lines.missing_eastern_rows.sum())),
              ('distinct matched lines', 'Missing approval shipment rows', int(lines.missing_approval_rows.sum())),
              ('eligible lines', 'Negative durations', int(values.lt(0).sum())),
              ('eligible lines', 'Over 24 hours', int(values.gt(24).sum()))]
    for flag in ['missing_accepted_state_change','state_change_before_entity_creation']:
        if flag in lines:
            audit.append(('quality',flag,int(lines[flag].sum())))
    stats = pd.DataFrame([{'N': len(values), 'minimum': values.min(), **{
        label: values.quantile(q, interpolation='linear') for label, q in
        [('p25', .25), ('median', .5), ('p75', .75), ('p95', .95)]}}])
    low = int(np.floor(values.min())) if len(values) else 0
    high = int(np.floor(values.max())) + 1 if len(values) else 1
    counts = np.bincount((np.floor(values).astype(int) - low).to_numpy(), minlength=high-low)
    bins = pd.DataFrame({'lower_hours': np.arange(low, high), 'upper_hours': np.arange(low+1, high+1),
                         'order_lines': counts})
    if counts.sum() != len(values) or frame.eligibility.value_counts().sum() != len(frame):
        raise ValueError('counts do not reconcile')
    return frame, lines, pd.DataFrame(audit, columns=['grain', 'measure', 'count']), stats, bins


def figure(bins, n, path, subtitle, endpoint='approval', seconds=False):
    endpoint_label = 'accepted entity state change' if endpoint == 'upload' else 'latest approval'
    origin_label = 'accepted entity state change' if endpoint == 'upload-to-approval' else 'order placement'
    title_origin = 'Accepted entity state change' if endpoint == 'upload-to-approval' else 'First-order placement'
    unit = 'Seconds' if seconds else 'Hours'
    lower, upper = ('lower_seconds','upper_seconds') if seconds else ('lower_hours','upper_hours')
    domain = [0,60] if seconds else [int(bins.lower_hours.min()),int(bins.upper_hours.max())]
    bin_note = '1-second bins; final bin includes 60 seconds' if seconds else '1-hour bins [lower, upper) · Full observed range'
    chart = alt.Chart(bins).mark_bar(color='#F28E2C', orient='vertical').encode(
        x=alt.X(lower+':Q', title=f'{unit} from {origin_label} to {endpoint_label}',
                axis=alt.Axis(tickCount=10),
                scale=alt.Scale(domain=domain, nice=False)),
        x2=upper+':Q', y=alt.Y('order_lines:Q', title='Prescription order lines',
                                  axis=alt.Axis(format=',d', tickMinStep=1)), y2=alt.datum(0),
        tooltip=[lower+':Q', upper+':Q', 'order_lines:Q']
    ).properties(width=1150, height=460, title=alt.Title(
        f'{title_origin} to {endpoint_label}', subtitle=subtitle +
        [f'Distinct D-status lines · N = {n:,} · {bin_note}'],
        anchor='start', fontSize=26, subtitleFontSize=17))
    chart.configure(background='transparent').configure_axis(labelFontSize=16, titleFontSize=18,
        titlePadding=14).configure_view(stroke=None).save(path, scale_factor=2)


def cumulative_distribution(lines):
    """Exact empirical CDF, grouping ties and using the eligible-line denominator."""
    values = lines.loc[lines.eligibility.eq('Eligible'), 'elapsed_hours']
    hours, counts = np.unique(values, return_counts=True)
    return pd.DataFrame({'elapsed_hours': hours, 'order_lines': counts,
                         'cumulative_lines': counts.cumsum(),
                         'cumulative_fraction': counts.cumsum() / len(values) if len(values) else []})


def cumulative_figure(cdf, n, path, subtitle, endpoint='upload', seconds=False):
    endpoint_label = 'accepted entity state change' if endpoint == 'upload' else 'latest approval'
    origin_label = 'accepted entity state change' if endpoint == 'upload-to-approval' else 'order placement'
    title_origin = 'accepted entity state change' if endpoint == 'upload-to-approval' else 'first-order placement'
    unit = 'Seconds' if seconds else 'Hours'
    value = 'elapsed_seconds' if seconds else 'elapsed_hours'
    domain = [0,60] if seconds else [float(np.floor(cdf.elapsed_hours.min())),float(np.floor(cdf.elapsed_hours.max())+1)]
    # Anchor the step function at zero probability before the first observation.
    anchor = pd.DataFrame([{value:domain[0], 'order_lines':0,'cumulative_lines':0,'cumulative_fraction':0.}])
    points = pd.concat([anchor, cdf], ignore_index=True).assign(sequence=lambda f: np.arange(len(f)))
    chart = alt.Chart(alt.Data(values=points.to_dict(orient='records'))).mark_line(
        color='#F28E2C', interpolate='step-after', strokeWidth=2).encode(
        x=alt.X(value+':Q', title=f'{unit} from {origin_label} to {endpoint_label}',
                axis=alt.Axis(tickCount=10),
                scale=alt.Scale(domain=domain, nice=False)),
        y=alt.Y('cumulative_fraction:Q', title='Cumulative share of prescription order lines',
                scale=alt.Scale(domain=[0, 1], nice=False), axis=alt.Axis(format='.0%')),
        order='sequence:Q', tooltip=[alt.Tooltip(value+':Q', format='.3f'),
            alt.Tooltip('cumulative_lines:Q', format=',d'),
            alt.Tooltip('cumulative_fraction:Q', format='.2%')]
    )
    references = alt.Chart(pd.DataFrame({'hours': [24, 72, 144, 240],
                                        'label': ['24 h', '72 h', '144 h', '240 h'],
                                        'label_height': [.05, .10, .05, .10]}))
    verticals = references.mark_rule(color='#555555', strokeDash=[6, 4], strokeWidth=1.5, clip=True).encode(
        x='hours:Q')
    labels = references.mark_text(color='#333333', fontSize=16, align='left', dx=5, clip=True).encode(
        x='hours:Q', y=alt.Y('label_height:Q', title='Cumulative share of prescription order lines',
                            scale=alt.Scale(domain=[0, 1], nice=False), axis=alt.Axis(format='.0%')), text='label:N')
    chart = (chart if seconds else verticals + chart + labels).properties(width=1150, height=460, title=alt.Title(
        f'Cumulative distribution · {title_origin} to {endpoint_label}',
        subtitle=subtitle + [f'Distinct D-status lines · N = {n:,} · Share with duration ≤ {unit.lower()} · Unbinned observations'],
        anchor='start', fontSize=26, subtitleFontSize=17))
    chart.configure(background='transparent').configure_axis(labelFontSize=16, titleFontSize=18,
        titlePadding=14).configure_view(stroke=None).save(path, scale_factor=2)


def short_gap_data(lines):
    """A conditional 0--60-second plot; full-range analysis stays unchanged."""
    eligible = lines.loc[lines.eligibility.eq('Eligible'), 'elapsed_hours']
    shown = eligible.loc[eligible.ge(0) & eligible.le(60/3600)] * 3600
    # Ordinary bins are [a,b); the final [59,60] bin retains exactly 60 seconds.
    indexes = np.minimum(np.floor(shown).astype(int),59)
    bins = pd.DataFrame({'lower_seconds':np.arange(60), 'upper_seconds':np.arange(1,61),
                         'order_lines':np.bincount(indexes.to_numpy(),minlength=60)})
    values,counts = np.unique(shown,return_counts=True)
    cdf = pd.DataFrame({'elapsed_seconds':values,'order_lines':counts,
                        'cumulative_lines':counts.cumsum(),
                        'cumulative_fraction':counts.cumsum()/len(shown) if len(shown) else []})
    summary = pd.DataFrame({'measure':['Full eligible lines','Shown: 0 through 60 seconds',
                                      'Omitted: over 60 seconds'],
                            'order_lines':[len(eligible),len(shown),int(eligible.gt(60/3600).sum())]})
    if bins.order_lines.sum()!=len(shown):
        raise ValueError('short-gap histogram counts do not reconcile')
    return bins,cdf,summary


def chart_stem(metadata):
    measure = {'approval': 'order-placement-to-max-approval',
               'upload': 'order-placement-to-accepted-state-change',
               'upload-to-approval': 'upload-to-max-approval'}[metadata.get('endpoint', 'approval')]
    stem = f'cmpu-d-lines_{measure}'
    if metadata.get('with_upload'):
        upload_end = date.fromisoformat(metadata.get('upload_end_date_exclusive') or
            (date.fromisoformat(metadata['end_date_exclusive']) + timedelta(days=UPLOAD_FOLLOWUP_DAYS)).isoformat())
        stem += f"_uploads-{metadata['upload_start_date']}_{upload_end - timedelta(days=1)}"
    if metadata.get('exclude_negative'):
        stem += '_nonnegative'
    return stem + '_' + TIMING_VARIANT


def write_outputs(frame, metadata, charts, tables, data_dir=None):
    original = frame
    endpoint = metadata.get('endpoint', 'approval')
    exclude_negative = metadata.get('exclude_negative', False)
    if metadata.get('with_upload'):
        frame = upload_subset(frame, metadata['start_date'], metadata['end_date_exclusive'],
                              metadata['upload_start_date'])
    associations, lines, audit, stats, bins = summarize(frame, metadata['start_date'], metadata['end_date_exclusive'], endpoint,
                                                       exclude_negative)
    if metadata.get('with_upload'):
        extra = [('prescription associations before upload filter', 'Cohort', len(original)),
                 ('prescription associations before upload filter', 'No matching upload', len(original)-len(frame))]
        extra += [('upload source', col, int(original[col].iloc[0]) if len(original) else None)
                  for col in AUDIT_COLUMNS]
        extra += [('upload source',key,int(original[key].iloc[0]) if len(original) and pd.notna(original[key].iloc[0]) else 0)
                  for key in ['accepted_window_upload_rows','excluded_window_upload_rows'] if key in original]
        audit = pd.concat([pd.DataFrame(extra, columns=audit.columns), audit], ignore_index=True)
    charts.mkdir(parents=True, exist_ok=True)
    tables.mkdir(parents=True, exist_ok=True)
    end = (date.fromisoformat(metadata['end_date_exclusive']) - timedelta(days=1)).isoformat()
    upload_end = (date.fromisoformat(metadata['end_date_exclusive'])
                  + timedelta(days=UPLOAD_FOLLOWUP_DAYS - 1)).isoformat()
    subtitle = [f"CMPU vet diet · CUSTOMER_UPLOAD · Rx created {metadata['start_date']}–{end} (UTC)"]
    if exclude_negative:
        subtitle.append('Nonnegative durations only · Negative durations excluded')
    upload_note = 'Upload presence is unrestricted. '
    if metadata.get('with_upload'):
        subtitle.append(f"Has matching upload · Uploads {metadata['upload_start_date']}–{upload_end} (UTC)")
        upload_note = ('Require a matching ACCEPTED DIET_PRESCRIPTION upload entity by expanded RX_ID and numeric CUSTOMER_ID. '
                       'No file-presence or upload-before-approval requirement. ')
    timing_note = ('Selected accepted entity STATE_CHANGED_TS_UTC − ORDER_PLACED_DTTM, hours. '
                   'Entity creation is within the stated search window; state-change time is unrestricted. Approval timestamp is not required. '
                   if endpoint == 'upload' else 'MAX_APPROVED_DATETIME − ORDER_PLACED_DTTM, hours. ')
    if endpoint == 'upload-to-approval':
        timing_note = ('MAX_APPROVED_DATETIME − selected accepted entity STATE_CHANGED_TS_UTC, hours. '
                       'Entity creation is within the stated search window; state-change time is unrestricted. Both endpoints required. ')
    shipment_note = ('Shipment rows collapsed to consistent line-placement timestamps. ' if endpoint == 'upload'
                     else 'Shipment rows collapsed using latest populated approval. ')
    range_note = ('Negative durations excluded from histogram and statistics; retained in details and eligibility audit. '
                  'All nonnegative outliers retained. ' if exclude_negative else 'Negative durations and outliers retained. ')
    plot_note = ('Plots show only gaps from 0 through 60 seconds; their CDF is normalized to that subset. Full-range statistics and data remain exported. ' if endpoint=='upload-to-approval' else '')
    note = (plot_note + ('Only current ACCEPTED entities qualify. Select earliest entity creation, with UPLOAD_ID ties; ' if metadata.get('with_upload') else '') + '\n\n'.join(subtitle) + '\n\n' + timing_note +
        'Both first-order keys matched; one count per distinct order/order-line pair, current line status D. '
        + shipment_note + upload_note +
        'Both timing endpoints required; no approval-date filter. ' + range_note +
        'Bins are [lower, upper); quantiles use unbinned hours with linear interpolation. '
        'Association and distinct-line audit counts have separate denominators; missing endpoints are not zero. '
        f"Extracted at {metadata['extracted_at_utc']}.\n\n")
    stem = chart_stem(metadata)
    for name, data in [('associations', associations), ('order-lines', lines), ('eligibility', audit),
                       ('statistics', stats), ('hourly-bins', bins)]:
        write_text(tables / f'{stem}_{name}.md', f'# {name.title()}\n\n' + note + markdown_table(data) + '\n')
    n = int(stats.N.iloc[0])
    histogram = charts / f'{stem}_histogram.png'
    cumulative = charts / f'{stem}_cumulative.png'
    plot_bins,plot_cdf,plot_counts = short_gap_data(lines) if endpoint=='upload-to-approval' else (None,None,None)
    plot_n = int(plot_counts.loc[1,'order_lines']) if plot_counts is not None else n
    plot_subtitle = subtitle + ([f'Showing {plot_n:,} of {n:,} eligible lines · Gaps over 60 seconds omitted'] if plot_counts is not None else [])
    if plot_n:
        figure(plot_bins if plot_bins is not None else bins,plot_n,histogram,plot_subtitle,endpoint,
               **({'seconds':True} if plot_counts is not None else {}))
    else:
        histogram.unlink(missing_ok=True)
    cdf = cumulative_distribution(lines)
    write_text(tables / f'{stem}_cumulative-distribution.md', '# Cumulative distribution\n\n' + note +
        'Exact empirical CDF: share of eligible lines with duration ≤ the listed hours.\n\n' +
        markdown_table(cdf) + '\n')
    if plot_n:
        cumulative_figure(plot_cdf if plot_cdf is not None else cdf,plot_n,cumulative,plot_subtitle,endpoint,
                          **({'seconds':True} if plot_counts is not None else {}))
    else:
        cumulative.unlink(missing_ok=True)
    if plot_counts is not None:
        write_text(tables/f'{stem}_plot-counts.md','# 60-second plot population\n\n'+plot_note+'\n\n'+markdown_table(plot_counts)+'\n')
    write_text(charts / f'{stem}.md', f'# First-order-line {endpoint} distribution\n\n' + note + (
        f'![Histogram]({histogram.name})\n\n![Cumulative distribution]({cumulative.name})\n' if plot_n else 'No eligible lines within the plot range; no figure generated.\n'))
    if data_dir is not None:
        data_dir.mkdir(parents=True,exist_ok=True)
        for name,data in [('associations',associations),('lines',lines),('audit',audit),('statistics',stats),('bins',bins),('cdf',cdf)]:
            data.to_parquet(data_dir/f'{name}.parquet',index=False)
        if plot_counts is not None:
            for name,data in [('plot-bins',plot_bins),('plot-cdf',plot_cdf),('plot-counts',plot_counts)]:
                data.to_parquet(data_dir/f'{name}.parquet',index=False)
    return audit, stats


def load_source(start_date, end_date, with_upload=False, upload_start_date='2026-08-01', cached=False):
    """Read or refresh the shared timing extract, validating SQL, dates and fingerprint."""
    sql = render_sql(start_date, end_date, with_upload, upload_start_date)
    upload_end_exclusive = (date.fromisoformat(end_date) + timedelta(days=UPLOAD_FOLLOWUP_DAYS)).isoformat()
    period = f'{start_date}_{end_date}'
    if with_upload:
        period += f'_with-upload_uploads-from-{upload_start_date}_uploads-end-{upload_end_exclusive}'
    period += '_' + TIMING_VARIANT
    directory = ROOT / 'data' / NAME / period
    parquet, manifest = directory / 'source.parquet', directory / 'source.json'
    if cached:
        metadata = json.loads(manifest.read_text())
        if (metadata.get('sql') != sql or metadata.get('parquet_sha256') != digest(parquet)
                or [metadata.get(k) for k in ['start_date', 'end_date_exclusive']] != [start_date, end_date]
                or bool(metadata.get('with_upload')) != with_upload
                or (with_upload and metadata.get('upload_start_date') != upload_start_date)):
            raise ValueError('cached SQL, dates or fingerprint differs; refresh extract')
        frame = pd.read_parquet(parquet).rename(columns=str.lower)
    else:
        directory.mkdir(parents=True, exist_ok=True)
        sql_directory = ROOT / 'src/autogenerated' / NAME / period
        sql_directory.mkdir(parents=True, exist_ok=True)
        query_name = ('cmpu_upload_to_max_approval_extract.sql' if with_upload
                      else 'cmpu_first_order_line_approval_extract.sql')
        query = sql_directory / query_name
        write_text(query, sql + '\n')
        manifest.unlink(missing_ok=True)
        subprocess.run([sys.executable, str(RUNNER), str(query), '--output-parquet', str(parquet.relative_to(ROOT)),
                        '--sql-log-dir', str((sql_directory / 'sql-history').relative_to(ROOT))], cwd=ROOT, check=True)
        frame = pd.read_parquet(parquet).rename(columns=str.lower)
        validation = upload_subset(frame, start_date, end_date, upload_start_date) if with_upload else frame
        summarize(validation, start_date, end_date)
        metadata = dict(sql=sql, sql_sha256=hashlib.sha256(sql.encode()).hexdigest(),
            parquet_sha256=digest(parquet), start_date=start_date, end_date_exclusive=end_date,
            prescription_end_date_exclusive=end_date,
            extracted_at_utc=datetime.now(timezone.utc).isoformat(),
            source_extracted_at=frame.extracted_at_session_time.unique().tolist(),
            warehouse=frame.extraction_warehouse.unique().tolist())
        if with_upload:
            metadata.update(with_upload=True, upload_start_date=upload_start_date,
                            upload_end_date_exclusive=upload_end_exclusive,
                            upload_followup_days=UPLOAD_FOLLOWUP_DAYS)
        write_text(manifest, json.dumps(metadata, indent=2) + '\n')
    return frame, metadata, period


@click.command()
@click.option('--start-date', default='2026-08-15', show_default=True)
@click.option('--end-date', default='2026-10-15', show_default=True,
              help='Exclusive prescription end; upload creation extends 11 days beyond this date.')
@click.option('--cached', is_flag=True)
@click.option('--print-sql', is_flag=True)
@click.option('--with-upload', is_flag=True)
@click.option('--upload-start-date', default='2026-08-01', show_default=True)
@click.option('--endpoint', type=click.Choice(['approval', 'upload', 'upload-to-approval']), default='approval', show_default=True)
@click.option('--exclude-negative', is_flag=True)
def main(start_date, end_date, cached, print_sql, with_upload, upload_start_date, endpoint, exclude_negative):
    try:
        with_upload = with_upload or endpoint in ['upload', 'upload-to-approval']
        sql = render_sql(start_date, end_date, with_upload, upload_start_date)
        if print_sql:
            click.echo(sql)
            return
        frame, metadata, period = load_source(start_date, end_date, with_upload, upload_start_date, cached)
        chart_end = (date.fromisoformat(end_date) - timedelta(days=1)).isoformat()
        charts = ROOT / 'outputs/charts' / f'{start_date}_{chart_end}'
        output_metadata = dict(metadata, endpoint=endpoint, exclude_negative=exclude_negative)
        audit, stats = write_outputs(frame, output_metadata, charts,
                                     ROOT / 'outputs/tables' / f'{start_date}_{chart_end}',
                                     data_dir=ROOT/'data'/NAME/period/(endpoint+('_nonnegative' if exclude_negative else '')))
        click.echo(audit.to_string(index=False) + '\n\n' + stats.to_string(index=False))
        click.echo(f'Chart notes: {charts / (chart_stem(output_metadata) + ".md")}')
        click.echo(f'Tables: {ROOT / "outputs/tables" / f"{start_date}_{chart_end}"}')
    except (ValueError, OSError, KeyError, subprocess.CalledProcessError) as error:
        raise click.ClickException(str(error)) from error


if __name__ == '__main__':
    main()

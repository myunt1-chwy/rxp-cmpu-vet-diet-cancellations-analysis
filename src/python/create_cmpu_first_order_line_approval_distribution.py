"""Overall first-order-line creation to latest approval distribution (REFNUM 16)."""
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

from src.python.create_cmpu_prescription_first_order_status import ROOT, RUNNER, digest, AUDIT_COLUMNS
from src.python.markdown_tables import markdown_table

NAME = 'cmpu-first-order-line-approval-distribution'
TEMPLATE = ROOT / 'src/sql/cmpu_first_order_line_approval_distribution.sql'
UPLOAD_FOLLOWUP_DAYS = 11
STATES = ['Missing order ID', 'Missing line ID', 'Invalid line ID', 'Unmatched line',
          'Non-D status', 'Missing both timestamps', 'Missing creation timestamp',
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
    uploaded = pd.to_datetime(frame.first_upload_at_utc, utc=True, errors='raise')
    if frame.upload_count.gt(0).ne(uploaded.notna()).any():
        raise ValueError('upload counts and timestamps disagree')
    if not uploaded.dropna().between(pd.Timestamp(upload_start, tz='UTC'),
                                    pd.Timestamp(end, tz='UTC') + pd.Timedelta(days=UPLOAD_FOLLOWUP_DAYS),
                                    inclusive='left').all():
        raise ValueError('upload outside search window')
    return frame.loc[frame.upload_count.gt(0)].copy()


def summarize(frame, start, end, endpoint='approval', exclude_negative=False):
    frame = frame.rename(columns=str.lower).copy()
    endpoint_column = 'first_upload_at_utc' if endpoint == 'upload' else 'max_approved_datetime'
    baseline_column = 'first_upload_at_utc' if endpoint == 'upload-to-approval' else 'line_created_utc'
    states = [state.replace('approval timestamp', 'upload timestamp') if endpoint == 'upload' else state
              for state in STATES]
    if endpoint == 'upload-to-approval':
        states = [state.replace('creation timestamp', 'upload timestamp') for state in states]
    if frame.rx_id.isna().any() or frame.rx_id.duplicated().any() or not frame.rx_source_rows.eq(1).all():
        raise ValueError('missing or duplicate prescription source IDs')
    if not frame.approval_channel.eq('CUSTOMER_UPLOAD').all():
        raise ValueError('unexpected approval channel')
    for col in ['rx_creation_datetime', 'line_created_utc', 'line_created_eastern', 'max_approved_datetime']:
        frame[col] = pd.to_datetime(frame[col], utc=True, errors='raise')
    if endpoint in ['upload', 'upload-to-approval']:
        frame['first_upload_at_utc'] = pd.to_datetime(frame.first_upload_at_utc, utc=True, errors='raise')
    if frame.rx_creation_datetime.isna().any() or not frame.rx_creation_datetime.between(
            pd.Timestamp(start, tz='UTC'), pd.Timestamp(end, tz='UTC'), inclusive='left').all():
        raise ValueError('prescription outside cohort window')
    matched = frame.order_id.notna()
    if (matched & (frame.order_id.ne(frame.first_order_id) | frame.order_line_id.ne(frame.first_order_line_id))).any():
        raise ValueError('first-order keys disagree')
    if (frame.loc[matched, ['status_variants', 'creation_variants']].ne(1).any().any()
            or frame.loc[matched, 'eastern_variants'].gt(1).any()):
        raise ValueError('conflicting shipment statuses or creation timestamps')
    eastern = frame.line_created_utc.dt.tz_convert('America/New_York').dt.tz_localize(None)
    companion = frame.line_created_eastern.dt.tz_localize(None)
    frame['timezone_checked'] = eastern.notna() & companion.notna()
    if (frame.timezone_checked & (eastern - companion).abs().gt(pd.Timedelta(seconds=1))).any():
        raise ValueError('UTC/Eastern creation timestamp disagreement')
    missing_line = frame.first_orderitem_id.astype('string').str.strip().fillna('').eq('')
    missing_creation, missing_endpoint = frame[baseline_column].isna(), frame[endpoint_column].isna()
    frame['eligibility'] = np.select([
        frame.first_order_id.isna(), missing_line, frame.first_order_line_id.isna(), ~matched,
        frame.line_status.ne('D').fillna(True).to_numpy(dtype=bool),
        missing_creation & missing_endpoint, missing_creation, missing_endpoint], states[:-1], default='Eligible')
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


def figure(bins, n, path, subtitle, endpoint='approval'):
    endpoint_label = 'earliest matching upload' if endpoint == 'upload' else 'latest approval'
    origin_label = 'earliest matching upload' if endpoint == 'upload-to-approval' else 'order-line creation'
    title_origin = 'Earliest matching upload' if endpoint == 'upload-to-approval' else 'First-order-line creation'
    chart = alt.Chart(bins).mark_bar(color='#F28E2C', orient='vertical').encode(
        x=alt.X('lower_hours:Q', title=f'Hours from {origin_label} to {endpoint_label}',
                axis=alt.Axis(tickCount=10),
                scale=alt.Scale(domain=[int(bins.lower_hours.min()), int(bins.upper_hours.max())], nice=False)),
        x2='upper_hours:Q', y=alt.Y('order_lines:Q', title='Prescription order lines',
                                  axis=alt.Axis(format=',d', tickMinStep=1)), y2=alt.datum(0),
        tooltip=['lower_hours:Q', 'upper_hours:Q', 'order_lines:Q']
    ).properties(width=1150, height=460, title=alt.Title(
        f'{title_origin} to {endpoint_label}', subtitle=subtitle +
        [f'Distinct D-status lines · N = {n:,} · 1-hour bins [lower, upper) · Full observed range'],
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


def cumulative_figure(cdf, n, path, subtitle, endpoint='upload'):
    endpoint_label = 'earliest matching upload' if endpoint == 'upload' else 'latest approval'
    origin_label = 'earliest matching upload' if endpoint == 'upload-to-approval' else 'order-line creation'
    title_origin = 'earliest matching upload' if endpoint == 'upload-to-approval' else 'first-order-line creation'
    # Anchor the step function at zero probability before the first observation.
    anchor = pd.DataFrame([dict(elapsed_hours=float(np.floor(cdf.elapsed_hours.min())),
                                order_lines=0, cumulative_lines=0, cumulative_fraction=0.)])
    points = pd.concat([anchor, cdf], ignore_index=True).assign(sequence=lambda f: np.arange(len(f)))
    chart = alt.Chart(alt.Data(values=points.to_dict(orient='records'))).mark_line(
        color='#F28E2C', interpolate='step-after', strokeWidth=2).encode(
        x=alt.X('elapsed_hours:Q', title=f'Hours from {origin_label} to {endpoint_label}',
                axis=alt.Axis(tickCount=10),
                scale=alt.Scale(domain=[float(np.floor(cdf.elapsed_hours.min())),
                                       float(np.floor(cdf.elapsed_hours.max()) + 1)], nice=False)),
        y=alt.Y('cumulative_fraction:Q', title='Cumulative share of prescription order lines',
                scale=alt.Scale(domain=[0, 1], nice=False), axis=alt.Axis(format='.0%')),
        order='sequence:Q', tooltip=[alt.Tooltip('elapsed_hours:Q', format='.3f'),
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
    chart = (verticals + chart + labels).properties(width=1150, height=460, title=alt.Title(
        f'Cumulative distribution · {title_origin} to {endpoint_label}',
        subtitle=subtitle + [f'Distinct D-status lines · N = {n:,} · Share with duration ≤ hours · Unbinned observations'],
        anchor='start', fontSize=26, subtitleFontSize=17))
    chart.configure(background='transparent').configure_axis(labelFontSize=16, titleFontSize=18,
        titlePadding=14).configure_view(stroke=None).save(path, scale_factor=2)


def chart_stem(metadata):
    measure = {'approval': 'line-creation-to-max-approval',
               'upload': 'line-creation-to-upload',
               'upload-to-approval': 'upload-to-max-approval'}[metadata.get('endpoint', 'approval')]
    stem = f'cmpu-d-lines_{measure}'
    if metadata.get('with_upload'):
        upload_end = date.fromisoformat(metadata.get('upload_end_date_exclusive') or
            (date.fromisoformat(metadata['end_date_exclusive']) + timedelta(days=UPLOAD_FOLLOWUP_DAYS)).isoformat())
        stem += f"_uploads-{metadata['upload_start_date']}_{upload_end - timedelta(days=1)}"
    if metadata.get('exclude_negative'):
        stem += '_nonnegative'
    return stem


def write_outputs(frame, metadata, charts, tables):
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
        upload_note = ('Require a matching DIET_PRESCRIPTION upload entity by expanded RX_ID and numeric CUSTOMER_ID. '
                       'No file-presence or upload-before-approval requirement. ')
    timing_note = ('Earliest matching upload CREATED_TS_UTC − ORDER_LINE_CREATED_DTTM, hours. '
                   'Earliest upload is within the stated upload search window. Approval timestamp is not required. '
                   if endpoint == 'upload' else 'MAX_APPROVED_DATETIME − ORDER_LINE_CREATED_DTTM, hours. ')
    if endpoint == 'upload-to-approval':
        timing_note = ('MAX_APPROVED_DATETIME − earliest matching upload CREATED_TS_UTC, hours. '
                       'Earliest upload is within the stated upload search window. Both endpoints required. ')
    shipment_note = ('Shipment rows collapsed to consistent line-creation timestamps. ' if endpoint == 'upload'
                     else 'Shipment rows collapsed using latest populated approval. ')
    range_note = ('Negative durations excluded from histogram and statistics; retained in details and eligibility audit. '
                  'All nonnegative outliers retained. ' if exclude_negative else 'Negative durations and outliers retained. ')
    note = ('\n\n'.join(subtitle) + '\n\n' + timing_note +
        'Both first-order keys matched; one count per distinct order/order-line pair, current line status D. '
        + shipment_note + upload_note +
        'Both timing endpoints required; no approval-date filter. ' + range_note +
        'Bins are [lower, upper); quantiles use unbinned hours with linear interpolation. '
        'Association and distinct-line audit counts have separate denominators; missing endpoints are not zero. '
        f"Extracted at {metadata['extracted_at_utc']}.\n\n")
    for name, data in [('associations', associations), ('order-lines', lines), ('eligibility', audit),
                       ('statistics', stats), ('hourly-bins', bins)]:
        (tables / f'{name}.md').write_text(f'# {name.title()}\n\n' + note + markdown_table(data) + '\n')
    n = int(stats.N.iloc[0])
    stem = chart_stem(metadata)
    histogram = charts / f'{stem}_histogram.png'
    cumulative = charts / f'{stem}_cumulative.png'
    if n:
        figure(bins, n, histogram, subtitle, endpoint)
    else:
        histogram.unlink(missing_ok=True)
    cdf = cumulative_distribution(lines)
    (tables / 'cumulative-distribution.md').write_text('# Cumulative distribution\n\n' + note +
        'Exact empirical CDF: share of eligible lines with duration ≤ the listed hours.\n\n' +
        markdown_table(cdf) + '\n')
    if n:
        cumulative_figure(cdf, n, cumulative, subtitle, endpoint)
    else:
        cumulative.unlink(missing_ok=True)
    (charts / f'{stem}.md').write_text(f'# First-order-line {endpoint} distribution\n\n' + note + (
        f'![Histogram]({histogram.name})\n\n![Cumulative distribution]({cumulative.name})\n' if n else 'No eligible lines; no figure generated.\n'))
    return audit, stats


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
        upload_end_exclusive = (date.fromisoformat(end_date) + timedelta(days=UPLOAD_FOLLOWUP_DAYS)).isoformat()
        period = f'{start_date}_{end_date}'
        if with_upload:
            period += f'_with-upload_uploads-from-{upload_start_date}_uploads-end-{upload_end_exclusive}'
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
            query.write_text(sql + '\n')
            manifest.unlink(missing_ok=True)
            subprocess.run([sys.executable, str(RUNNER), str(query), '--output-parquet', str(parquet.relative_to(ROOT)),
                            '--sql-log-dir', str((sql_directory / 'sql-history').relative_to(ROOT))], cwd=ROOT, check=True)
            frame = pd.read_parquet(parquet).rename(columns=str.lower)
            validation = upload_subset(frame, start_date, end_date, upload_start_date) if with_upload else frame
            summarize(validation, start_date, end_date, endpoint)
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
            manifest.write_text(json.dumps(metadata, indent=2) + '\n')
        output_period = period + ('_upload-time' if endpoint == 'upload' else '')
        if endpoint == 'upload-to-approval':
            output_period += '_upload-to-approval'
        if exclude_negative:
            output_period += '_nonnegative'
        chart_end = (date.fromisoformat(end_date) - timedelta(days=1)).isoformat()
        charts = ROOT / 'outputs/charts' / f'{start_date}_{chart_end}'
        output_metadata = dict(metadata, endpoint=endpoint, exclude_negative=exclude_negative)
        audit, stats = write_outputs(frame, output_metadata, charts,
                                     ROOT / 'outputs/tables' / NAME / output_period)
        click.echo(audit.to_string(index=False) + '\n\n' + stats.to_string(index=False))
        click.echo(f'Chart notes: {charts / (chart_stem(output_metadata) + ".md")}')
    except (ValueError, OSError, KeyError, subprocess.CalledProcessError) as error:
        raise click.ClickException(str(error)) from error


if __name__ == '__main__':
    main()

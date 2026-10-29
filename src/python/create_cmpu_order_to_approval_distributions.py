"""First-order placement to first-usage approval, one observation per prescription."""
from datetime import date, datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import altair as alt
import click
from jinja2 import Environment, StrictUndefined
import numpy as np
import pandas as pd

from src.python.create_cmpu_prescription_first_order_status import (
    AUDIT_COLUMNS, ROOT, RUNNER, TIMING_VARIANT, digest, period_name,
)
from src.python.create_cmpu_prescription_first_order_status import validate_accepted_uploads
from src.python.markdown_tables import markdown_table, table_layout
from src.python.markdown_tables import write_text

NAME = 'cmpu-order-to-approval-distributions'
TEMPLATE = ROOT / 'src/sql/cmpu_order_to_approval_distributions.sql'
GROUPS = ['Has matching accepted upload', 'No matching accepted upload']
COLORS = ['#F28E2C', '#8CC9EE']
STATES = ['No first order ID', 'First order not found', 'Unknown order status',
          'Canceled', 'Missing both timestamps', 'Missing order timestamp',
          'Missing approval timestamp', 'Eligible']


def render_sql(start, end, upload_start):
    start, end, upload_start = map(date.fromisoformat, [start, end, upload_start])
    if not upload_start <= start < end:
        raise ValueError('require upload start <= prescription start < exclusive end')
    return Environment(undefined=StrictUndefined).from_string(TEMPLATE.read_text()).render(
        start_date=start.isoformat(), end_date=end.isoformat(), upload_start_date=upload_start.isoformat())


def summarize(frame, start, end, upload_start):
    frame = frame.rename(columns=str.lower).copy()
    if frame.rx_id.isna().any() or frame.rx_id.duplicated().any() or not frame.rx_source_rows.eq(1).all():
        raise ValueError('missing or duplicate prescription source IDs')
    if not frame.order_source_rows.isin([0, 1]).all():
        raise ValueError('duplicate order source keys')
    if (frame.upload_count.isna().any() or frame.upload_count.lt(0).any()
            or frame.upload_count.mod(1).ne(0).any()):
        raise ValueError('invalid upload counts')
    for column in AUDIT_COLUMNS:
        if frame[column].isna().any() or frame[column].nunique() > 1:
            raise ValueError('inconsistent source audit')
    if len(frame) and frame.invalid_upload_source_rows.iloc[0]:
        raise ValueError('missing or duplicate upload source keys')
    if not frame.approval_channel.eq('CUSTOMER_UPLOAD').all():
        raise ValueError('unexpected approval channel')
    for col in ['rx_creation_datetime', 'first_usage_approved_datetime', 'first_upload_at_utc',
                'order_placed_at_utc', 'order_placed_at_eastern']:
        frame[col] = pd.to_datetime(frame[col], utc=True, errors='raise')
    if (frame.rx_creation_datetime.isna().any()
            or not frame.rx_creation_datetime.between(pd.Timestamp(start, tz='UTC'),
                     pd.Timestamp(end, tz='UTC'), inclusive='left').all()):
        raise ValueError('prescription outside cohort window')
    frame = validate_accepted_uploads(frame)
    frame['accepted_elapsed_hours'] = (frame.upload_state_changed_at_utc - frame.order_placed_at_utc).dt.total_seconds()/3600
    uploaded = frame.first_upload_at_utc
    if frame.upload_count.gt(0).ne(uploaded.notna()).any():
        raise ValueError('upload counts and timestamps disagree')
    if not uploaded.dropna().between(pd.Timestamp(upload_start, tz='UTC'),
                                    pd.Timestamp(end, tz='UTC'), inclusive='left').all():
        raise ValueError('upload outside search window')
    if (frame.first_order_id.isna() & frame.order_source_rows.ne(0)).any():
        raise ValueError('matched order without first order ID')
    frame['upload_group'] = np.where(frame.upload_count.gt(0), GROUPS[0], GROUPS[1])
    status = frame.order_status.astype('string').str.strip().str.upper().replace('', pd.NA)
    order_missing = frame.order_placed_at_utc.isna()
    approval_missing = frame.first_usage_approved_datetime.isna()
    frame['eligibility'] = np.select([
        frame.first_order_id.isna(), frame.order_source_rows.eq(0), status.isna(),
        status.eq('X').fillna(False).to_numpy(dtype=bool), order_missing & approval_missing,
        order_missing, approval_missing], STATES[:-1], default='Eligible')
    frame['elapsed_hours'] = ((frame.first_usage_approved_datetime - frame.order_placed_at_utc)
                              .dt.total_seconds() / 3600)
    selected = frame.loc[frame.eligibility.eq('Eligible')].copy()
    if not np.isfinite(selected.elapsed_hours).all():
        raise ValueError('nonfinite eligible durations')
    # Eastern companion is a wall-clock timestamp, despite parsing as UTC above.
    eastern_wall = frame.order_placed_at_utc.dt.tz_convert('America/New_York').dt.tz_localize(None)
    companion = frame.order_placed_at_eastern.dt.tz_localize(None)
    checked = eastern_wall.notna() & companion.notna()
    mismatched = checked & (eastern_wall - companion).abs().gt(pd.Timedelta(seconds=1))
    frame['order_timezone_mismatch'] = mismatched
    if mismatched.any():
        raise ValueError('UTC/Eastern order timestamp disagreement exceeds one second')
    audit, stats, bins = [], [], []
    low = int(np.floor(selected.elapsed_hours.min())) if len(selected) else 0
    high = int(np.floor(selected.elapsed_hours.max())) + 1 if len(selected) else 1
    for group in GROUPS:
        population = frame.loc[frame.upload_group.eq(group)]
        values = selected.loc[selected.upload_group.eq(group), 'elapsed_hours']
        counts = population.eligibility.value_counts()
        row = {'upload_group': group, 'cohort': len(population),
               **{state: int(counts.get(state, 0)) for state in STATES},
               'negative_durations': int(values.lt(0).sum()),
               'over_24h': int(values.gt(24).sum()),
               'timezone_pairs_checked': int(checked.loc[population.index].sum()),
               'timezone_companion_missing': int((population.order_placed_at_utc.notna()
                                                  & population.order_placed_at_eastern.isna()).sum())}
        if sum(row[state] for state in STATES) != len(population):
            raise ValueError('eligibility does not reconcile')
        audit.append(row)
        stats.append({'upload_group': group, 'N': len(values), 'minimum': values.min(),
                      **{label: values.quantile(q, interpolation='linear') for label, q in
                         [('p25', .25), ('median', .5), ('p75', .75), ('p95', .95)]}})
        counts = np.bincount((np.floor(values).astype(int) - low).to_numpy(), minlength=high-low)
        if counts.sum() != len(values):
            raise ValueError('histogram counts do not reconcile')
        bins.append(pd.DataFrame({'upload_group': group, 'lower_hours': np.arange(low, high),
                                  'upper_hours': np.arange(low+1, high+1), 'prescriptions': counts}))
    return frame, pd.DataFrame(audit), pd.DataFrame(stats), pd.concat(bins, ignore_index=True)


def figures(stats, bins, directory, subtitle):
    directory.mkdir(parents=True, exist_ok=True)
    panels = []
    domain = [int(bins.lower_hours.min()), int(bins.upper_hours.max())]
    ymax = max(1, int(np.ceil(bins.prescriptions.max() * 1.05)))
    for group, color in zip(GROUPS, COLORS):
        n = int(stats.loc[stats.upload_group.eq(group), 'N'].iloc[0])
        chart = alt.Chart(bins.loc[bins.upload_group.eq(group)]).mark_bar(color=color, orient='vertical').encode(
            x=alt.X('lower_hours:Q', title='Hours from first order placement to first-usage approval',
                    scale=alt.Scale(domain=domain, nice=False)), x2='upper_hours:Q',
            y=alt.Y('prescriptions:Q', title='Prescriptions', scale=alt.Scale(domain=[0, ymax])), y2=alt.datum(0),
            tooltip=['lower_hours:Q', 'upper_hours:Q', 'prescriptions:Q'])
        if not n:
            chart = alt.layer(chart, alt.Chart(pd.DataFrame({'label': ['No eligible prescriptions']}))
                              .mark_text(fontSize=20).encode(text='label:N'))
        panels.append(chart.properties(width=1200, height=300, title=f'{group} · N = {n:,}'))
    chart = alt.vconcat(*panels, spacing=35).resolve_scale(x='shared', y='shared').properties(
        title=alt.Title('Order to first-usage approval · 1-hour bins', subtitle=subtitle,
                        anchor='start', fontSize=26, subtitleFontSize=17))
    chart.configure(background='transparent').configure_axis(labelFontSize=16, titleFontSize=18,
        titlePadding=14).configure_title(fontSize=22).configure_view(stroke=None).save(
            directory / 'distributions.png', scale_factor=2)
    headers = ['Upload group', 'N', 'Min (h)', '25th (h)', 'Median (h)', '75th (h)', '95th (h)']
    rows = [headers]
    for row in stats.itertuples(index=False, name=None):
        rows.append([str(row[0]), f'{row[1]:,}', *['—' if pd.isna(v) else f'{v:,.2f}' for v in row[2:]]])
    cells = pd.DataFrame([{'x': col, 'y': r, 'text': value} for r, row in enumerate(rows)
                          for col, value in enumerate(row)])
    positions = [155, 355, 495, 635, 775, 915, 1055]
    cells['position'] = cells.x.map(dict(enumerate(positions)))
    cells['color'] = cells.y.map({0: '#333333', 1: '#A95808', 2: '#28749B'})
    table = alt.Chart(cells).mark_text(fontSize=20).encode(
        x=alt.X('position:Q', scale=alt.Scale(domain=[0, 1160]), axis=None),
        y=alt.Y('y:O', sort=[0, 1, 2], axis=None), text='text:N',
        color=alt.Color('color:N', scale=None, legend=None)
    ).properties(width=1160, height=180, title=alt.Title(
        'Order to first-usage approval · duration percentiles', subtitle=subtitle +
        ['Hours; quantiles use unbinned durations with linear interpolation.'], anchor='start',
        fontSize=26, subtitleFontSize=17))
    table.configure(background='transparent').configure_view(stroke=None).save(
        directory / 'statistics.png', scale_factor=2)


def write_outputs(frame, metadata, charts, tables, table_prefix='', data_dir=None):
    details, audit, stats, bins = summarize(frame, metadata['start_date'], metadata['end_date_exclusive'],
                                           metadata['upload_start_date'])
    tables.mkdir(parents=True, exist_ok=True)
    end = (date.fromisoformat(metadata['end_date_exclusive']) - timedelta(days=1)).isoformat()
    subtitle = [f"CMPU vet diet · CUSTOMER_UPLOAD · Rx created {metadata['start_date']}–{end} (UTC)",
                f"Uploads: {metadata['upload_start_date']}–{end} · First order with known status other than X"]
    note = 'Only current ACCEPTED upload entities qualify; state-change timestamps are retained separately from creation-based discovery.\n\n' + '\n\n'.join(subtitle) + (
        '\n\nDuration = FIRST_USAGE_APPROVED_DATETIME − ORDER_PLACED_DTTM, hours. '
        'One observation per prescription; both timestamps required. Negative durations and all outliers retained. '
        'Bins are [lower, upper), aligned to integer hours. Order status is the current snapshot. '
        'No prescription-status/deletion filter or approval-date limit. Uploads match expanded RX_ID and numeric '
        'CUSTOMER_ID from DIET_PRESCRIPTION upload entities; this does not verify file presence or require upload '
        'before approval. These comparisons do not establish causality. Missing approval is not zero duration. '
        f"Extracted at {metadata['extracted_at_utc']}.\n\n")
    for name, data in [('eligibility', audit), ('statistics', stats), ('hourly-bins', bins), ('prescriptions', details)]:
        display = data.copy()
        if name == 'statistics':
            for col in display.columns[2:]:
                display[col] = display[col].map(lambda x: '—' if pd.isna(x) else f'{x:.2f}')
        write_text(tables / (table_prefix + f'{name}.md'), f'# {name.title()}\n\n' + note + markdown_table(display) + '\n')
    source_audit = {col: int(frame[col].iloc[0]) if len(frame) else None for col in AUDIT_COLUMNS}
    source_audit.update({key:int(frame[key].iloc[0]) if len(frame) and pd.notna(frame[key].iloc[0]) else 0
                         for key in ['accepted_window_upload_rows','excluded_window_upload_rows'] if key in frame})
    write_text(tables / (table_prefix + 'source-audit.md'), '# Upload source audit\n\n' + note + markdown_table(
        pd.DataFrame(source_audit.items(), columns=['measure', 'count'])) + '\n')
    if stats.N.sum():
        figures(stats, bins, charts, subtitle)
    else:
        charts.mkdir(parents=True, exist_ok=True)
        for name in ['distributions.png', 'statistics.png']:
            (charts / name).unlink(missing_ok=True)
    write_text(charts / 'README.md', '# Order to first-usage approval\n\n' + note + (
        '![Distributions](distributions.png)\n\n![Percentiles](statistics.png)\n' if stats.N.sum()
        else 'No eligible prescriptions; no figures generated.\n'))
    if data_dir is not None:
        data_dir.mkdir(parents=True,exist_ok=True)
        for name,data in [('associations',details),('audit',audit),('statistics',stats),('bins',bins)]:
            data.to_parquet(data_dir/f'{name}.parquet',index=False)
    return audit, stats


@click.command()
@click.option('--start-date', default='2026-08-15', show_default=True)
@click.option('--end-date', default='2026-10-15', show_default=True)
@click.option('--upload-start-date', default='2026-08-01', show_default=True)
@click.option('--cached', is_flag=True)
@click.option('--print-sql', is_flag=True)
def main(start_date, end_date, upload_start_date, cached, print_sql):
    try:
        sql = render_sql(start_date, end_date, upload_start_date)
        if print_sql:
            click.echo(sql)
            return
        period = period_name(start_date, end_date, upload_start_date) + '_' + TIMING_VARIANT
        directory = ROOT / 'data' / NAME / period
        parquet, manifest = directory / 'source.parquet', directory / 'source.json'
        if cached:
            metadata = json.loads(manifest.read_text())
            if (metadata.get('sql') != sql or metadata.get('parquet_sha256') != digest(parquet)
                    or [metadata.get(k) for k in ['start_date', 'end_date_exclusive', 'upload_start_date']]
                    != [start_date, end_date, upload_start_date]):
                raise ValueError('cached SQL, dates or fingerprint differs; refresh extract')
            frame = pd.read_parquet(parquet).rename(columns=str.lower)
        else:
            directory.mkdir(parents=True, exist_ok=True)
            generated = ROOT / 'src/autogenerated' / NAME / period
            generated.mkdir(parents=True, exist_ok=True)
            query = generated / 'source.sql'
            write_text(query, sql + '\n')
            manifest.unlink(missing_ok=True)
            subprocess.run([sys.executable, str(RUNNER), str(query), '--output-parquet', str(parquet.relative_to(ROOT)),
                            '--sql-log-dir', str((generated / 'sql-history').relative_to(ROOT))], cwd=ROOT, check=True)
            frame = pd.read_parquet(parquet).rename(columns=str.lower)
            summarize(frame, start_date, end_date, upload_start_date)
            metadata = dict(sql=sql, sql_sha256=hashlib.sha256(sql.encode()).hexdigest(),
                            parquet_sha256=digest(parquet), start_date=start_date, end_date_exclusive=end_date,
                            upload_start_date=upload_start_date, extracted_at_utc=datetime.now(timezone.utc).isoformat(),
                            source_extracted_at=frame.extracted_at_session_time.unique().tolist(),
                            warehouse=frame.extraction_warehouse.unique().tolist())
            write_text(manifest, json.dumps(metadata, indent=2) + '\n')
        table_dir, table_prefix = table_layout(ROOT, NAME, period)
        audit, stats = write_outputs(frame, metadata, ROOT / 'outputs/charts' / NAME / period,
                                     table_dir, table_prefix=table_prefix, data_dir=directory)
        click.echo(audit.to_string(index=False) + '\n\n' + stats.to_string(index=False))
    except (ValueError, OSError, KeyError, subprocess.CalledProcessError) as error:
        raise click.ClickException(str(error)) from error


if __name__ == '__main__':
    main()

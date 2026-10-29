"""REFNUM 18: elapsed upload time as a share of elapsed approval time."""
from collections import Counter
from datetime import date, datetime, timedelta, timezone
import json
import subprocess

import altair as alt
import click
import numpy as np
import pandas as pd

from src.python import create_cmpu_first_order_line_approval_distribution as timing
from src.python.markdown_tables import markdown_table
from src.python.markdown_tables import write_text

ROOT = timing.ROOT
NAME = 'cmpu-upload-time-ratio-distribution'
EXCLUSIONS = ['Zero approval duration', 'Negative approval duration', 'Negative upload duration']


def summarize(frame, start, end, upload_start):
    """Reuse source validation and line grain; classify ratios before aggregation."""
    original = frame.rename(columns=str.lower)
    selected = timing.upload_subset(original, start, end, upload_start)
    associations, lines, source_audit, _, _ = timing.summarize(selected, start, end)
    for details in [associations, lines]:
        details['upload_state_changed_at_utc'] = pd.to_datetime(details.upload_state_changed_at_utc, utc=True, errors='raise')
        upload_duration = details.upload_state_changed_at_utc - details.order_placed_utc
        approval_duration = details.max_approved_datetime - details.order_placed_utc
        details['upload_duration_hours'] = upload_duration.dt.total_seconds() / 3600
        details['approval_duration_hours'] = approval_duration.dt.total_seconds() / 3600
        details['ratio'] = upload_duration / approval_duration.where(approval_duration.ne(pd.Timedelta(0)))
        eligible = details.eligibility.eq('Eligible')
        details.loc[eligible & approval_duration.eq(pd.Timedelta(0)), 'eligibility'] = EXCLUSIONS[0]
        details.loc[eligible & approval_duration.lt(pd.Timedelta(0)), 'eligibility'] = EXCLUSIONS[1]
        details.loc[details.eligibility.eq('Eligible') & upload_duration.lt(pd.Timedelta(0)),
                    'eligibility'] = EXCLUSIONS[2]
        # These explicit names keep the two intervals distinct in exported details.
        details.drop(columns='elapsed_hours', inplace=True)

    eligible = lines.loc[lines.eligibility.eq('Eligible')]
    values = eligible.ratio
    if not np.isfinite(values).all() or values.lt(0).any():
        raise ValueError('invalid eligible ratios')
    states = timing.STATES[:-1] + EXCLUSIONS + ['Eligible']
    # Keep source/line-grain evidence, replacing duration-specific audit counts.
    audit = source_audit.loc[~source_audit.measure.isin(timing.STATES)
                             & source_audit.grain.ne('eligible lines')].copy()
    rows = [('prescription associations before upload filter', 'Cohort', len(original)),
            ('prescription associations before upload filter', 'No matching upload', len(original)-len(selected))]
    rows += [('upload source', col, int(original[col].iloc[0]) if len(original) else None)
             for col in timing.AUDIT_COLUMNS]
    rows += [('upload source',key,int(original[key].iloc[0]) if len(original) and pd.notna(original[key].iloc[0]) else 0)
             for key in ['accepted_window_upload_rows','excluded_window_upload_rows'] if key in original]
    rows += [(grain, state, int(details.eligibility.eq(state).sum()))
             for grain, details in [('prescription associations', associations), ('distinct matched lines', lines)]
             for state in states]
    rows += [('eligible lines', 'Ratio above 1', int(values.gt(1).sum())),
             ('eligible lines', 'Zero ratio', int(values.eq(0).sum()))]
    audit = pd.concat([pd.DataFrame(rows, columns=audit.columns), audit], ignore_index=True)

    stats = pd.DataFrame([dict(N=len(values), mean=values.mean(), minimum=values.min(),
        **{label: values.quantile(q, interpolation='linear') for label, q in
           [('p25', .25), ('median', .5), ('p75', .75), ('p95', .95)]}, maximum=values.max())])
    # Python integer nanoseconds avoid floating-point boundary errors and int64
    # overflow when scaling long durations by 100. Ratio 1 belongs to [1, 1.01).
    indexes = [((row.upload_state_changed_at_utc - row.order_placed_utc).value * 100)
               // (row.max_approved_datetime - row.order_placed_utc).value
               for row in eligible.itertuples()]
    counts = Counter(indexes)
    bins = pd.DataFrame([(index, index / 100, (index+1) / 100, count)
                         for index, count in sorted(counts.items())],
                        columns=['bin_index', 'lower_ratio', 'upper_ratio', 'order_lines'])
    ratios, frequencies = np.unique(values, return_counts=True)
    cdf = pd.DataFrame(dict(ratio=ratios, order_lines=frequencies,
        cumulative_lines=frequencies.cumsum(),
        cumulative_fraction=frequencies.cumsum() / len(values) if len(values) else []))
    if (bins.order_lines.sum() != len(eligible)
            or len(associations) != sum(associations.eligibility.eq(s).sum() for s in states)
            or len(lines) != sum(lines.eligibility.eq(s).sum() for s in states)
            or (len(cdf) and (cdf.cumulative_lines.iloc[-1] != len(eligible)
                              or cdf.cumulative_fraction.iloc[-1] != 1))):
        raise ValueError('ratio counts do not reconcile')
    return associations, lines, audit, stats, bins, cdf


def figures(bins, cdf, n, charts, stem, subtitle):
    domain = [float(bins.lower_ratio.min()), float(bins.upper_ratio.max())]
    x_title = 'Accepted-state elapsed time / approval elapsed time'
    histogram = alt.Chart(bins).mark_bar(color='#F28E2C', orient='vertical').encode(
        x=alt.X('lower_ratio:Q', title=x_title, axis=alt.Axis(format='.0%', tickCount=10),
                scale=alt.Scale(domain=domain, nice=False)),
        x2='upper_ratio:Q', y=alt.Y('order_lines:Q', title='D-status order lines',
                                  axis=alt.Axis(format=',d', tickMinStep=1)), y2=alt.datum(0),
        tooltip=[alt.Tooltip('lower_ratio:Q', format='.0%'), alt.Tooltip('upper_ratio:Q', format='.0%'),
                 alt.Tooltip('order_lines:Q', format=',d')])
    anchor = pd.DataFrame([dict(ratio=domain[0], order_lines=0, cumulative_lines=0, cumulative_fraction=0.)])
    points = pd.concat([anchor, cdf], ignore_index=True).assign(sequence=lambda f: np.arange(len(f)))
    cumulative = alt.Chart(alt.Data(values=points.to_dict(orient='records'))).mark_line(
        color='#F28E2C', interpolate='step-after', strokeWidth=2).encode(
        x=alt.X('ratio:Q', title=x_title, axis=alt.Axis(format='.0%', tickCount=10),
                scale=alt.Scale(domain=domain, nice=False)),
        y=alt.Y('cumulative_fraction:Q', title='Cumulative share of D-status order lines',
                scale=alt.Scale(domain=[0, 1], nice=False), axis=alt.Axis(format='.0%')),
        order='sequence:Q', tooltip=[alt.Tooltip('ratio:Q', format='.4%'),
            alt.Tooltip('cumulative_lines:Q', format=',d'), alt.Tooltip('cumulative_fraction:Q', format='.2%')])
    for chart, suffix, title, method in [
        (histogram, 'histogram', 'Upload time as a share of approval time', '1-percentage-point bins [lower, upper)'),
        (cumulative, 'cumulative', 'Cumulative distribution · upload time as a share of approval time',
         'Exact empirical CDF · Unbinned observations')]:
        chart.properties(width=1150, height=460, title=alt.Title(title, subtitle=subtitle +
            [f'Distinct D-status first-order lines · N = {n:,} · {method}'],
            anchor='start', fontSize=26, subtitleFontSize=16, offset=16)).configure(
                background='transparent', font='Arial', axis=alt.AxisConfig(labelFontSize=16, titleFontSize=19, titlePadding=14)).configure_view(stroke=None).save(charts / f'{stem}_{suffix}.png', scale_factor=2)


def fit_times(lines, log=False):
    """Unweighted OLS with an intercept, using only ratio-eligible unique lines."""
    selected = lines.loc[lines.eligibility.eq('Eligible')]
    original_n = len(selected)
    if log:
        selected = selected.loc[selected.approval_duration_hours.gt(0) & selected.upload_duration_hours.gt(0)]
    x = selected.approval_duration_hours.to_numpy(float)
    y = selected.upload_duration_hours.to_numpy(float)
    if log:
        x, y = np.log(x), np.log(y)
    result = dict(N=len(x), slope=np.nan, intercept_hours=np.nan, r_squared=np.nan,
                  fit_status='Insufficient data')
    if len(x) >= 2:
        centered_x, centered_y = x-x.mean(), y-y.mean()
        x_variation = np.dot(centered_x, centered_x)
        result['fit_status'] = 'Constant approval duration'
        if x_variation > 0:
            slope = np.dot(centered_x, centered_y) / x_variation
            intercept = y.mean()-slope*x.mean()
            residuals = y-(intercept+slope*x)
            y_variation = np.dot(centered_y, centered_y)
            result.update(slope=slope, intercept_hours=intercept,
                          r_squared=1-np.dot(residuals, residuals)/y_variation if y_variation > 0 else np.nan,
                          fit_status='Fitted' if y_variation > 0 else 'Fitted; R² undefined for constant upload duration')
    if log:
        intercept = result.pop('intercept_hours')
        result.update(intercept_log_hours=intercept, r_squared_log=result.pop('r_squared'),
                      power_multiplier=np.exp(intercept), excluded_nonpositive_times=original_n-len(selected),
                      log_base='e')
    return pd.DataFrame([result])


def time_figure(lines, fit, path, subtitle, log=False):
    selected = lines.loc[lines.eligibility.eq('Eligible'),
                         ['order_id', 'order_line_id', 'approval_duration_hours', 'upload_duration_hours']].copy()
    # Snowflake NUMBER identifiers may be Decimals, which the PNG renderer cannot
    # serialize as inline data. They are categorical tooltip labels here.
    for column in ['order_id', 'order_line_id']:
        selected[column] = selected[column].astype(str)
    if log:
        selected = selected.loc[selected.approval_duration_hours.gt(0) & selected.upload_duration_hours.gt(0)]
    x_scale = alt.Scale(type='log', zero=False, nice=False, padding=5) if log else alt.Scale(zero=True)
    y_scale = (alt.Scale(type='log', zero=False, nice=False, padding=5) if log
               else alt.Scale(zero=True, nice=False, padding=5))
    unit = 'hours, log scale' if log else 'hours'
    points = alt.Chart(alt.Data(values=selected.to_dict(orient='records'))).mark_circle(
        color='#F28E2C', opacity=0.18, size=12).encode(
        x=alt.X('approval_duration_hours:Q', title=f'Order placement to latest approval ({unit})',
                scale=x_scale, axis=alt.Axis(tickCount=5 if log else 10)),
        y=alt.Y('upload_duration_hours:Q', title=f'Order placement to accepted entity state change ({unit})',
                scale=y_scale, axis=alt.Axis(tickCount=5 if log else 10)),
        tooltip=['order_id:N', 'order_line_id:N', alt.Tooltip('approval_duration_hours:Q', format='.3f'),
                 alt.Tooltip('upload_duration_hours:Q', format='.3f')])
    row = fit.iloc[0]
    if pd.notna(row.slope):
        x = [float(selected.approval_duration_hours.min()), float(selected.approval_duration_hours.max())]
        y = ([np.exp(row.intercept_log_hours+row.slope*np.log(v)) for v in x] if log
             else [row.intercept_hours+row.slope*v for v in x])
        predicted = pd.DataFrame(dict(approval_duration_hours=x,
                                     upload_duration_hours=y))
        regression = alt.Chart(predicted).mark_line(color='#4E79A7', strokeWidth=3).encode(
            x='approval_duration_hours:Q', y='upload_duration_hours:Q')
        chart = points + regression
        r2 = row.r_squared_log if log else row.r_squared
        r_squared = f'{r2:.4f}' if pd.notna(r2) else 'undefined'
        fit_note = (f'OLS: ln(upload hours) = {row.slope:.4f} × ln(approval hours) {row.intercept_log_hours:+.4f} · R² (log) = {r_squared}'
                    if log else f'OLS: upload hours = {row.slope:.4f} × approval hours {row.intercept_hours:+.4f} · R² = {r_squared}')
    else:
        chart, fit_note = points, f'No fitted line: {row.fit_status}'
    legend_note = ('Orange: observed lines · Blue: least-squares fit with intercept'
                   if pd.notna(row.slope) else 'Orange: observed lines · Regression unavailable')
    population_note = (f'Positive elapsed times only · Zero/nonpositive pairs excluded: {int(row.excluded_nonpositive_times):,}'
                       if log else 'Nonnegative upload times')
    chart.properties(width=1150, height=600, title=alt.Title(
        'Upload and approval elapsed times · ' + ('log–log fit' if log else 'linear fit'), subtitle=subtitle[:2] +
        [f'Distinct D-status first-order lines · N = {len(selected):,} · {population_note} · Full observed range',
         fit_note, legend_note],
        anchor='start', fontSize=26, subtitleFontSize=16, offset=16)).configure(
            background='transparent', font='Arial',
            axis=alt.AxisConfig(labelFontSize=16, titleFontSize=19, titlePadding=14)
        ).configure_view(stroke=None).save(path, scale_factor=2)


def write_outputs(frame, metadata, charts, tables, data_dir=None):
    start, end, upload_start = (metadata[k] for k in ['start_date', 'end_date_exclusive', 'upload_start_date'])
    associations, lines, audit, stats, bins, cdf = summarize(frame, start, end, upload_start)
    last = (date.fromisoformat(end) - timedelta(days=1)).isoformat()
    upload_last = (date.fromisoformat(end) + timedelta(days=timing.UPLOAD_FOLLOWUP_DAYS-1)).isoformat()
    stem = f'cmpu-d-lines_upload-time-share_uploads-{upload_start}_{upload_last}_nonnegative_{timing.TIMING_VARIANT}'
    scatter = charts / (stem.replace('upload-time-share', 'upload-vs-approval-times') + '_linear-fit.png')
    log_scatter = scatter.with_name(scatter.name.replace('_linear-fit.png', '_log-log-fit.png'))
    subtitle = [f'CMPU vet diet · CUSTOMER_UPLOAD · Rx created {start}–{last} (UTC)',
                f'Selected accepted entity state change · Uploads {upload_start}–{upload_last} (UTC)',
                '(Accepted state change − order placement) / (latest approval − order placement) · Nonnegative numerator; positive denominator']
    note = ('Only current ACCEPTED entities qualify. Select earliest entity creation, with UPLOAD_ID ties; ' + '\n\n'.join(subtitle) + '\n\n'
        'One observation per distinct matched first-order/order-line pair with current status D. '
        'Shipment rows collapsed using latest populated approval; conflicting placement/status values rejected. '
        'UTC/Eastern companions validated where populated. Uploads match expanded RX_ID and numeric CUSTOMER_ID. '
        'All three timestamps required. Negative upload durations and zero/negative approval durations are excluded '
        'and retained explicitly in details/audits. Zero ratios, ratios above one and all outliers are retained. '
        'No approval-date filter. Ratios use unrounded durations; ratio statistics are dimensionless with linear quantiles. '
        'A ratio of 0.75 is 75%, meaning the accepted state change occurred three-quarters of the way from order placement to approval. '
        'Bins are [lower, upper), width 0.01; unlisted empty bins have zero count. '
        'CDF is the share of eligible lines with ratio ≤ each listed ratio. '
        f"Source extracted at {metadata['extracted_at_utc']}; source Parquet SHA-256 {metadata['parquet_sha256']}.\n\n")
    charts.mkdir(parents=True, exist_ok=True)
    tables.mkdir(parents=True, exist_ok=True)
    fit = fit_times(lines)
    log_fit = fit_times(lines, log=True)
    for name, data in [('associations', associations), ('order-lines', lines), ('eligibility', audit),
                       ('statistics', stats), ('ratio-bins', bins), ('cumulative-distribution', cdf)]:
        write_text(tables / f'{stem}_{name}.md', f'# {name.title()}\n\n' + note + markdown_table(data) + '\n')
    fit_note = ('Unweighted ordinary least squares with a fitted intercept: '
        'upload_duration_hours = intercept_hours + slope × approval_duration_hours. '
        'Both intervals start at order placement. The scatter and fit use the same eligible unique lines '
        'as the ratio charts, including all outliers. R² describes this sample; '
        'these related intervals share a start time and the association does not establish causation.\n\n')
    write_text(tables / (stem.replace('upload-time-share', 'upload-vs-approval-times') + '_linear-fit.md'), '# Elapsed-time linear fit\n\n' + note + fit_note + markdown_table(fit) + '\n')
    log_note = ('Unweighted OLS with an intercept on natural logs of both elapsed times, measured in hours: '
        'ln(upload_hours) = intercept_log_hours + slope × ln(approval_hours). '
        'The equivalent fitted curve is upload_hours = power_multiplier × approval_hours^slope, '
        'where power_multiplier = exp(intercept_log_hours). This back-transformed curve does not apply '
        'a mean-response bias correction. R² is calculated in log space. Only strictly positive '
        'elapsed-time pairs from the ratio-eligible population enter this fit; no pseudocount is added. '
        'All positive outliers are retained. The original ratio and linear-fit populations are unchanged.\n\n')
    write_text(tables / (stem.replace('upload-time-share', 'upload-vs-approval-times') + '_log-log-fit.md'), '# Elapsed-time log–log fit\n\n' + note + log_note + markdown_table(log_fit) + '\n')
    n = int(stats.N.iloc[0])
    if n:
        figures(bins, cdf, n, charts, stem, subtitle)
        time_figure(lines, fit, scatter, subtitle)
    else:
        for suffix in ['histogram', 'cumulative']:
            (charts / f'{stem}_{suffix}.png').unlink(missing_ok=True)
        scatter.unlink(missing_ok=True)
    if log_fit.N.iloc[0]:
        time_figure(lines, log_fit, log_scatter, subtitle, log=True)
    else:
        log_scatter.unlink(missing_ok=True)
    notes = charts / f'{stem}.md'
    write_text(notes, '# Upload time as a share of approval time\n\n' + note +
        (f'![Histogram]({stem}_histogram.png)\n\n![Cumulative distribution]({stem}_cumulative.png)\n\n'
         f'![Upload versus approval elapsed times]({scatter.name})\n\n' + fit_note + markdown_table(fit) + '\n'
         if n else 'No eligible lines; no figures generated.\n') + '\n\n' +
        (f'![Log–log time fit]({log_scatter.name})\n\n' if log_fit.N.iloc[0]
         else 'No strictly positive time pairs; no log–log figure generated.\n\n') +
        log_note + markdown_table(log_fit) + '\n')
    if data_dir is not None:
        data_dir.mkdir(parents=True,exist_ok=True)
        for name,data in [('associations',associations),('lines',lines),('audit',audit),('statistics',stats),('bins',bins),('cdf',cdf),('linear-fit',fit),('log-log-fit',log_fit)]:
            data.to_parquet(data_dir/f'{name}.parquet',index=False)
    return audit, stats, notes


@click.command()
@click.option('--start-date', default='2026-08-15', show_default=True)
@click.option('--end-date', default='2026-10-15', show_default=True, help='Exclusive prescription end; uploads extend 11 days.')
@click.option('--upload-start-date', default='2026-08-01', show_default=True)
@click.option('--cached', is_flag=True)
@click.option('--print-sql', is_flag=True)
def main(start_date, end_date, upload_start_date, cached, print_sql):
    try:
        if print_sql:
            click.echo(timing.render_sql(start_date, end_date, True, upload_start_date))
            return
        frame, source, period = timing.load_source(start_date, end_date, True, upload_start_date, cached)
        last = date.fromisoformat(end_date) - timedelta(days=1)
        audit, stats, notes = write_outputs(frame, source, ROOT/'outputs/charts'/f'{start_date}_{last}',
                                           ROOT/'outputs/tables'/f'{start_date}_{last}',
                                           data_dir=ROOT/'data'/NAME/period)
        directory = ROOT/'data'/NAME/period
        directory.mkdir(parents=True, exist_ok=True)
        write_text(directory/'analysis.json', json.dumps(dict(
            formula='(upload_state_changed_at_utc - order_placed_utc) / (max_approved_datetime - order_placed_utc)',
            time_fit='upload_duration_hours = intercept_hours + slope * approval_duration_hours; unweighted OLS',
            log_time_fit='ln(upload_duration_hours) = intercept_log_hours + slope * ln(approval_duration_hours); unweighted OLS',
            log_fit_requires_strictly_positive_times=True,
            bin_width_ratio=0.01, exclude_negative_upload_duration=True, require_positive_approval_duration=True,
            start_date=start_date, end_date_exclusive=end_date, upload_start_date=upload_start_date,
            upload_end_date_exclusive=source['upload_end_date_exclusive'],
            source_parquet=str((timing.ROOT/'data'/timing.NAME/period/'source.parquet').relative_to(ROOT)),
            source_parquet_sha256=source['parquet_sha256'], source_sql_sha256=source['sql_sha256'],
            source_extracted_at_utc=source['extracted_at_utc'],
            generated_at_utc=datetime.now(timezone.utc).isoformat(), eligible_lines=int(stats.N.iloc[0])), indent=2)+'\n')
        click.echo(audit.to_string(index=False) + '\n\n' + stats.to_string(index=False))
        click.echo(f'Chart notes: {notes}')
        click.echo(f'Tables: {ROOT / "outputs/tables" / f"{start_date}_{last}"}')
    except (ValueError, OSError, KeyError, subprocess.CalledProcessError) as error:
        raise click.ClickException(str(error)) from error


if __name__ == '__main__':
    main()

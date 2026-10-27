"""REFNUM 21: survival until upload or cancellation, using audited REFNUM 20 data."""
from datetime import date, timedelta
import json

import altair as alt
import click
import numpy as np
import pandas as pd
from scipy.stats import norm
from statsmodels.duration.survfunc import SurvfuncRight

from src.python import create_cmpu_first_order_line_event_times as events
from src.python.create_cmpu_prescription_first_order_status import ROOT, digest
from src.python.markdown_tables import markdown_table, table_layout
from src.python.markdown_tables import write_text

NAME = 'cmpu-first-order-line-survival'
DAY_NS = 86_400_000_000_000
CURVE_COLUMNS = ['duration_ns', 'elapsed_days', 'at_risk', 'events', 'censored',
                 'survival_probability', 'ci95_lower', 'ci95_upper']


def observations(lines, cutoff):
    """Retain all matched lines in details; exclude invalid origins/negative durations."""
    cutoff = pd.Timestamp(cutoff)
    if cutoff.tzinfo is None:
        raise ValueError('cutoff must include a timezone')
    cutoff = cutoff.tz_convert('UTC')
    frame = lines.copy()
    if (frame[['order_id', 'order_line_id']].isna().any().any()
            or frame.duplicated(['order_id', 'order_line_id']).any()):
        raise ValueError('require unique populated order/line keys')
    for col in ['line_created_utc', 'event_time']:
        frame[col] = pd.to_datetime(frame[col], utc=True, format='mixed').astype('datetime64[ns, UTC]')
    frame['survival_eligibility'] = 'Included'
    frame.loc[frame.event_time.lt(frame.line_created_utc), 'survival_eligibility'] = 'Negative event duration'
    frame.loc[frame.line_created_utc.gt(cutoff), 'survival_eligibility'] = 'Creation after cutoff'
    frame.loc[frame.line_created_utc.isna(), 'survival_eligibility'] = 'Missing creation'
    included = frame.survival_eligibility.eq('Included')
    observed = frame.event_time.notna() & frame.event_time.le(cutoff)
    frame['event_observed'] = pd.Series(pd.NA, index=frame.index, dtype='boolean')
    frame.loc[included, 'event_observed'] = observed[included]
    frame['observation_end_utc'] = frame.event_time.where(observed, cutoff).where(included)
    delta = frame.observation_end_utc - frame.line_created_utc
    frame['duration_ns'] = pd.Series(pd.NA, index=frame.index, dtype='Int64')
    frame.loc[included, 'duration_ns'] = delta[included].astype('int64')
    frame['elapsed_days'] = frame.duration_ns / DAY_NS
    frame['survival_outcome'] = 'Excluded'
    frame.loc[included & observed, 'survival_outcome'] = 'Event'
    frame.loc[included & ~observed & frame.event_time.isna(), 'survival_outcome'] = 'Censored: missing event'
    frame.loc[included & ~observed & frame.event_time.notna(), 'survival_outcome'] = 'Censored: event after cutoff'
    return frame


def kaplan_meier(frame):
    selected = frame.loc[frame.survival_eligibility.eq('Included')]
    if selected.empty:
        return pd.DataFrame(columns=CURVE_COLUMNS)
    grouped = selected.groupby('duration_ns').event_observed.agg(['size', 'sum'])
    curve = grouped.rename(columns={'sum': 'events'}).reset_index()
    curve['at_risk'] = len(selected) - curve['size'].cumsum().shift(fill_value=0)
    curve['censored'] = curve['size'] - curve.events
    curve['survival_probability'] = (1 - curve.events / curve.at_risk).cumprod().astype(float)
    # Greenwood variance and pointwise log-log 95% intervals, conditional on estimated event times.
    denom = curve.at_risk * (curve.at_risk - curve.events)
    greenwood = (curve.events / denom.where(denom.ne(0))).fillna(0).cumsum().astype(float)
    survival = curve.survival_probability.to_numpy()
    interior = (survival > 0) & (survival < 1)
    lower, upper = survival.copy(), survival.copy()
    z = norm.ppf(.975)
    loglog = np.log(-np.log(survival[interior]))
    se = np.sqrt(greenwood.to_numpy()[interior]) / np.abs(np.log(survival[interior]))
    lower[interior] = np.exp(-np.exp(loglog + z * se))
    upper[interior] = np.exp(-np.exp(loglog - z * se))
    curve['ci95_lower'], curve['ci95_upper'] = lower, upper
    curve['elapsed_days'] = curve.duration_ns / DAY_NS
    # Independently reconcile every event-time risk set and probability to statsmodels.
    fit = SurvfuncRight(selected.duration_ns.to_numpy(dtype=np.int64),
                       selected.event_observed.to_numpy(dtype=int))
    event_rows = curve.loc[curve.events.gt(0)]
    if (not np.array_equal(event_rows.duration_ns.to_numpy(dtype=np.int64), fit.surv_times)
            or not np.array_equal(event_rows.at_risk.to_numpy(dtype=int), fit.n_risk)
            or not np.array_equal(event_rows.events.to_numpy(dtype=int), fit.n_events)
            or not np.allclose(event_rows.survival_probability.to_numpy(dtype=float), fit.surv_prob,
                               rtol=1e-10, atol=1e-12)
            or int(curve.events.sum() + curve.censored.sum()) != len(selected)):
        raise ValueError('Kaplan-Meier risk sets or probabilities do not reconcile')
    return curve[CURVE_COLUMNS]


def risk_table(frame, curve):
    selected = frame.loc[frame.survival_eligibility.eq('Included')]
    rows = []
    for day in [0, 1, 3, 6, 10, 12, 20, 40, 60]:
        ns = day * DAY_NS
        if len(selected) == 0 or ns > int(selected.duration_ns.max()):
            continue
        previous = curve.loc[curve.duration_ns.le(ns)]
        rows.append(dict(elapsed_days=day, at_risk=int(selected.duration_ns.ge(ns).sum()),
                         cumulative_events=int((selected.event_observed & selected.duration_ns.le(ns)).sum()),
                         cumulative_censored=int((~selected.event_observed & selected.duration_ns.le(ns)).sum()),
                         survival_probability=float(previous.survival_probability.iloc[-1]) if len(previous) else 1.))
    return pd.DataFrame(rows, columns=['elapsed_days', 'at_risk', 'cumulative_events',
                                      'cumulative_censored', 'survival_probability'])


def figure(curve, n, path, subtitle):
    initial = dict(duration_ns=0, elapsed_days=0., at_risk=n, events=0, censored=0,
                   survival_probability=1., ci95_lower=1., ci95_upper=1.)
    display_end = min(13., max(1., float(curve.elapsed_days.max())))
    points = pd.concat([pd.DataFrame([initial]), curve.loc[curve.elapsed_days.le(display_end)]], ignore_index=True)
    if points.elapsed_days.iloc[-1] < display_end:
        points = pd.concat([points, points.iloc[[-1]].assign(
            elapsed_days=display_end, duration_ns=int(display_end * DAY_NS), events=0, censored=0)], ignore_index=True)
    points = points.assign(sequence=lambda f: np.arange(len(f)))
    # Limit PNG geometry to two exact steps per horizontal output pixel.
    # Full-resolution steps remain in the curve exports.
    maximum = display_end
    pixel = np.floor(points.elapsed_days.to_numpy(dtype=float) / maximum * 2300).astype(int)
    keep = np.r_[True, pixel[1:] != pixel[:-1]] | np.r_[pixel[:-1] != pixel[1:], True]
    points = points.loc[keep]
    data = alt.Data(values=points.to_dict(orient='records'))
    base = alt.Chart(data).encode(x=alt.X('elapsed_days:Q', title='Days from order-line creation',
        scale=alt.Scale(domain=[0, display_end], nice=False),
        axis=alt.Axis(tickCount=12)), order='sequence:Q')
    band = base.mark_area(color='#F28E2C', opacity=.18, interpolate='step-after').encode(
        y=alt.Y('ci95_lower:Q', title='Probability of awaiting upload or cancellation',
                scale=alt.Scale(domain=[0,1], nice=False), axis=alt.Axis(format='.0%')),
        y2='ci95_upper:Q')
    line = base.mark_line(color='#C96500', strokeWidth=2.5, interpolate='step-after').encode(
        y=alt.Y('survival_probability:Q', title='Probability of awaiting upload or cancellation',
                scale=alt.Scale(domain=[0,1], nice=False), axis=alt.Axis(format='.0%')),
        tooltip=[alt.Tooltip('elapsed_days:Q', format='.4f'), alt.Tooltip('survival_probability:Q', format='.3%'),
                 'at_risk:Q', 'events:Q', 'censored:Q'])
    reference = alt.Chart(alt.Data(values=[{'day': day, 'label': f'Day {day}'}
                                         for day in [3, 6, 10, 11]])).encode(x='day:Q')
    marker = reference.mark_rule(color='#555555', strokeDash=[6, 4], strokeWidth=1.5, clip=True)
    label = reference.mark_text(color='#555555', fontSize=16, align='left',
                                baseline='top', dx=6, clip=True).encode(y=alt.value(10), text='label:N')
    levels = []
    for day in [3, 6, 10]:
        previous = curve.loc[curve.duration_ns.le(day * DAY_NS)]
        probability = float(previous.survival_probability.iloc[-1]) if len(previous) else 1.
        if day <= display_end:
            levels.append({'probability': probability, 'label': f'Day {day}: {probability:.2%}'})
    horizontal = alt.Chart(alt.Data(values=levels)).encode(y=alt.Y('probability:Q',
        title='Probability of awaiting upload or cancellation', scale=alt.Scale(domain=[0, 1], nice=False)))
    guides = horizontal.mark_rule(color='#3979A0', strokeDash=[3, 4], strokeWidth=1.2)
    values = horizontal.mark_text(color='#3979A0', fontSize=16, align='right',
                                  baseline='bottom', dx=-6, dy=-6).encode(
        x=alt.datum(display_end), text='label:N')
    (band + line + marker + label + guides + values).properties(width=1150, height=520, title=alt.Title(
        'First-order-line survival until upload or cancellation', subtitle=subtitle,
        anchor='start', fontSize=25, subtitleFontSize=16, offset=16)).configure(
            background='transparent', font='Arial', axis=alt.AxisConfig(
                labelFontSize=16, titleFontSize=18, titlePadding=14)).configure_view(stroke=None).save(path, scale_factor=2)


def write_outputs(lines, associations, metadata, period):
    cutoff = pd.Timestamp(metadata['upload_end_date_exclusive'], tz='UTC')
    if cutoff > pd.Timestamp(metadata['extracted_at_utc']):
        raise ValueError('censoring cutoff is later than source extraction; refresh source')
    details = observations(lines, cutoff)
    curve = kaplan_meier(details)
    risks = risk_table(details, curve)
    selected = details.loc[details.survival_eligibility.eq('Included')]
    audit = [('Prescriptions', len(associations)), ('Unmatched prescription associations',
             int(associations.association_state.ne('Matched').sum())), ('Distinct matched lines', len(lines))]
    audit += [('Source negative durations (overlapping quality flag)',
               int(details.event_time.lt(details.line_created_utc).sum()))]
    audit += [(str(k), int(v)) for k,v in details.survival_eligibility.value_counts().items()]
    audit += [(str(k), int(v)) for k,v in details.survival_outcome.value_counts().items()]
    for source in ['actual_upload', 'estimated_upload', 'order_cancellation', 'tie', 'missing']:
        audit.append((f'Included event source: {source}', int((selected.event_observed & selected.event_time_source.eq(source)).sum())))
    audit = pd.DataFrame(audit, columns=['measure','count'])
    tables, prefix = table_layout(ROOT, NAME, period)
    last = (date.fromisoformat(metadata['end_date_exclusive']) - timedelta(days=1)).isoformat()
    charts = ROOT / 'outputs/charts' / f"{metadata['start_date']}_{last}"
    tables.mkdir(parents=True, exist_ok=True)
    charts.mkdir(parents=True, exist_ok=True)
    stem = prefix.rstrip('_')
    note = (f"Prescriptions UTC [{metadata['start_date']}, {metadata['end_date_exclusive']}); "
            f"uploads UTC [{metadata['upload_start_date']}, {metadata['upload_end_date_exclusive']}).\n\n"
            'One observation per audited REFNUM 20 distinct order/order-line pair; all statuses and flags. '
            'Event is the earlier of actual/estimated upload and cancellation, including ties. '
            'The 0.96 upload estimate is treated as an event time. S(t) is the probability that neither '
            'upload nor cancellation has occurred by elapsed day t; it is not an upload-completion probability. '
            f'Right censor missing or later events at {cutoff.isoformat()}; an event exactly at cutoff is observed. '
            'Exclude missing creation, creation after cutoff and negative event durations from the curve; '
            'preserve them in line details. Zero durations are included. '
            'Kaplan–Meier uses events before censoring for equal durations and no extrapolation beyond follow-up. '
            'The shaded band is a pointwise 95% log-log Greenwood confidence interval conditional on supplied '
            'event times; it does not capture uncertainty from the 0.96 estimation rule. '
            'Independent right censoring is assumed. The PNG shows days 0–13 with vertical markers '
            'at days 3, 6, 10 and 11 and labeled horizontal guides for S(3), S(6) and S(10); '
            'the curve table retains full follow-up. For PNG rendering only, retain the first and last '
            'exact step in each horizontal output-pixel bin; the exported curve retains every step.\n\n'
            f"Source extracted {metadata['extracted_at_utc']}; source SHA-256 {metadata['parquet_sha256']}. "
            'Estimator reference: https://www.statsmodels.org/stable/duration.html\n\n')
    for kind, data in [('line-details', details), ('survival-curve', curve), ('risk-table', risks), ('audit', audit)]:
        write_text(tables / f'{prefix}{kind}.md', f'# First-order-line survival: {kind}\n\n' + note + markdown_table(data) + '\n')
    path = charts / f'{stem}.png'
    if len(selected):
        subtitle = [f"CMPU vet diet · CUSTOMER_UPLOAD · Rx created {metadata['start_date']}–{last} UTC",
            f'N = {len(selected):,} · Events = {int(selected.event_observed.sum()):,} · Censored = {int((~selected.event_observed).sum()):,}',
            f'Actual/estimated upload or cancellation · Censor at {cutoff.strftime("%Y-%m-%d %H:%M")} UTC',
            'Shading: pointwise 95% CI · Estimated event times treated as fixed']
        figure(curve, len(selected), path, subtitle)
    else:
        path.unlink(missing_ok=True)
    write_text(charts / f'{stem}.md', '# First-order-line survival\n\n' + note +
        (f'![Survival curve]({path.name})\n\n' if len(selected) else 'No eligible lines; no chart generated.\n\n') + markdown_table(audit) + '\n')
    data_dir = ROOT / 'data' / NAME / period
    data_dir.mkdir(parents=True, exist_ok=True)
    for kind, data in [('observations', details), ('curve', curve), ('risk-table', risks), ('audit', audit)]:
        data.to_parquet(data_dir / f'{kind}.parquet', index=False)
    write_text(data_dir / 'manifest.json', json.dumps(dict(source_parquet_sha256=metadata['parquet_sha256'],
        source_sql_sha256=metadata['sql_sha256'], cutoff_utc=cutoff.isoformat(),
        endpoint='upload_or_cancellation', negative_durations='exclude',
        confidence_interval='pointwise 95% log-log Greenwood; conditional on fixed event times',
        files={p.name:digest(p) for p in data_dir.glob('*.parquet')}), indent=2) + '\n')
    return audit, path


@click.command()
@click.option('--start-date', default='2026-08-15', show_default=True)
@click.option('--end-date', default='2026-10-15', show_default=True)
@click.option('--upload-start-date', default='2026-08-01', show_default=True)
def main(start_date, end_date, upload_start_date):
    try:
        frame, metadata, period = events.load_source(start_date, end_date, upload_start_date, cached=True)
        associations, lines, _ = events.validate(frame, start_date, end_date, upload_start_date)
        audit, path = write_outputs(lines, associations, metadata, period)
        click.echo(audit.to_string(index=False))
        click.echo(f'Chart: {path}')
    except (ValueError, OSError, KeyError) as error:
        raise click.ClickException(str(error)) from error


if __name__ == '__main__':
    main()

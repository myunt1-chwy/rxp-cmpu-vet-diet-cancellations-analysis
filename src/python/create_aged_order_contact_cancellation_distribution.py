"""REFNUM 26: signed, one-day contact-leg distributions around aged cancellation."""
from datetime import date, timedelta
import json
import math

import altair as alt
import click
import pandas as pd

from src.python import create_aged_order_reorder_prescription_sankeys as sankeys
from src.python import create_aged_order_reorder_wismo as contacts_analysis
from src.python.create_cmpu_prescription_first_order_status import ROOT, digest
from src.python.markdown_tables import markdown_table, table_layout
from src.python.markdown_tables import write_text

NAME = 'aged-order-contact-cancellation-distribution'
DAY_NS = 86_400_000_000_000
HORIZONS = [7, 14, 21]


def load_inputs(start, end, as_of):
    baseline, bmeta, period = sankeys.windows.load_source(start, end, as_of, True, require_same_pet=True, include_21_days=True)
    windows = sankeys.windows.summarize(baseline, start, end, as_of, require_same_pet=True, include_21_days=True)
    chosen = sankeys.select_customers(windows)
    rx, rmeta, _ = sankeys.load_source(chosen, period, bmeta['parquet_sha256'], True)
    frozen, _ = sankeys.summarize(chosen, windows['associations'], rx)
    selected, intervals = contacts_analysis.requests_for(frozen)
    dependencies = dict(baseline=bmeta['parquet_sha256'], prescription_channels=rmeta['parquet_sha256'],
                        customer_selection=sankeys.SELECTION)
    raw, metadata, _ = contacts_analysis.load_source(intervals, period, dependencies, 'UTC', True,
                                                     all_contacts=True, all_order_history=True)
    validated = contacts_analysis.summarize(selected, intervals, raw, 'UTC', all_contacts=True, all_order_history=True)
    metadata = dict(metadata, start_date=start, end_date_exclusive=end, as_of_date=as_of)
    return contacts_analysis.contact_columns(validated['selected-customers'], True), validated['contact-interval-associations'], metadata, period


def summarize(selected, contacts):
    if (selected.original_customer_id.isna().any() or selected.request_id.isna().any()
            or selected.duplicated(['followup_days', 'original_customer_id']).any()
            or not selected.followup_days.isin(HORIZONS).all()):
        raise ValueError('invalid selected customer/horizon population')
    selected = selected.copy()
    selected['order_cancel_time'] = pd.to_datetime(selected.order_cancel_time, utc=True, format='mixed').astype('datetime64[ns, UTC]')
    if selected.order_cancel_time.isna().any():
        raise ValueError('missing selected cancellation timestamp')
    if set(contacts.request_id) != set(selected.loc[selected.contact_count.gt(0), 'request_id']):
        raise ValueError('contact interval keys differ from selected source counts')
    if contacts.handled_flag.isna().any() or not contacts.handled_flag.eq(True).all():
        raise ValueError('unhandled contact in all-handled source')
    contacts = contacts.copy()
    contacts['source_contact_row'] = range(1, len(contacts) + 1)
    contacts['contact_at_utc'] = pd.to_datetime(contacts.contact_at_utc, utc=True, format='mixed').astype('datetime64[ns, UTC]')
    columns = ['followup_days', 'original_customer_id', 'original_order_id', 'original_line_id',
               'reorder_order_id', 'reorder_line_id', 'order_cancel_time', 'request_id']
    events = selected[columns].merge(contacts, on='request_id', how='inner', validate='many_to_many')
    if events.order_id.ne(events.original_order_id).any():
        raise ValueError('contact must reference the original aged order')
    observed = events.groupby(['followup_days', 'original_customer_id']).size()
    expected = selected.set_index(['followup_days', 'original_customer_id']).contact_count
    if not observed.reindex(expected.index, fill_value=0).eq(expected).all():
        raise ValueError('contact legs do not reconcile to frozen selected-customer totals')
    events['elapsed_ns'] = (events.contact_at_utc - events.order_cancel_time).astype('int64').astype('Int64')
    events.loc[events.contact_at_utc.isna(), 'elapsed_ns'] = pd.NA
    events['elapsed_days'] = events.elapsed_ns / DAY_NS
    # Integer floor division is exact for negative lags and nanosecond boundaries.
    events['relative_day'] = events.elapsed_ns // DAY_NS
    events['missing_contact_time'] = events.contact_at_utc.isna()
    dated = events.loc[~events.missing_contact_time]
    lower = min(0, int(dated.relative_day.min())) if len(dated) else 0
    upper = max(0, int(dated.relative_day.max())) if len(dated) else 0
    bins, summary = [], []
    for days in HORIZONS:
        population = selected.loc[selected.followup_days.eq(days)]
        subset = events.loc[events.followup_days.eq(days)]
        valid = subset.loc[~subset.missing_contact_time]
        groups = {int(day): group for day, group in valid.groupby('relative_day')}
        for day in range(lower, upper + 1):
            group = groups.get(day, valid.iloc[:0])
            count = len(group)
            bins.append(dict(followup_days=days, relative_day=day, lower_day=day, upper_day=day+1,
                lower_hours=day*24, upper_hours=(day+1)*24,
                contact_legs=count, share_of_dated_contacts=count/len(valid) if len(valid) else 0.,
                customers=group.original_customer_id.nunique(), distinct_sessions=group.session_id.nunique(),
                timing='Before cancellation' if day < 0 else 'At/after cancellation'))
        before = int(valid.elapsed_ns.lt(0).sum()); exact = int(valid.elapsed_ns.eq(0).sum()); after = int(valid.elapsed_ns.gt(0).sum())
        if before + exact + after + int(subset.missing_contact_time.sum()) != len(subset):
            raise ValueError('before/exact/after/undated totals do not reconcile')
        summary.append(dict(followup_days=days, reordered_customers=len(population),
            customers_with_contacts=int(population.contact_count.gt(0).sum()),
            customers_without_contacts=int(population.contact_count.eq(0).sum()),
            contact_legs=len(subset), dated_contact_legs=len(valid), undated_contact_legs=int(subset.missing_contact_time.sum()),
            contacts_before_cancellation=before, contacts_at_cancellation=exact, contacts_after_cancellation=after,
            percent_before=100*before/len(valid) if len(valid) else None,
            percent_after=100*after/len(valid) if len(valid) else None,
            min_elapsed_days=valid.elapsed_days.min(), median_elapsed_days=valid.elapsed_days.median(),
            max_elapsed_days=valid.elapsed_days.max()))
    bins, summary = pd.DataFrame(bins), pd.DataFrame(summary)
    for row in summary.itertuples():
        if bins.loc[bins.followup_days.eq(row.followup_days), 'contact_legs'].sum() != row.dated_contact_legs:
            raise ValueError('daily bins do not reconcile to dated contacts')
    return {'daily-bins': bins, 'summary': summary, 'contact-details': events}


def figure(bins, summary, metadata, path, background='transparent'):
    days = int(summary.followup_days)
    lower, upper = int(bins.lower_day.min()), int(bins.upper_day.max())
    ticks = sorted({lower, upper, 0, *range(math.ceil(lower/5)*5, upper+1, 5)})
    # Avoid colliding endpoint and nearby 5-day tick labels.
    ticks = [n for n in ticks if n in [lower, upper, 0] or (n-lower >= 2 and upper-n >= 2)]
    scope = bins.loc[bins.followup_days.eq(days)]
    y_max = max(.1, math.ceil(float(bins.share_of_dated_contacts.max())*1.15*20)/20)
    x = alt.X('lower_day:Q', title='Days from aged-order cancellation · negative = before, positive = after',
              scale=alt.Scale(domain=[lower, upper], nice=False), axis=alt.Axis(values=ticks, labelAngle=0))
    bars = alt.Chart(scope).mark_bar(orient='vertical').encode(
        x=x, x2='upper_day:Q',
        y=alt.Y('share_of_dated_contacts:Q', title='Share of dated contact legs',
                scale=alt.Scale(domain=[0, y_max], nice=False), axis=alt.Axis(format='.0%')),
        y2=alt.Y2(datum=0),
        color=alt.Color('timing:N', title=None, scale=alt.Scale(
            domain=['Before cancellation', 'At/after cancellation'], range=['#4E79A7', '#F28E2C']),
            legend=alt.Legend(orient='top', labelFontSize=14)),
        tooltip=[alt.Tooltip('lower_day:Q', title='Bin start day (inclusive)'),
                 alt.Tooltip('upper_day:Q', title='Bin end day (exclusive)'),
                 alt.Tooltip('contact_legs:Q', format=',d'),
                 alt.Tooltip('share_of_dated_contacts:Q', format='.2%'),
                 alt.Tooltip('customers:Q', format=',d'), alt.Tooltip('distinct_sessions:Q', format=',d')])
    zero = alt.Chart(pd.DataFrame({'day': [0]})).mark_rule(color='#333333', strokeDash=[6,4], strokeWidth=2).encode(x='day:Q')
    annotation = alt.Chart(pd.DataFrame({'day': [0], 'share': [y_max*.97], 'label': ['Cancellation (day 0)']})).mark_text(
        align='left', dx=7, baseline='top', fontSize=14, color='#333333').encode(x='day:Q', y='share:Q', text='label:N')
    top = scope.loc[scope.contact_legs.gt(0)].sort_values(['contact_legs','relative_day'],ascending=[False,True]).head(3).copy()
    top['center'] = top.lower_day + .5
    labels = alt.Chart(top).mark_text(dy=-8, fontSize=14, fontWeight='bold', color='#333333').encode(
        x='center:Q', y='share_of_dated_contacts:Q', text=alt.Text('contact_legs:Q',format=',d'))
    last = date.fromisoformat(metadata['end_date_exclusive']) - timedelta(days=1)
    cutoff = pd.Timestamp(metadata['as_of_date'], tz='UTC') - pd.Timedelta(days=days)
    (bars+zero+annotation+labels).properties(width=1200,height=470,title=alt.Title(
        f'Contact timing around cancellation · {days}-day reorder group',
        subtitle=[f"CMPU vet diet · Original CUSTOMER_UPLOAD Rx {metadata['start_date']}–{last} · Same customer/product/pet reorders",
            f"{int(summary.reordered_customers):,} reordered customers · {int(summary.customers_with_contacts):,} with contacts · {int(summary.contact_legs):,} contact legs",
            f"Before cancellation: {int(summary.contacts_before_cancellation):,} · At cancellation: {int(summary.contacts_at_cancellation):,} · After: {int(summary.contacts_after_cancellation):,} · Undated: {int(summary.undated_contact_legs):,}",
            f"Cohort as-of {metadata['as_of_date']} 00:00 UTC · Order cancellations ≤ {cutoff:%Y-%m-%d %H:%M} UTC",
            'All available handled contacts on original aged order · All categories · UTC · Common axes across the three groups',
            '24-hour bins [day, day+1); day 0 starts at cancellation · Top-bin labels are contact counts'],
        anchor='start',fontSize=24,subtitleFontSize=14,offset=18)).configure(
            background=background,font='Arial',axis=alt.AxisConfig(labelFontSize=14,titleFontSize=16,titlePadding=12)
        ).configure_view(stroke=None).save(path,scale_factor=2)


def write_outputs(outputs, metadata, period):
    output_period = period + '_all-handled-contacts_all-order-history_UTC'
    tables, prefix = table_layout(ROOT, NAME, output_period)
    charts = ROOT / 'outputs/charts' / tables.name
    directory = ROOT / 'data' / NAME / output_period
    for path in [tables, charts, directory]: path.mkdir(parents=True,exist_ok=True)
    note = (f"Frozen 7/14/21-day REFNUM 24 shortest-delay selected same-customer/product/pet reorders; cohort as-of {metadata['as_of_date']} 00:00 UTC. "
        'Each customer supplies one selected original aged order/cancellation per horizon. Join contacts to ORIGINAL aged ORDER_ID via the validated lookup request. '
        'Use all available HANDLED_FLAG=TRUE contact legs, with no category or contact-time filter, including before cancellation, after reorder and after the cohort cutoff. '
        'Counts are contact legs (COUNT(*)), not unique customers or sessions. A customer can contribute multiple contacts and bins. '
        'The same contact may appear in multiple horizon populations; do not sum horizons as unique global contacts. '
        'Lag = UTC SESSION_START_DTTM minus selected order cancellation. Negative lags are before, zero is exact cancellation and positive lags are after. '
        'Daily bins use exact integer nanosecond floor division: [day,day+1), including the lower endpoint and excluding the upper. '
        'For example [-2,-1) days is 24–48 hours before; [4,5) is 96–120 hours after. Day 0 covers [0,24) hours after/at cancellation. '
        'Missing contact times remain in details/summary and are excluded only from the dated histogram denominator. '
        'All plotted bins, including zeros and tails, share an identical day range and percentage scale across horizons. '
        'Per-bin unique-customer/session counts can overlap across bins and should not be added to recover unique totals. '
        f"Source SHA-256 {metadata['parquet_sha256']}; source extracted {metadata['extracted_at_utc']}.\n\n")
    hashes = {}
    for kind, frame in outputs.items():
        table = tables / f'{prefix}{kind}.md'
        write_text(table, f'# Contacts relative to cancellation: {kind}\n\n' + note + markdown_table(frame) + '\n')
        parquet = directory / f'{kind}.parquet'; frame.to_parquet(parquet,index=False)
        hashes[str(table.relative_to(ROOT))] = digest(table)
        hashes[str(parquet.relative_to(ROOT))] = digest(parquet)
    for summary in outputs['summary'].itertuples(index=False):
        stem = prefix + f'{summary.followup_days}d-contact-timing'
        png = charts / f'{stem}.png'
        figure(outputs['daily-bins'],summary,metadata,png)
        write_text(png.with_suffix('.md'), '# Contact timing around cancellation\n\n' + note + f'![Contact timing]({png.name})\n')
        hashes[str(png.relative_to(ROOT))] = digest(png)
        hashes[str(png.with_suffix('.md').relative_to(ROOT))] = digest(png.with_suffix('.md'))
    write_text(directory/'manifest.json', json.dumps(dict(contact_source_sha256=metadata['parquet_sha256'],
        dependencies=metadata['dependencies'],contact_scope='all-handled',contact_time_scope='all-order-history',
        contact_timezone='UTC',bin_rule='floor(elapsed nanoseconds / 86400000000000); [day,day+1)',
        measure='contact legs; share among dated contact legs within horizon',followup_days=HORIZONS,files=hashes),indent=2)+'\n')
    return charts,tables


@click.command()
@click.option('--start-date',default='2026-08-15',show_default=True)
@click.option('--end-date',default='2026-10-15',show_default=True)
@click.option('--as-of-date',default='2026-10-27',show_default=True)
def main(start_date,end_date,as_of_date):
    try:
        selected,contacts,metadata,period = load_inputs(start_date,end_date,as_of_date)
        outputs = summarize(selected,contacts)
        charts,tables = write_outputs(outputs,metadata,period)
        click.echo(outputs['summary'].to_string(index=False))
        click.echo(f'Charts: {charts}\nTables: {tables}')
    except (ValueError,OSError,KeyError) as error:
        raise click.ClickException(str(error)) from error


if __name__=='__main__': main()

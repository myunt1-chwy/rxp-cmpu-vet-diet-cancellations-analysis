"""One count per reorder customer, at their shortest qualifying delay."""
from datetime import date, timedelta
import json

import altair as alt
import click
import pandas as pd

from src.python import create_aged_order_reorder_windows as windows
from src.python.create_cmpu_prescription_first_order_status import ROOT, digest
from src.python.markdown_tables import markdown_table, table_layout
from src.python.markdown_tables import write_text

NAME='aged-order-reorder-daily-customers'
DAY_NS=86_400_000_000_000


def daily_counts(matches,customers,followup_days=14):
    if followup_days not in [7,14,21]:raise ValueError('supported plot windows are 7, 14 and 21 days')
    frame=matches.loc[matches.followup_days.eq(followup_days)].copy()
    eligible=customers.loc[customers.followup_days.eq(followup_days)]
    if eligible.original_customer_id.isna().any() or eligible.original_customer_id.duplicated().any():
        raise ValueError(f'invalid {followup_days}-day customer population')
    expected=set(eligible.loc[eligible.has_reordered,'original_customer_id'])
    if frame.original_customer_id.isna().any() or not frame.eligibility.eq('Eligible').all():
        raise ValueError(f'invalid {followup_days}-day reorder matches')
    for col in ['order_cancel_time','reorder_placed_at_utc']:
        frame[col]=pd.to_datetime(frame[col],utc=True,format='mixed').astype('datetime64[ns, UTC]')
        if frame[col].isna().any():raise ValueError('missing cancellation or reorder time')
    frame['elapsed_ns']=(frame.reorder_placed_at_utc-frame.order_cancel_time).astype('int64')
    if frame.elapsed_ns.le(0).any() or frame.elapsed_ns.gt(followup_days*DAY_NS).any():
        raise ValueError(f'reorder outside {followup_days}-day window')
    selected=frame.sort_values(['original_customer_id','elapsed_ns','reorder_placed_at_utc',
        'reorder_order_id','reorder_line_id','original_order_id','original_line_id']).drop_duplicates('original_customer_id').copy()
    selected['day']=((selected.elapsed_ns-1)//DAY_NS+1).astype(int)
    if set(selected.original_customer_id)!=expected:
        raise ValueError(f'plotted customer IDs differ from {followup_days}-day reordered population')
    counts=selected.day.value_counts().reindex(range(1,followup_days+1),fill_value=0)
    bins=pd.DataFrame(dict(day=range(1,followup_days+1),lower_hours=[24*d for d in range(followup_days)],
        upper_hours=[24*d for d in range(1,followup_days+1)],customers=counts.to_numpy(dtype=int)))
    bins['percent_of_reordered_customers']=100*bins.customers/len(selected) if len(selected) else 0.
    if bins.customers.sum()!=len(selected):raise ValueError('daily customer counts do not reconcile')
    return selected,bins,len(eligible)


def figure(bins,eligible_count,reordered_count,path,metadata,followup_days=14):
    last=(date.fromisoformat(metadata['end_date_exclusive'])-timedelta(days=1)).isoformat()
    base=alt.Chart(bins).encode(
        x=alt.X('day:O',sort=list(range(1,followup_days+1)),title='Day after aged-order cancellation · Day 1 = first 24 hours',
                axis=alt.Axis(labelAngle=0),scale=alt.Scale(paddingInner=.06,paddingOuter=.05)),
        y=alt.Y('customers:Q',title='Number of customers',scale=alt.Scale(domain=[0,max(1,int(bins.customers.max())*1.14)],nice=False),
                axis=alt.Axis(format=',d',tickMinStep=1)),
        tooltip=['day:O','customers:Q',alt.Tooltip('percent_of_reordered_customers:Q',format='.2f')])
    bars=base.mark_bar(color='#F28E2C')
    labels=base.mark_text(dy=-8,fontSize=16,fontWeight='bold',color='#333333').encode(text=alt.Text('customers:Q',format=',d'))
    (bars+labels).properties(width=1150,height=500,title=alt.Title(
        ('Customer reorders for the same product and pet after aged cancellation' if metadata.get('match_pet')
         else f'Customers reordering the same product within {followup_days} days of aged cancellation'),
        subtitle=[f"CMPU vet diet · CUSTOMER_UPLOAD · Rx created {metadata['start_date']}–{last} UTC",
            f'Eligible customers: {eligible_count:,} · Customers who reordered: {reordered_count:,}',
            f"As-of {metadata['as_of_date']} 00:00 UTC · Complete {followup_days}-day follow-up",
            'Each customer counted once at their shortest qualifying reorder delay · 24-hour bins (lower, upper]'],
        anchor='start',fontSize=24,subtitleFontSize=16,offset=16)).configure(
            background='transparent',font='Arial',axis=alt.AxisConfig(labelFontSize=16,titleFontSize=18,titlePadding=14)
        ).configure_view(stroke=None).save(path,scale_factor=2)


def write_outputs(outputs,metadata,period,followup_days=14):
    selected,bins,eligible=daily_counts(outputs['reorder-matches'],outputs['customers'],followup_days)
    tables,prefix=table_layout(ROOT,windows.NAME,period)
    last=(date.fromisoformat(metadata['end_date_exclusive'])-timedelta(days=1)).isoformat()
    charts=ROOT/'outputs/charts'/f"{metadata['start_date']}_{last}"
    tables.mkdir(parents=True,exist_ok=True);charts.mkdir(parents=True,exist_ok=True)
    stem=prefix+f'{followup_days}d-customers-by-reorder-day'
    path=charts/f'{stem}.png'
    note=(f"Frozen REFNUM 23 source, as-of {metadata['as_of_date']} 00:00 UTC. "
        f'{eligible:,} customers with at least one complete {followup_days}-day aged cancellation; {len(selected):,} placed '
        f'a same-product reorder within {followup_days} days. One observation per customer, selecting the minimum exact elapsed '
        'nanoseconds across their eligible cancellation/reorder-line matches. Ties choose the earlier reorder timestamp, '
        'then reorder order/line and original order/line IDs. This measures the shortest observed qualifying delay per '
        'customer, not necessarily their chronologically first reorder. Day 1 covers (0,24] hours, day 2 (24,48], '
        f'through day {followup_days} ({24*(followup_days-1)},{24*followup_days}] hours. An event exactly on a day boundary belongs to that day. '
        f'All {followup_days} days are shown, including zero-count days. Customers without a qualifying reorder are outside the '
        'histogram; bins sum to the reordered-customer count. Counts are placed attempts regardless of later shipment/status.\n\n' +
        ('Matching also requires a known, unambiguous identical PET_ID on the original and reordered line.\n\n'
         if metadata.get('match_pet') else '') +
        f"Source SHA-256 {metadata['parquet_sha256']}; source extracted {metadata['extracted_at_utc']}.\n\n")
    for kind,data in [('daily-counts',bins),('selected-customers',selected)]:
        write_text(tables/f'{stem}_{kind}.md', f'# {followup_days}-day reorder customers: {kind}\n\n'+note+markdown_table(data)+'\n')
    if eligible:figure(bins,eligible,len(selected),path,metadata,followup_days=followup_days)
    else:path.unlink(missing_ok=True)
    write_text(path.with_suffix('.md'), '# Customers by reorder day\n\n'+note+
        (f'![Customers by reorder day]({path.name})\n' if eligible else 'No eligible customer population; no figure generated.\n'))
    directory=ROOT/'data'/NAME/period;directory.mkdir(parents=True,exist_ok=True)
    selected.to_parquet(directory/'selected-customers.parquet',index=False)
    bins.to_parquet(directory/'daily-counts.parquet',index=False)
    write_text(directory/'manifest.json', json.dumps(dict(source_sha256=metadata['parquet_sha256'],
        followup_days=followup_days,match_pet=metadata.get('match_pet',False),customer_selection='minimum elapsed nanoseconds',bins='(lower, upper] hours; 24-hour width',
        eligible_customers=eligible,reordered_customers=len(selected),
        files={p.name:digest(p) for p in directory.glob('*.parquet')},chart_sha256=digest(path) if path.exists() else None),indent=2)+'\n')
    return bins,path


@click.command()
@click.option('--start-date',default='2026-08-15',show_default=True)
@click.option('--end-date',default='2026-10-15',show_default=True)
@click.option('--as-of-date',default='2026-10-27',show_default=True)
@click.option('--followup-days',type=click.Choice(['14','21']),default='14',show_default=True)
@click.option('--same-pet',is_flag=True,help='Use the same-customer/product/pet windows cache.')
def main(start_date,end_date,as_of_date,same_pet,followup_days):
    try:
        followup_days=int(followup_days)
        raw,metadata,period=windows.load_source(start_date,end_date,as_of_date,True,require_same_pet=same_pet,include_21_days=followup_days==21)
        outputs=windows.summarize(raw,start_date,end_date,as_of_date,require_same_pet=same_pet,include_21_days=followup_days==21)
        bins,path=write_outputs(outputs,metadata,period,followup_days=followup_days)
        click.echo(bins.to_string(index=False));click.echo(f'Chart: {path}')
    except (ValueError,OSError,KeyError) as error:
        raise click.ClickException(str(error)) from error


if __name__=='__main__':main()

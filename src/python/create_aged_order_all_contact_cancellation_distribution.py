"""REFNUM 32: contact timing for every aged order in the CMPU upload cohort."""
from datetime import date, datetime, timedelta, timezone
import hashlib
import json
import subprocess
import sys

import altair as alt
import click
from jinja2 import Environment, StrictUndefined
import pandas as pd

from src.python.create_cmpu_prescription_first_order_status import ROOT, RUNNER, digest
from src.python.markdown_tables import markdown_table, table_layout, write_text

NAME = 'aged-order-all-contact-cancellation-distribution'
TEMPLATE = ROOT / 'src/sql/aged_order_all_contact_cancellation_distribution.sql'
DAY_NS = 86_400_000_000_000
ASSOCIATIONS = ['rx_id', 'rx_customer_id', 'first_order_id', 'first_orderitem_id',
    'first_order_line_id', 'rx_creation_datetime', 'rx_source_rows', 'order_id', 'order_line_id',
    'customer_id', 'customer_variants', 'order_cancel_reason', 'reason_variants',
    'order_cancel_time', 'cancel_variants', 'shipment_rows']
CONTACTS = ['order_id', 'leg_id', 'session_id', 'session_channel', 'contact_at_utc',
            'category_wismo_flag', 'handled_flag']
NOTE = ('CMPU vet-diet CUSTOMER_UPLOAD first-order cohort; every aged order, regardless of reordering. '
    'Distinct order/order-line keys collapse shipment rows; orders are counted once across prescriptions and lines. '
    'All available HANDLED_FLAG=TRUE contact rows on aged orders, all categories, with no contact-time restriction. '
    'Contacts and cancellations are UTC. The as-of cutoff applies to cancellations, not contact history. '
    'Lag = contact time minus cancellation; exact nanosecond floor bins [day,day+1). '
    'Undated contacts remain in details and totals but are excluded from histogram shares. '
    'Counts follow contact source rows (contact legs), not unique sessions. Daily customer/session/order counts '
    'can overlap across bins. Full data are in the corresponding data/ Parquet files. ')


def render_sql(start, end, as_of):
    start, end, as_of = map(date.fromisoformat, [start, end, as_of])
    if not start < end <= as_of <= datetime.now(timezone.utc).date():
        raise ValueError('require start < exclusive end <= as-of <= current UTC date')
    return Environment(undefined=StrictUndefined).from_string(TEMPLATE.read_text()).render(
        start_date=start.isoformat(), end_date=end.isoformat(), as_of_date=as_of.isoformat())


def unpack(raw):
    raw = raw.rename(columns=str.lower)
    if not raw.record_type.isin(['association', 'contact']).all():
        raise ValueError('unexpected source record type')
    def records(kind, columns):
        return pd.DataFrame([{k.lower(): v for k, v in json.loads(p).items()}
                             for p in raw.loc[raw.record_type.eq(kind), 'payload']], columns=columns)
    return records('association', ASSOCIATIONS), records('contact', CONTACTS)


def summarize(associations, contacts, start, end, as_of):
    render_sql(start, end, as_of)
    a, c = associations.copy(), contacts.copy()
    if a.rx_id.isna().any() or a.rx_id.duplicated().any() or not a.rx_source_rows.eq(1).all():
        raise ValueError('missing or duplicate prescription IDs')
    for col in ['rx_creation_datetime', 'order_cancel_time']:
        a[col] = pd.to_datetime(a[col], utc=True, format='mixed').astype('datetime64[ns, UTC]')
    if not a.rx_creation_datetime.between(pd.Timestamp(start,tz='UTC'), pd.Timestamp(end,tz='UTC'), inclusive='left').all():
        raise ValueError('prescription outside cohort window')
    parsed = a.first_orderitem_id.astype('string').str.strip().str.fullmatch('[0-9]+').fillna(False)
    for row, valid in zip(a.itertuples(), parsed):
        expected = int(str(row.first_orderitem_id).strip()) if valid else None
        if (expected is None) != pd.isna(row.first_order_line_id) or (expected is not None and expected != row.first_order_line_id):
            raise ValueError('invalid numeric line key')
    matched = a.order_id.notna()
    if matched.ne(a.order_line_id.notna()).any() or (matched & (
            a.order_id.ne(a.first_order_id) | a.order_line_id.ne(a.first_order_line_id))).any():
        raise ValueError('first-order association keys disagree')
    lines = a.loc[matched, ASSOCIATIONS[7:]].drop_duplicates()
    if lines.duplicated(['order_id','order_line_id']).any():
        raise ValueError('conflicting repeated line associations')
    if (not lines.customer_variants.eq(1).all() or not lines.reason_variants.eq(1).all()
            or lines.cancel_variants.gt(1).any()):
        raise ValueError('conflicting source customer, reason or cancellation')
    fields = ['customer_id', 'order_cancel_reason', 'order_cancel_time']
    if lines.groupby('order_id')[fields].nunique(dropna=False).gt(1).any().any():
        raise ValueError('conflicting order-level customer, reason or cancellation')
    orders = lines.drop_duplicates('order_id')[['order_id', *fields]].copy()
    orders = orders.loc[orders.order_cancel_reason.eq('aged order') & orders.order_cancel_time.notna()
        & orders.order_cancel_time.le(pd.Timestamp(as_of,tz='UTC'))].copy()
    if c.order_id.isna().any() or not c.order_id.isin(orders.order_id).all():
        raise ValueError('contact references an order outside the aged population')
    if not c.handled_flag.eq(True).all():
        raise ValueError('unhandled contact in source')
    c['contact_at_utc'] = pd.to_datetime(c.contact_at_utc, utc=True, format='mixed').astype('datetime64[ns, UTC]')
    c['source_contact_row'] = range(1, len(c)+1)
    c = c.merge(orders, on='order_id', how='left', validate='many_to_one')
    c['elapsed_ns'] = (c.contact_at_utc-c.order_cancel_time).astype('int64').astype('Int64')
    c.loc[c.contact_at_utc.isna(), 'elapsed_ns'] = pd.NA
    c['elapsed_days'] = c.elapsed_ns / DAY_NS
    c['relative_day'] = c.elapsed_ns // DAY_NS
    orders['contact_count'] = orders.order_id.map(c.groupby('order_id').size()).fillna(0).astype(int)
    a['association_state'] = 'Unmatched line'
    a.loc[a.first_order_id.isna(), 'association_state'] = 'Missing order ID'
    a.loc[a.first_order_id.notna() & a.first_orderitem_id.isna(), 'association_state'] = 'Missing line ID'
    a.loc[a.first_order_id.notna() & a.first_orderitem_id.notna() & ~parsed, 'association_state'] = 'Invalid line ID'
    a.loc[matched, 'association_state'] = 'Matched, outside aged population'
    a.loc[a.order_id.isin(orders.order_id), 'association_state'] = 'Aged order'
    dated = c.loc[c.contact_at_utc.notna()]
    lower = min(0, int(dated.relative_day.min())) if len(dated) else 0
    upper = max(0, int(dated.relative_day.max())) if len(dated) else 0
    bins = pd.DataFrame({'relative_day': range(lower,upper+1)})
    grouped = dated.groupby('relative_day').agg(contact_legs=('order_id','size'),
        orders=('order_id','nunique'), customers=('customer_id','nunique'), distinct_sessions=('session_id','nunique'))
    bins = bins.merge(grouped, on='relative_day', how='left').fillna(0)
    bins['share_of_dated_contacts'] = bins.contact_legs / len(dated) if len(dated) else 0.
    bins['upper_day'] = bins.relative_day + 1
    bins['timing'] = bins.relative_day.map(lambda d: 'Before cancellation' if d<0 else 'At/after cancellation')
    customer_contacts = orders.groupby('customer_id').contact_count.sum()
    summary = pd.DataFrame([dict(aged_orders=len(orders), customers=orders.customer_id.nunique(),
        orders_with_contacts=int(orders.contact_count.gt(0).sum()), orders_without_contacts=int(orders.contact_count.eq(0).sum()),
        customers_with_contacts=int(customer_contacts.gt(0).sum()), customers_without_contacts=int(customer_contacts.eq(0).sum()),
        orders_missing_customer=int(orders.customer_id.isna().sum()), contact_legs=len(c), dated_contact_legs=len(dated),
        undated_contact_legs=int(c.contact_at_utc.isna().sum()), contacts_before_cancellation=int(dated.elapsed_ns.lt(0).sum()),
        contacts_at_cancellation=int(dated.elapsed_ns.eq(0).sum()), contacts_after_cancellation=int(dated.elapsed_ns.gt(0).sum()),
        min_elapsed_days=dated.elapsed_days.min(), median_elapsed_days=dated.elapsed_days.median(), max_elapsed_days=dated.elapsed_days.max())])
    if bins.contact_legs.sum() != len(dated) or orders.contact_count.sum() != len(c):
        raise ValueError('contact counts do not reconcile')
    audit = a.association_state.value_counts().rename_axis('association_state').reset_index(name='prescriptions')
    return {'associations': a, 'orders': orders, 'contact-details': c, 'daily-bins': bins, 'summary': summary, 'audit': audit}


def figure(bins, summary, metadata, path):
    row = summary.iloc[0]
    bars = alt.Chart(bins).mark_bar(orient='vertical').encode(
        x=alt.X('relative_day:Q', title='Days from aged-order cancellation (negative = before)',
                scale=alt.Scale(domain=[int(bins.relative_day.min()),int(bins.upper_day.max())], nice=False)),
        x2='upper_day:Q',
        y=alt.Y('share_of_dated_contacts:Q', title='Share of dated contact legs', axis=alt.Axis(format='.0%')),
        y2=alt.Y2(datum=0),
        color=alt.Color('timing:N',title=None,scale=alt.Scale(
            domain=['Before cancellation','At/after cancellation'],range=['#4E79A7','#F28E2C'])),
        tooltip=['relative_day:Q','contact_legs:Q','orders:Q','customers:Q','distinct_sessions:Q'])
    zero = alt.Chart(pd.DataFrame({'day':[0]})).mark_rule(color='#333333',strokeDash=[6,4]).encode(x='day:Q')
    last = date.fromisoformat(metadata['end_date_exclusive'])-timedelta(days=1)
    (bars+zero).properties(width=1200,height=470,title=alt.Title(
        'Contact timing around cancellation · All aged orders',anchor='start',fontSize=23,subtitleFontSize=14,
        subtitle=[f"CMPU vet-diet CUSTOMER_UPLOAD Rx {metadata['start_date']}–{last} · No reorder requirement",
            f"{int(row.aged_orders):,} aged orders · {int(row.customers):,} customers · {int(row.orders_with_contacts):,} orders with contacts",
            f"{int(row.contact_legs):,} contact legs · {int(row.undated_contact_legs):,} undated · Cancellation cutoff {metadata['as_of_date']} 00:00 UTC",
            'All handled contacts on aged orders · All categories and available history · UTC · 24-hour bins [day, day+1) · Dashed line: cancellation']
    )).configure(background='transparent',font='Arial',axis=alt.AxisConfig(labelFontSize=13,titleFontSize=15),
        legend=alt.LegendConfig(orient='top')).configure_view(stroke=None).save(path,scale_factor=2)


def run(start, end, as_of, cached=False, print_sql=False):
    sql = render_sql(start,end,as_of)
    if print_sql:
        click.echo(sql)
        return
    period = f'{start}_{end}_as-of-{as_of}_all-handled-contacts_all-order-history_UTC'
    directory = ROOT/'data'/NAME/period
    parquet, manifest = directory/'source.parquet', directory/'source.json'
    expected = dict(sql_sha256=hashlib.sha256(sql.encode()).hexdigest(), start_date=start,
                    end_date_exclusive=end,as_of_date=as_of, contact_timezone='UTC')
    if cached:
        metadata = json.loads(manifest.read_text())
        if any(metadata.get(k)!=v for k,v in expected.items()) or metadata.get('parquet_sha256')!=digest(parquet):
            raise ValueError('cached dates, SQL or source fingerprint differs; refresh the extract')
    else:
        directory.mkdir(parents=True,exist_ok=True)
        generated = ROOT/'src/autogenerated'/NAME/period
        generated.mkdir(parents=True,exist_ok=True)
        query = generated/'aged_order_all_contact_cancellation_distribution.sql'
        write_text(query, sql+'\n')
        manifest.unlink(missing_ok=True)
        subprocess.run([sys.executable,str(RUNNER),str(query),'--output-parquet',str(parquet.relative_to(ROOT)),
                        '--sql-log-dir',str((generated/'sql-history').relative_to(ROOT))],cwd=ROOT,check=True)
        metadata = dict(expected,parquet_sha256=digest(parquet),extracted_at_utc=datetime.now(timezone.utc).isoformat())
    outputs = summarize(*unpack(pd.read_parquet(parquet)),start,end,as_of)
    # Publish provenance only after validation succeeds.
    write_text(manifest,json.dumps(metadata,indent=2)+'\n')
    tables,prefix = table_layout(ROOT,NAME,period)
    charts = ROOT/'outputs/charts'/tables.name
    tables.mkdir(parents=True,exist_ok=True); charts.mkdir(parents=True,exist_ok=True)
    files = {}
    note = NOTE+f"Source extracted {metadata['extracted_at_utc']}; SHA-256 {metadata['parquet_sha256']}.\n\n"
    for kind,frame in outputs.items():
        full = directory/f'{kind}.parquet'; frame.to_parquet(full,index=False)
        table = tables/f'{prefix}{kind}.md'
        write_text(table,f'# All aged-order contact timing: {kind}\n\n'+note+markdown_table(frame)+'\n')
        for path in [full,table]: files[str(path.relative_to(ROOT))]=digest(path)
    png = charts/f'{prefix}contact-timing.png'
    figure(outputs['daily-bins'],outputs['summary'],metadata,png)
    caption = png.with_suffix('.md')
    write_text(caption,'# All aged-order contact timing\n\n'+note+f'![Contact timing]({png.name})\n')
    for path in [png,caption]: files[str(path.relative_to(ROOT))]=digest(path)
    write_text(directory/'manifest.json',json.dumps(dict(source=metadata,files=files,
        bin_rule='floor(elapsed nanoseconds / 86400000000000); [day,day+1)',measure='contact legs'),indent=2)+'\n')
    click.echo(outputs['summary'].to_string(index=False))
    click.echo(f'Chart: {png}\nTables: {tables}')


@click.command()
@click.option('--start-date',default='2026-08-15',show_default=True)
@click.option('--end-date',default='2026-10-15',show_default=True)
@click.option('--as-of-date',default='2026-10-27',show_default=True)
@click.option('--cached',is_flag=True)
@click.option('--print-sql',is_flag=True)
def main(start_date,end_date,as_of_date,cached,print_sql):
    try:
        run(start_date,end_date,as_of_date,cached,print_sql)
    except (ValueError,OSError,KeyError,subprocess.CalledProcessError) as error:
        raise click.ClickException(str(error)) from error


if __name__=='__main__': main()

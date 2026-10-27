"""REFNUM 22: exact-product reorder attempts within 168 hours of aged cancellation."""
from datetime import date, datetime, timedelta, timezone
import hashlib
import json
import subprocess
import sys

import click
from jinja2 import Environment, StrictUndefined
import pandas as pd

from src.python.create_cmpu_prescription_first_order_status import ROOT, RUNNER, digest
from src.python.markdown_tables import markdown_table, table_layout
from src.python.markdown_tables import write_text

NAME = 'aged-order-same-product-reorders'
TEMPLATE = ROOT / 'src/sql/aged_order_same_product_reorders.sql'
RX_COLUMNS = ['rx_id', 'rx_source_rows', 'rx_creation_datetime', 'approval_channel',
              'customer_id', 'product_id', 'first_order_id', 'first_orderitem_id', 'first_order_line_id']
ORIGINAL_COLUMNS = ['original_order_id', 'original_line_id', 'original_customer_id', 'original_product_id',
    'original_product_variants', 'original_customer_variants', 'original_shipment_rows', 'original_line_status', 'original_status_variants',
    'order_cancel_reason', 'original_reason_variants', 'order_cancel_time', 'original_cancel_variants']
REORDER_COLUMNS = ['reorder_order_id', 'reorder_line_id', 'reorder_customer_id', 'reorder_product_id',
    'reorder_product_variants', 'reorder_customer_variants', 'reorder_shipment_rows', 'reorder_line_status', 'reorder_status_variants',
    'reorder_placed_at_utc', 'reorder_placed_at_eastern', 'reorder_placement_variants',
    'reorder_shipped_at_utc', 'reorder_shipped_at_eastern']
KEYS = ['original_order_id', 'original_line_id']


def render_sql(start, end, as_of, channel='CUSTOMER_UPLOAD'):
    start, end, as_of = map(date.fromisoformat, [start, end, as_of])
    if start >= end or as_of < end:
        raise ValueError('require start < exclusive end <= as-of date')
    if channel not in ['CUSTOMER_UPLOAD', 'ALL']:
        raise ValueError('unsupported approval channel scope')
    if as_of > datetime.now(timezone.utc).date():
        raise ValueError('as-of date cannot be in the future')
    return Environment(undefined=StrictUndefined).from_string(TEMPLATE.read_text()).render(
        start_date=start.isoformat(), end_date=end.isoformat(), as_of_date=as_of.isoformat(),
        customer_upload_only=channel == 'CUSTOMER_UPLOAD')


def summarize(raw, start, end, as_of, channel='CUSTOMER_UPLOAD', *, followup_days=7, require_same_pet=False):
    if followup_days not in [7, 14, 21]:
        raise ValueError('supported follow-up windows are 7, 14 and 21 days')
    window_word = {7: 'seven', 14: 'fourteen', 21: 'twenty-one'}[followup_days]
    within_window = 'shipped_within_' + window_word.replace('-', '_') + '_days'
    original_columns = ORIGINAL_COLUMNS + (['original_pet_id', 'original_pet_variants'] if require_same_pet else [])
    reorder_columns = REORDER_COLUMNS + (['reorder_pet_id', 'reorder_pet_variants'] if require_same_pet else [])
    frame = raw.rename(columns=str.lower).copy()
    for col in ['rx_creation_datetime', 'order_cancel_time', 'reorder_placed_at_utc',
                'reorder_placed_at_eastern', 'reorder_shipped_at_utc', 'reorder_shipped_at_eastern']:
        frame[col] = pd.to_datetime(frame[col], utc=True, format='mixed').astype('datetime64[ns, UTC]')
    cutoff = pd.Timestamp(as_of, tz='UTC')
    if frame.rx_id.isna().any() or not frame.rx_source_rows.eq(1).all():
        raise ValueError('missing or duplicate source prescription IDs')
    if frame.groupby('rx_id')[RX_COLUMNS].nunique(dropna=False).gt(1).any().any():
        raise ValueError('inconsistent prescription associations')
    associations = frame[RX_COLUMNS + original_columns].drop_duplicates()
    if associations.rx_id.duplicated().any():
        raise ValueError('inconsistent original line associations')
    if associations.rx_creation_datetime.isna().any() or not associations.rx_creation_datetime.between(
            pd.Timestamp(start, tz='UTC'), pd.Timestamp(end, tz='UTC'), inclusive='left').all():
        raise ValueError('prescription outside cohort window')
    if channel == 'CUSTOMER_UPLOAD' and not associations.approval_channel.eq(channel).all():
        raise ValueError('unexpected approval channel')
    for row in associations.itertuples():
        raw_key = '' if pd.isna(row.first_orderitem_id) else str(row.first_orderitem_id).strip()
        expected = int(raw_key) if raw_key.isascii() and raw_key.isdigit() else None
        if ((expected is None) != pd.isna(row.first_order_line_id)
                or (expected is not None and row.first_order_line_id != expected)):
            raise ValueError('invalid numeric first-order line key')
    matched = associations.original_order_id.notna()
    if matched.ne(associations.original_line_id.notna()).any() or (matched & (
            associations.original_order_id.ne(associations.first_order_id)
            | associations.original_line_id.ne(associations.first_order_line_id))).any():
        raise ValueError('both first-order join keys must agree')
    for col in ['original_status_variants', 'original_reason_variants', 'original_customer_variants']:
        if not associations.loc[matched, col].eq(1).all():
            raise ValueError('conflicting original status or cancellation reason')
    if associations.loc[matched, ['original_cancel_variants', 'original_product_variants']].gt(1).any().any():
        raise ValueError('conflicting cancellation timestamps or product mappings')
    aged_association = associations.order_cancel_reason.astype('string').str.strip().str.lower().eq('aged order').fillna(False)
    product_disagreement = (matched & associations.product_id.notna() & associations.original_product_id.notna()
                            & associations.product_id.ne(associations.original_product_id))
    for a,b in [('customer_id','original_customer_id'), ('product_id','original_product_id')]:
        compare = matched & associations[a].notna() & associations[b].notna()
        if a == 'product_id':
            compare &= aged_association
        if associations.loc[compare,a].ne(associations.loc[compare,b]).any():
            raise ValueError('prescription and original line customer/product disagree')
    original = associations.loc[matched, original_columns].drop_duplicates().reset_index(drop=True)
    if original.duplicated(KEYS).any():
        raise ValueError('inconsistent shipment or repeated line associations')
    original['eligibility'] = 'Eligible'
    aged = original.order_cancel_reason.astype('string').str.strip().str.lower().eq('aged order').fillna(False)
    original['followup_end_utc'] = original.order_cancel_time + pd.Timedelta(days=followup_days)
    # Mutually exclusive exclusions; quality indicators remain in details.
    masks = [(~aged, 'Not an Aged Order cancellation'),
        (original.order_cancel_time.isna(), 'Missing cancellation time'),
        (original.original_customer_id.isna(), 'Missing customer ID'),
        (original.original_product_id.isna(), 'Missing product mapping'),
        (original.order_cancel_time.gt(cutoff), 'Cancellation after as-of'),
        (original.followup_end_utc.gt(cutoff), f'Incomplete {window_word}-day follow-up')]
    if require_same_pet:
        if (original.original_pet_variants.isna().any() or original.original_pet_variants.lt(1).any()):
            raise ValueError('invalid original pet identity audit')
        masks[4:4] = [(original.original_pet_id.isna(), 'Missing pet ID'),
                      (original.original_pet_variants.gt(1), 'Ambiguous pet ID')]
    for mask,label in reversed(masks):
        original.loc[mask,'eligibility'] = label
    eligibility = original.set_index(KEYS).eligibility
    associations['association_state'] = [eligibility.loc[(r.original_order_id,r.original_line_id)] if pd.notna(r.original_order_id)
        else 'Missing order ID' if pd.isna(r.first_order_id)
        else 'Missing line ID' if pd.isna(r.first_orderitem_id) or str(r.first_orderitem_id).strip()==''
        else 'Invalid line ID' if pd.isna(r.first_order_line_id) else 'Unmatched line'
        for r in associations.itertuples()]
    candidate = frame.reorder_order_id.notna()
    if candidate.ne(frame.reorder_line_id.notna()).any():
        raise ValueError('incomplete reorder key')
    links = frame.loc[candidate, KEYS + reorder_columns].drop_duplicates()
    if links.duplicated(KEYS + ['reorder_order_id','reorder_line_id']).any():
        raise ValueError('conflicting reorder association values')
    reorders = links[reorder_columns].drop_duplicates()
    if reorders.duplicated(['reorder_order_id','reorder_line_id']).any():
        raise ValueError('inconsistent reorder line across cancellation associations')
    if (not reorders.reorder_status_variants.eq(1).all()
            or not reorders.reorder_customer_variants.eq(1).all()
            or not reorders.reorder_placement_variants.eq(1).all()
            or reorders.reorder_product_variants.gt(1).any()):
        raise ValueError('conflicting reorder status, placement or product mapping')
    for utc,eastern in [('reorder_placed_at_utc','reorder_placed_at_eastern'),
                        ('reorder_shipped_at_utc','reorder_shipped_at_eastern')]:
        left = reorders[utc].dt.tz_convert('America/New_York').dt.tz_localize(None)
        right = reorders[eastern].dt.tz_localize(None)
        if (left.notna() & right.notna() & (left-right).abs().gt(pd.Timedelta(seconds=1))).any():
            raise ValueError('UTC/Eastern reorder timestamp disagreement')
    links = links.merge(original, on=KEYS, how='left', validate='many_to_one')
    if (links.eligibility.isna().any() or links.reorder_order_id.eq(links.original_order_id).any()
            or links.reorder_customer_id.isna().any() or links.reorder_product_id.isna().any()
            or links.reorder_customer_id.ne(links.original_customer_id).any()
            or links.reorder_product_id.ne(links.original_product_id).any()
            or links.reorder_placed_at_utc.isna().any()
            or links.reorder_placed_at_utc.le(links.order_cancel_time).any()
            or links.reorder_placed_at_utc.gt(links.followup_end_utc).any()
            or links.reorder_placed_at_utc.gt(cutoff).any()):
        raise ValueError(f'invalid same-customer/product {window_word}-day reorder match')
    if require_same_pet and (links.original_pet_id.isna().any() or links.reorder_pet_id.isna().any()
            or not links.original_pet_variants.eq(1).all() or not links.reorder_pet_variants.eq(1).all()
            or links.original_pet_id.ne(links.reorder_pet_id).any()):
        raise ValueError('reorder pet identity does not match original line')
    if (links.reorder_shipped_at_utc.notna() & links.reorder_shipped_at_utc.lt(links.reorder_placed_at_utc)).any():
        raise ValueError('reorder shipment precedes order placement')
    links['elapsed_days'] = (links.reorder_placed_at_utc-links.order_cancel_time).dt.total_seconds()/86400
    links['shipped_by_as_of'] = links.reorder_shipped_at_utc.notna() & links.reorder_shipped_at_utc.le(cutoff)
    links[within_window] = links.shipped_by_as_of & links.reorder_shipped_at_utc.le(links.followup_end_utc)
    attempts = links.groupby(KEYS).size()
    shipped = links.groupby(KEYS).shipped_by_as_of.sum()
    original = original.set_index(KEYS)
    original['reorder_line_attempts'] = attempts.reindex(original.index,fill_value=0).astype(int)
    original['shipped_reorder_lines'] = shipped.reindex(original.index,fill_value=0).astype(int)
    original['has_reorder'] = original.reorder_line_attempts.gt(0)
    original['has_shipped_reorder'] = original.shipped_reorder_lines.gt(0)
    original = original.reset_index()
    eligible = original.loc[original.eligibility.eq('Eligible')]
    summaries=[]
    for grain,keys in [('Canceled order lines',KEYS), ('Canceled orders',['original_order_id']),
        ('Customer/product pairs',['original_customer_id','original_product_id']), ('Customers',['original_customer_id'])]:
        groups=eligible.groupby(keys,dropna=False).agg(reordered=('has_reorder','any'),shipped=('has_shipped_reorder','any'))
        denominator=len(groups)
        for outcome,col in [(f'Any reorder attempt within {followup_days} days','reordered'),(f'Reorder within {followup_days} days, shipped by as-of','shipped')]:
            numerator=int(groups[col].sum())
            summaries.append(dict(grain=grain,outcome=outcome,denominator=denominator,count=numerator,
                                  percent=100*numerator/denominator if denominator else None))
    summary=pd.DataFrame(summaries)
    audit=[('Prescription associations',len(associations)), ('Distinct matched original lines',len(original)),
           ('Qualifying reorder line associations',len(links)), ('Distinct reorder lines',len(reorders)),
           ('Reorder lines linked to multiple cancellations',int(links.groupby(['reorder_order_id','reorder_line_id']).size().gt(1).sum()))]
    audit += [(f'Associations: {k}',int(v)) for k,v in associations.association_state.value_counts().items()]
    audit += [(f'Original lines: {k}',int(v)) for k,v in original.eligibility.value_counts().items()]
    audit += [('Prescription/original product disagreements outside aged cohort',int((product_disagreement & ~aged_association).sum()))]
    audit += [('Original shipment rows',int(original.original_shipment_rows.sum())),
              ('Reorder shipment rows',int(reorders.reorder_shipment_rows.sum())),
              ('Missing original customer',int(original.original_customer_id.isna().sum())),
              ('Missing original product mapping',int(original.original_product_id.isna().sum())),
              ('Aged reason with non-X line status',int((aged & original.original_line_status.ne('X')).sum())),
              ('Missing reorder Eastern placement companions',int(reorders.reorder_placed_at_eastern.isna().sum())),
              (f'Qualifying reorder lines shipped within cancellation + {followup_days} days',int(links[within_window].sum()))]
    if require_same_pet:
        audit += [('Original lines missing pet ID', int(original.original_pet_id.isna().sum())),
                  ('Original lines with ambiguous pet ID', int(original.original_pet_variants.gt(1).sum()))]
    if summary['count'].gt(summary.denominator).any() or summary.loc[summary.outcome.str.contains('shipped'),'count'].to_numpy().max(initial=0)>len(eligible):
        raise ValueError('summary counts do not reconcile')
    return associations, original, links, summary, pd.DataFrame(audit,columns=['measure','count'])


def load_source(start,end,as_of,channel,cached):
    sql=render_sql(start,end,as_of,channel)
    period=f'{start}_{end}_{channel.lower()}_reorders-7d_as-of-{as_of}'
    directory=ROOT/'data'/NAME/period
    parquet,manifest=directory/'source.parquet',directory/'source.json'
    options=dict(start_date=start,end_date_exclusive=end,as_of_date=as_of,approval_channel=channel)
    if cached:
        metadata=json.loads(manifest.read_text())
        if (metadata.get('sql')!=sql or metadata.get('sql_sha256')!=hashlib.sha256(sql.encode()).hexdigest()
                or metadata.get('parquet_sha256')!=digest(parquet)
                or any(metadata.get(k)!=v for k,v in options.items())):
            raise ValueError('cached SQL, dates, scope or fingerprint differs; refresh extract')
        frame=pd.read_parquet(parquet)
    else:
        directory.mkdir(parents=True,exist_ok=True)
        generated=ROOT/'src/autogenerated'/NAME/period
        generated.mkdir(parents=True,exist_ok=True)
        query=generated/'aged_order_same_product_reorders.sql';write_text(query, sql+'\n')
        manifest.unlink(missing_ok=True)
        subprocess.run([sys.executable,str(RUNNER),str(query),'--output-parquet',str(parquet.relative_to(ROOT)),
                        '--sql-log-dir',str((generated/'sql-history').relative_to(ROOT))],cwd=ROOT,check=True)
        frame=pd.read_parquet(parquet).rename(columns=str.lower)
        summarize(frame,start,end,as_of,channel)
        metadata=dict(options,sql=sql,sql_sha256=hashlib.sha256(sql.encode()).hexdigest(),
            parquet_sha256=digest(parquet),extracted_at_utc=datetime.now(timezone.utc).isoformat(),
            source_extracted_at=frame.extracted_at_session_time.unique().tolist(),
            warehouse=frame.extraction_warehouse.unique().tolist())
        write_text(manifest, json.dumps(metadata,indent=2)+'\n')
    return frame,metadata,period


def write_outputs(frame,metadata,period):
    outputs=summarize(frame,metadata['start_date'],metadata['end_date_exclusive'],metadata['as_of_date'],metadata['approval_channel'])
    tables,prefix=table_layout(ROOT,NAME,period);tables.mkdir(parents=True,exist_ok=True)
    directory=ROOT/'data'/NAME/period;directory.mkdir(parents=True,exist_ok=True)
    note=(f"CMPU vet-diet prescriptions UTC [{metadata['start_date']}, {metadata['end_date_exclusive']}); "
        f"approval channels: {metadata['approval_channel']}. As-of UTC {metadata['as_of_date']} 00:00.\n\n"
        'Aged Order means the recorded order cancellation reason, case/outer whitespace normalized. '
        'Original lines join both first-order keys. Reorder attempts require exact CUSTOMER_ID and PRODUCT_ID, '
        'a different order, and placement in (cancellation, cancellation + 168 hours], no later than as-of. '
        'Product IDs map through line PRODUCT_PART_NUMBER to the latest PDM.PRODUCT snapshot; unmapped IDs remain audited. '
        'Prescription/line product disagreements outside aged cancellations are audited; '
        'disagreements within aged cancellations stop the analysis. Shipment rows and prescription associations are deduplicated. No reorder channel or prescription-source filter. '
        'All placed statuses count as attempts, including subsequently canceled reorders. Fulfilled means shipment '
        'timestamp evidence by as-of, possibly later than seven days; it does not imply delivery or full-quantity fulfillment. '
        'Only cancellations with complete seven-day follow-up and usable keys enter rates. '
        'Customer/product and customer denominators require at least one eligible cancellation; only reorder evidence '
        'from eligible cancellations enters their numerators. A reorder may link to multiple cancellations in details, '
        'but each customer/product pair or customer counts once in summaries. '
        'Current statuses are extraction-time snapshots, not reconstructed as-of statuses. '
        'ORDER_CANCEL_DTTM and unsuffixed placement/shipment timestamps are UTC under the established Eastern-companion convention.\n\n'
        f"Source SHA-256: {metadata['parquet_sha256']}; extracted {metadata['extracted_at_utc']}.\n\n")
    hashes={}
    for kind,data in zip(['associations','canceled-line-details','reorder-matches','summary','audit'],outputs):
        write_text(tables/f'{prefix}{kind}.md', f'# Seven-day same-product reorders: {kind}\n\n'+note+markdown_table(data)+'\n')
        path=directory/f'{kind}.parquet';data.to_parquet(path,index=False);hashes[path.name]=digest(path)
    write_text(directory/'exports.json', json.dumps(dict(source_sha256=metadata['parquet_sha256'],files=hashes),indent=2)+'\n')
    return outputs[3],outputs[4],tables


@click.command()
@click.option('--start-date',default='2026-08-15',show_default=True)
@click.option('--end-date',default='2026-10-15',show_default=True)
@click.option('--as-of-date',default=lambda:datetime.now(timezone.utc).date().isoformat(),help='UTC midnight; excludes later placements/shipments.')
@click.option('--approval-channel',type=click.Choice(['CUSTOMER_UPLOAD','ALL']),default='CUSTOMER_UPLOAD',show_default=True)
@click.option('--cached',is_flag=True)
@click.option('--print-sql',is_flag=True)
def main(start_date,end_date,as_of_date,approval_channel,cached,print_sql):
    try:
        if print_sql:
            click.echo(render_sql(start_date,end_date,as_of_date,approval_channel));return
        frame,metadata,period=load_source(start_date,end_date,as_of_date,approval_channel,cached)
        summary,audit,tables=write_outputs(frame,metadata,period)
        click.echo(summary.to_string(index=False));click.echo(audit.to_string(index=False));click.echo(f'Tables: {tables}')
    except (ValueError,OSError,KeyError,subprocess.CalledProcessError) as error:
        raise click.ClickException(str(error)) from error


if __name__=='__main__':
    main()

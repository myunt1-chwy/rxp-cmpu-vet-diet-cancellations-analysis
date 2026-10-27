"""REFNUM 35: customer shipment history strictly before first aged cancellation."""
from datetime import date, datetime, timezone
import hashlib
import json
import subprocess
import sys

import click
from jinja2 import Environment, StrictUndefined
import pandas as pd

from src.python import create_aged_order_all_contact_cancellation_distribution as cohort
from src.python.create_cmpu_prescription_first_order_status import ROOT, RUNNER, digest
from src.python.markdown_tables import markdown_table, table_layout, write_text
from src.python.prior_shipment_history import summarize_history, FLAGS

NAME = 'aged-customer-prior-shipped-prescriptions'
TEMPLATE = ROOT/'src/sql/aged_customer_prior_shipped_prescriptions.sql'
HISTORY = ['order_id','order_line_id','rx_id','shipment_customer_id','customer_variants','shipped_at_utc',
    'shipment_rows','rx_customer_id','rx_source_rows','is_vet_diet_flag','prescription_source','merch_class2']
NOTE = ('CMPU vet-diet CUSTOMER_UPLOAD prescriptions define the aged-order cohort. Each customer is counted once. '
    'Reference = earliest qualifying aged cancellation; every qualifying aged-cancelled order is excluded from history, '
    'including all tied reference orders and all lines on those orders. '
    'Shipment evidence is ORDER_LINE_SHIPPED_DTTM strictly before that cancellation, UTC, on another order. '
    'A shipped line is sufficient; delivery, complete-order fulfillment and current status are not required. '
    'Historical RX_ID and customer ID must both match; history is not restricted by prescription creation dates, '
    'approval channel, product or pet. Shipment rows collapse by order/line/RX_ID before customer aggregation. '
    'Inclusive pharmacy means vet diet (IS_VET_DIET_FLAG=TRUE) or MERCH_CLASS2 Pharmacy, Compound, Over the Counter. '
    'CMPU vet diet additionally requires PRESCRIPTION_SOURCE=CMPU. All percentages use the full aged-customer denominator. '
    'Vet diet is a subset of inclusive pharmacy, and CMPU vet diet is a subset of vet diet; do not add headline counts. '
    'Other/unclassified categories remain in evidence/audits, outside those three flags. '
    'Available-history dates describe observed candidate shipments for cohort customers, not warehouse retention bounds. '
    'Full detail is retained in the matching data/ Parquet files. ')


def render_sql(start,end,as_of):
    start,end,as_of=map(date.fromisoformat,[start,end,as_of])
    if not start<end<=as_of<=datetime.now(timezone.utc).date():
        raise ValueError('require start < exclusive end <= as-of <= current UTC date')
    return Environment(undefined=StrictUndefined).from_string(TEMPLATE.read_text()).render(
        start_date=start.isoformat(),end_date=end.isoformat(),as_of_date=as_of.isoformat())


def unpack(raw):
    raw=raw.rename(columns=str.lower)
    if not raw.record_type.isin(['association','shipment']).all():
        raise ValueError('unexpected source record type')
    def frame(kind,columns):
        return pd.DataFrame([{k.lower():v for k,v in json.loads(p).items()}
            for p in raw.loc[raw.record_type.eq(kind),'payload']],columns=columns)
    return frame('association',cohort.ASSOCIATIONS),frame('shipment',HISTORY)


def summarize(associations,history,start,end,as_of):
    render_sql(start,end,as_of)
    population=cohort.summarize(associations,pd.DataFrame(columns=cohort.CONTACTS),start,end,as_of)
    orders=population['orders'].drop(columns='contact_count')
    customers=orders.groupby('customer_id').agg(reference_cancel_time=('order_cancel_time','min'),
        aged_orders=('order_id','size')).reset_index()
    anchors=orders.merge(customers[['customer_id','reference_cancel_time']],on='customer_id',validate='many_to_one')
    anchors=anchors.loc[anchors.order_cancel_time.eq(anchors.reference_cancel_time)]
    h=history.copy()
    if h[['order_id','order_line_id']].isna().any().any() or h.duplicated(['order_id','order_line_id','rx_id']).any():
        raise ValueError('missing or duplicate historical order/line/RX keys')
    if (not h.customer_variants.eq(1).all() or h.rx_source_rows.isna().any()
            or h.rx_source_rows.gt(1).any() or h.rx_source_rows.lt(0).any()):
        raise ValueError('conflicting historical customer or prescription identities')
    if h.groupby(['order_id','order_line_id']).shipment_customer_id.nunique(dropna=False).gt(1).any():
        raise ValueError('conflicting customers across historical prescription associations')
    h['shipped_at_utc']=pd.to_datetime(h.shipped_at_utc,utc=True,format='mixed').astype('datetime64[ns, UTC]')
    h=h.merge(customers[['customer_id','reference_cancel_time']],left_on='shipment_customer_id',right_on='customer_id',
              how='left',validate='many_to_one')
    anchor_keys=set(zip(anchors.customer_id,anchors.order_id))
    h['is_reference_order']=[(r.shipment_customer_id,r.order_id) in anchor_keys for r in h.itertuples()]
    h['is_aged_cancelled_order']=h.order_id.isin(orders.order_id)
    h['eligibility']='Eligible'
    # Apply the most specific key/source exclusions last.
    h.loc[h.is_reference_order,'eligibility']='Reference order'
    h.loc[h.is_aged_cancelled_order & ~h.is_reference_order,'eligibility']='Other aged-cancelled order'
    h.loc[h.shipped_at_utc.ge(h.reference_cancel_time),'eligibility']='At/after reference cancellation'
    h.loc[h.shipped_at_utc.isna(),'eligibility']='Missing shipment time'
    h.loc[h.rx_customer_id.isna()|h.rx_customer_id.ne(h.shipment_customer_id),'eligibility']='RX/customer mismatch'
    h.loc[h.rx_source_rows.eq(0),'eligibility']='Unmatched RX_ID'
    h.loc[h.rx_id.isna(),'eligibility']='Missing RX_ID'
    h.loc[h.reference_cancel_time.isna(),'eligibility']='Customer outside cohort'
    result=summarize_history(customers,h)
    customers,h=result['customers'],result['shipment-evidence']
    summary=result['summary'].rename(columns={'percent_of_customers':'percent_of_aged_customers'})
    summary.loc[summary.measure.eq('Customers'),'measure']='Aged customers'
    exclusive=result['exclusive-groups'].rename(columns={'percent_of_customers':'percent_of_aged_customers'})
    categories=result['categories']
    denominator=len(customers)
    merch=h.merch_class2.astype('string').str.strip().str.casefold()
    vet=h.is_vet_diet_flag.eq(True)
    eligible=h.eligibility.eq('Eligible')
    if (eligible & h.is_aged_cancelled_order).any():
        raise ValueError('an aged-cancelled order contributed prior shipment evidence')
    audit=[dict(measure='Cohort association: '+r.association_state,count=int(r.prescriptions))
           for r in population['audit'].itertuples()]
    audit += [dict(measure='History: '+str(k),count=int(v)) for k,v in h.eligibility.value_counts().items()]
    audit += [dict(measure='Aged orders missing customer ID',count=int(orders.customer_id.isna().sum())),
        dict(measure='Collapsed history shipment rows',count=int(h.shipment_rows.sum())-len(h)),
        dict(measure='Eligible unclassified history records',count=int((eligible & h.category.eq('Other/unclassified')).sum())),
        dict(measure='Vet-diet flag disagrees with merchandise category',count=int((eligible & vet & merch.isin(['pharmacy','compound','over the counter'])).sum()))]
    observed=h.loc[h.reference_cancel_time.notna() & h.shipped_at_utc.lt(h.reference_cancel_time),'shipped_at_utc']
    coverage=pd.DataFrame([dict(earliest_observed_candidate_shipment_utc=observed.min(),
        latest_observed_candidate_shipment_utc=observed.max(),reference_customers=denominator)])
    if exclusive.customers.sum()!=denominator or customers.customer_id.duplicated().any():
        raise ValueError('customer groups do not reconcile')
    return {'summary':summary,'exclusive-groups':exclusive,'categories':categories,
        'customers':customers,'reference-orders':anchors,'aged-orders':orders,'associations':population['associations'],
        'shipment-evidence':h,'audit':pd.DataFrame(audit),'history-coverage':coverage}


def run(start,end,as_of,cached=False,print_sql=False):
    sql=render_sql(start,end,as_of)
    if print_sql:
        click.echo(sql)
        return
    period=f'{start}_{end}_as-of-{as_of}'
    directory=ROOT/'data'/NAME/period
    parquet,manifest=directory/'source.parquet',directory/'source.json'
    expected=dict(start_date=start,end_date_exclusive=end,as_of_date=as_of,
                  sql_sha256=hashlib.sha256(sql.encode()).hexdigest(),time_zone='UTC')
    if cached:
        metadata=json.loads(manifest.read_text())
        if any(metadata.get(k)!=v for k,v in expected.items()) or metadata.get('parquet_sha256')!=digest(parquet):
            raise ValueError('cached SQL, dates or source fingerprint differs; refresh extract')
    else:
        directory.mkdir(parents=True,exist_ok=True)
        generated=ROOT/'src/autogenerated'/NAME/period
        generated.mkdir(parents=True,exist_ok=True)
        query=generated/'aged_customer_prior_shipped_prescriptions.sql'
        write_text(query,sql+'\n')
        manifest.unlink(missing_ok=True)
        subprocess.run([sys.executable,str(RUNNER),str(query),'--output-parquet',str(parquet.relative_to(ROOT)),
            '--sql-log-dir',str((generated/'sql-history').relative_to(ROOT))],cwd=ROOT,check=True)
        metadata=dict(expected,parquet_sha256=digest(parquet),extracted_at_utc=datetime.now(timezone.utc).isoformat())
    raw=pd.read_parquet(parquet)
    outputs=summarize(*unpack(raw),start,end,as_of)
    metadata['warehouse']=raw.rename(columns=str.lower).extraction_warehouse.dropna().unique().tolist()
    write_text(manifest,json.dumps(metadata,indent=2)+'\n')
    # Compare to the frozen REFNUM 32 population when the matching snapshot exists.
    baseline=ROOT/'data'/cohort.NAME/(f'{start}_{end}_as-of-{as_of}_all-handled-contacts_all-order-history_UTC')/'orders.parquet'
    if baseline.exists():
        original=set(pd.read_parquet(baseline).customer_id.dropna())
        current=set(outputs['customers'].customer_id)
        outputs['cohort-comparison']=pd.DataFrame([dict(previous_customers=len(original),current_customers=len(current),
            added_customers=len(current-original),removed_customers=len(original-current),baseline_sha256=digest(baseline))])
    tables,prefix=table_layout(ROOT,NAME,period)
    tables.mkdir(parents=True,exist_ok=True)
    files={}
    note=NOTE+f"Extracted {metadata['extracted_at_utc']}; source SHA-256 {metadata['parquet_sha256']}.\n\n"
    for kind,frame in outputs.items():
        full=directory/f'{kind}.parquet';frame.to_parquet(full,index=False)
        table=tables/f'{prefix}{kind}.md'
        write_text(table,f'# Prior shipped prescriptions: {kind}\n\n'+note+markdown_table(frame)+'\n')
        for path in [full,table]:files[str(path.relative_to(ROOT))]=digest(path)
    write_text(directory/'manifest.json',json.dumps(dict(source=metadata,files=files),indent=2)+'\n')
    click.echo(outputs['summary'].to_string(index=False))
    click.echo(f'Tables: {tables}')


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


if __name__=='__main__':main()

"""REFNUM 42: prior same-clinic shipment experience using order-line CLINIC_ID."""
from datetime import date,datetime,timezone
import hashlib
import json
import subprocess
import sys

import click
from jinja2 import Environment,StrictUndefined
import pandas as pd

from src.python import create_aged_customer_prior_shipped_prescriptions as prior
from src.python import create_aged_order_all_contact_cancellation_distribution as cohort
from src.python.create_cmpu_prescription_first_order_status import ROOT,RUNNER,digest
from src.python.markdown_tables import markdown_table,table_layout,write_text

NAME='aged-customer-prior-same-clinic-shipments'
TEMPLATE=ROOT/'src/sql/aged_customer_prior_same_clinic_shipments.sql'
CLINIC_SOURCE='EDLDB.BT_HCA_HCDM.ORDER_LINE_COST_MEASURES_RXP.CLINIC_ID'
ASSOCIATIONS=cohort.ASSOCIATIONS+['aged_clinic_id','prescription_clinic_id','line_clinic_variants',
    'order_placed_time','order_placed_eastern','placed_variants','eastern_variants']
HISTORY=prior.HISTORY+['history_clinic_id','prescription_history_clinic_id','history_clinic_variants']
GROUPS=['Observed prior same-clinic shipment','Prior shipments with other recorded clinics only',
        'No qualifying prior prescription shipments','Unknown']
UNRESOLVED=['Missing historical clinic ID','Unmatched RX_ID','RX/customer mismatch','Missing RX_ID']
NOTE=('CMPU vet-diet CUSTOMER_UPLOAD prescriptions define the aged-order cohort. '
    'Compare ORDER_LINE_COST_MEASURES_RXP.CLINIC_ID on both aged and historical shipped lines. '
    'Prescription clinic IDs are comparison fields only; there is no prescription fallback. '
    'Count each customer once across all their aged orders/recorded clinics. '
    'Prior shipment must be strictly before the specific aged order placement, UTC, on a different order; '
    'every qualifying aged-cancelled order and all its lines are excluded. '
    'Historical RX_ID and customer IDs must match; source/channel/product/pet are unrestricted. '
    'Shipment repetitions collapse before comparison. Conflicting populated shipment-row clinic IDs stop publication. '
    'A positive match takes precedence over incomplete information elsewhere. Otherwise missing clinic/placement '
    'or unresolved prior prescription/customer/clinic information makes the customer Unknown. Null IDs never match. '
    'Known other-clinic history and no qualifying prior prescription history are separate categories. '
    'Percentages use all customers and separately assessable customers; Unknown is not no prior relationship. '
    'Unknown-reason counts overlap. CLINIC_ID identifies the recorded clinic, and does not establish an individual vet match. '
    'Complete evidence is in the associated data/ Parquet files. ')


def render_sql(start,end,as_of):
    start,end,as_of=map(date.fromisoformat,[start,end,as_of])
    if not start<end<=as_of<=datetime.now(timezone.utc).date():
        raise ValueError('require start < exclusive end <= as-of <= current UTC date')
    return Environment(undefined=StrictUndefined).from_string(TEMPLATE.read_text()).render(
        start_date=start.isoformat(),end_date=end.isoformat(),as_of_date=as_of.isoformat())


def unpack(raw):
    raw=raw.rename(columns=str.lower)
    if not raw.record_type.isin(['association','shipment']).all():raise ValueError('unexpected source record type')
    def frame(kind,cols):
        return pd.DataFrame([{k.lower():v for k,v in json.loads(p).items()}
            for p in raw.loc[raw.record_type.eq(kind),'payload']],columns=cols)
    return frame('association',ASSOCIATIONS),frame('shipment',HISTORY)


def summarize(a,h,start,end,as_of):
    render_sql(start,end,as_of)
    a,h=a.copy(),h.copy()
    population=cohort.summarize(a,pd.DataFrame(columns=cohort.CONTACTS),start,end,as_of)
    orders=population['orders'].drop(columns='contact_count')
    matched=a.order_id.notna()
    if (a.loc[matched,'line_clinic_variants'].isna().any() or a.loc[matched,'line_clinic_variants'].gt(1).any()
            or a.loc[matched,'line_clinic_variants'].eq(0).ne(a.loc[matched,'aged_clinic_id'].isna()).any()):
        raise ValueError('conflicting or inconsistent aged order-line clinic IDs')
    line_clinics=a.loc[matched,['order_id','order_line_id','aged_clinic_id']].drop_duplicates()
    if line_clinics.duplicated(['order_id','order_line_id']).any():
        raise ValueError('conflicting repeated aged order-line clinic IDs')
    for col in ['placed_variants','eastern_variants']:
        if a.loc[matched,col].isna().any() or a.loc[matched,col].gt(1).any():
            raise ValueError('conflicting order placement timestamps')
    a['order_placed_time']=pd.to_datetime(a.order_placed_time,utc=True,format='mixed').astype('datetime64[ns, UTC]')
    a['order_placed_eastern']=pd.to_datetime(a.order_placed_eastern,format='mixed').astype('datetime64[ns]')
    paired=a.order_placed_time.notna() & a.order_placed_eastern.notna()
    eastern=a.order_placed_time.dt.tz_convert('America/New_York').dt.tz_localize(None)
    if a.loc[paired,'order_placed_eastern'].ne(eastern.loc[paired]).any():
        raise ValueError('UTC/Eastern placement companions disagree')
    placements=a.loc[matched,['order_id','order_line_id','order_placed_time']].drop_duplicates()
    if placements.duplicated(['order_id','order_line_id']).any() or placements.groupby('order_id').order_placed_time.nunique(dropna=False).gt(1).any():
        raise ValueError('conflicting repeated order/line placement')
    orders=orders.merge(placements.drop_duplicates('order_id')[['order_id','order_placed_time']],
                        on='order_id',how='left',validate='one_to_one')
    refs=a.loc[a.order_id.isin(orders.order_id)].copy()
    refs['missing_aged_clinic']=refs.aged_clinic_id.isna()
    refs['missing_placement']=refs.order_placed_time.isna()
    refs['aged_customer_mismatch']=refs.rx_customer_id.isna() | refs.rx_customer_id.ne(refs.customer_id)
    refs['reference_incomplete']=refs[['missing_aged_clinic','missing_placement','aged_customer_mismatch']].any(axis=1)
    if h[['order_id','order_line_id']].isna().any().any() or h.duplicated(['order_id','order_line_id','rx_id']).any():
        raise ValueError('missing or duplicate historical order/line/RX keys')
    if (not h.customer_variants.eq(1).all() or h.rx_source_rows.isna().any()
            or not h.rx_source_rows.isin([0,1]).all()):
        raise ValueError('conflicting historical customer or prescription identities')
    if h.groupby(['order_id','order_line_id']).shipment_customer_id.nunique(dropna=False).gt(1).any():
        raise ValueError('conflicting historical order-line customer')
    if (h.history_clinic_variants.isna().any() or h.history_clinic_variants.gt(1).any()
            or h.history_clinic_variants.eq(0).ne(h.history_clinic_id.isna()).any()):
        raise ValueError('conflicting or inconsistent historical order-line clinic IDs')
    h['shipped_at_utc']=pd.to_datetime(h.shipped_at_utc,utc=True,format='mixed').astype('datetime64[ns, UTC]')
    h['is_aged_cancelled_order']=h.order_id.isin(orders.order_id)
    h['eligibility']='Eligible'
    h.loc[h.history_clinic_id.isna(),'eligibility']='Missing historical clinic ID'
    h.loc[h.rx_customer_id.isna() | h.rx_customer_id.ne(h.shipment_customer_id),'eligibility']='RX/customer mismatch'
    h.loc[h.rx_source_rows.eq(0),'eligibility']='Unmatched RX_ID'
    h.loc[h.rx_id.isna(),'eligibility']='Missing RX_ID'
    h.loc[h.is_aged_cancelled_order,'eligibility']='Aged-cancelled order'
    h.loc[h.shipped_at_utc.isna(),'eligibility']='Missing shipment time'
    h.loc[~h.shipment_customer_id.isin(orders.customer_id.dropna()),'eligibility']='Customer outside cohort'
    valid=h.loc[h.eligibility.eq('Eligible')]
    clinics=valid.groupby(['shipment_customer_id','history_clinic_id']).agg(
        first_shipped_at_utc=('shipped_at_utc','min'),history_records=('rx_id','size'),
        distinct_orders=('order_id','nunique')).reset_index()
    refs=refs.merge(clinics,left_on=['customer_id','aged_clinic_id'],right_on=['shipment_customer_id','history_clinic_id'],
        how='left',validate='many_to_one')
    refs['same_clinic_prior_shipment']=~refs.reference_incomplete & refs.first_shipped_at_utc.lt(refs.order_placed_time)
    earliest=valid.groupby('shipment_customer_id').shipped_at_utc.min()
    unresolved=h.loc[h.eligibility.isin(UNRESOLVED)].groupby('shipment_customer_id').shipped_at_utc.min()
    refs['first_known_clinic_shipment_utc']=earliest.reindex(refs.customer_id).array
    refs['first_unresolved_shipment_utc']=unresolved.reindex(refs.customer_id).array
    refs['has_known_prior_shipment']=refs.first_known_clinic_shipment_utc.lt(refs.order_placed_time)
    refs['unresolved_prior_history']=refs.first_unresolved_shipment_utc.lt(refs.order_placed_time)
    customers=refs.loc[refs.customer_id.notna()].groupby('customer_id').agg(
        aged_orders=('order_id','nunique'),recorded_aged_clinics=('aged_clinic_id','nunique'),
        has_prior_same_clinic=('same_clinic_prior_shipment','any'),
        incomplete_aged_reference=('reference_incomplete','any'),
        unresolved_prior_history=('unresolved_prior_history','any'),
        has_known_prior_shipment=('has_known_prior_shipment','any')).reset_index()
    if set(customers.customer_id)!=set(orders.customer_id.dropna()):
        raise ValueError('customer clinic references differ from aged population')
    customers['group']=GROUPS[2]
    customers.loc[customers.has_known_prior_shipment,'group']=GROUPS[1]
    customers.loc[customers.incomplete_aged_reference | customers.unresolved_prior_history,'group']=GROUPS[3]
    customers.loc[customers.has_prior_same_clinic,'group']=GROUPS[0]
    customers['assessable']=customers.group.ne(GROUPS[3])
    quality={}
    ref_flags=refs.loc[refs.customer_id.notna()].groupby('customer_id')[[
        'missing_aged_clinic','missing_placement','aged_customer_mismatch']].any()
    for customer,row in ref_flags.iterrows():
        quality[customer]=[label for flag,label in [('missing_aged_clinic','Missing aged clinic ID'),
            ('missing_placement','Missing aged order placement'),('aged_customer_mismatch','Aged RX/customer mismatch')]
            if row[flag]]
    latest_placement=refs.groupby('customer_id').order_placed_time.max()
    unresolved_times=h.loc[h.eligibility.isin(UNRESOLVED)].groupby([
        'shipment_customer_id','eligibility']).shipped_at_utc.min().reset_index()
    for row in unresolved_times.itertuples():
        latest=latest_placement.get(row.shipment_customer_id,pd.NaT)
        if pd.notna(latest) and row.shipped_at_utc<latest:
            quality.setdefault(row.shipment_customer_id,[]).append(row.eligibility)
    customers['quality_reasons']=customers.customer_id.map(lambda c:'; '.join(sorted(set(quality.get(c,[])))))
    customers['unknown_reasons']=customers.quality_reasons.where(~customers.assessable,'')
    total=len(customers);assessable=int(customers.assessable.sum())
    summary=customers.group.value_counts().reindex(GROUPS,fill_value=0).rename_axis('group').reset_index(name='customers')
    summary['percent_of_all_customers']=100*summary.customers/total if total else None
    summary['percent_of_assessable_customers']=100*summary.customers/assessable if assessable else None
    summary.loc[summary.group.eq(GROUPS[3]),'percent_of_assessable_customers']=None
    if summary.customers.sum()!=total or customers.customer_id.duplicated().any():raise ValueError('customer groups do not reconcile')
    audit=[dict(measure='Association: '+str(k),count=int(v)) for k,v in population['associations'].association_state.value_counts().items()]
    audit += [dict(measure='History: '+str(k),count=int(v)) for k,v in h.eligibility.value_counts().items()]
    audit += [dict(measure='Aged customers',count=total),dict(measure='Assessable customers',count=assessable),
        dict(measure='Aged orders',count=len(orders)),dict(measure='Aged orders missing customer',count=int(orders.customer_id.isna().sum())),
        dict(measure='References missing aged clinic',count=int(refs.missing_aged_clinic.sum())),
        dict(measure='References missing placement',count=int(refs.missing_placement.sum())),
        dict(measure='References with aged customer mismatch',count=int(refs.aged_customer_mismatch.sum())),
        dict(measure='References with unresolved prior history',count=int(refs.unresolved_prior_history.sum())),
        dict(measure='References with populated prescription clinic ID',count=int(refs.prescription_clinic_id.notna().sum())),
        dict(measure='Aged populated order-line/prescription clinic disagreements',count=int((refs.aged_clinic_id.notna() & refs.prescription_clinic_id.notna() & refs.aged_clinic_id.ne(refs.prescription_clinic_id)).sum())),
        dict(measure='Historical populated order-line/prescription clinic disagreements',count=int((h.history_clinic_id.notna() & h.prescription_history_clinic_id.notna() & h.history_clinic_id.ne(h.prescription_history_clinic_id)).sum()))]
    coverage=pd.DataFrame([dict(earliest_observed_candidate_shipment_utc=h.shipped_at_utc.min(),
        latest_observed_candidate_shipment_utc=h.shipped_at_utc.max())])
    clinic_coverage=pd.DataFrame([dict(scope=label,records=len(frame),with_clinic_id=int(frame[clinic].notna().sum()),
        missing_clinic_id=int(frame[clinic].isna().sum()),customers=frame[customer].nunique(),
        customers_with_any_clinic_id=frame.loc[frame[clinic].notna(),customer].nunique())
        for label,frame,clinic,customer in [('Aged-order prescription references',refs,'aged_clinic_id','customer_id'),
            ('Historical candidate records',h,'history_clinic_id','shipment_customer_id')]])
    unknown=customers.loc[~customers.assessable,'unknown_reasons'].astype('string').str.split('; ').explode().value_counts()
    unknown_reasons=unknown.rename_axis('reason').reset_index(name='customers')
    outputs={'summary':summary,'customers':customers,'aged-orders':orders,'aged-order-clinic-references':refs,
        'associations':population['associations'],'shipment-evidence':h,'customer-clinic-history':clinics,
        'audit':pd.DataFrame(audit),'history-coverage':coverage,'clinic-coverage':clinic_coverage,
        'unknown-reasons':unknown_reasons}

    # Preserve the published clinic label dtypes from the former adapter.
    for frame in outputs.values():
        for column in ['group','quality_reasons','unknown_reasons','eligibility','measure','reason','scope']:
            if column in frame:frame[column]=frame[column].astype('string')
    return outputs


def run(start,end,as_of,cached=False,print_sql=False):
    sql=render_sql(start,end,as_of)
    if print_sql:click.echo(sql);return
    period=f'{start}_{end}_as-of-{as_of}_order-line-clinic'
    directory=ROOT/'data'/NAME/period;parquet=directory/'source.parquet';manifest=directory/'source.json'
    expected=dict(start_date=start,end_date_exclusive=end,as_of_date=as_of,time_zone='UTC',
        sql_sha256=hashlib.sha256(sql.encode()).hexdigest(),clinic_source=CLINIC_SOURCE)
    if cached:
        meta=json.loads(manifest.read_text())
        if any(meta.get(k)!=v for k,v in expected.items()) or meta.get('parquet_sha256')!=digest(parquet):
            raise ValueError('cached SQL, dates or source fingerprint differs; refresh extract')
    else:
        directory.mkdir(parents=True,exist_ok=True)
        generated=ROOT/'src/autogenerated'/NAME/period;generated.mkdir(parents=True,exist_ok=True)
        query=generated/'aged_customer_prior_same_clinic_shipments.sql';write_text(query,sql+'\n')
        manifest.unlink(missing_ok=True)
        subprocess.run([sys.executable,str(RUNNER),str(query),'--output-parquet',str(parquet.relative_to(ROOT)),
            '--sql-log-dir',str((generated/'sql-history').relative_to(ROOT))],cwd=ROOT,check=True)
        meta=dict(expected,parquet_sha256=digest(parquet),extracted_at_utc=datetime.now(timezone.utc).isoformat())
    raw=pd.read_parquet(parquet);outputs=summarize(*unpack(raw),start,end,as_of)
    meta['warehouse']=raw.rename(columns=str.lower).extraction_warehouse.dropna().unique().tolist()
    baseline=ROOT/'data'/cohort.NAME/(f'{start}_{end}_as-of-{as_of}_all-handled-contacts_all-order-history_UTC')/'orders.parquet'
    if baseline.exists():
        old=set(pd.read_parquet(baseline).customer_id.dropna());current=set(outputs['customers'].customer_id)
        outputs['cohort-comparison']=pd.DataFrame([dict(previous_customers=len(old),current_customers=len(current),
            added_customers=len(current-old),removed_customers=len(old-current),baseline_sha256=digest(baseline))])
    write_text(manifest,json.dumps(meta,indent=2)+'\n')
    tables,prefix=table_layout(ROOT,NAME,period);tables.mkdir(parents=True,exist_ok=True)
    note=NOTE+f"Prescription dates {start} inclusive to {end} exclusive; as-of {as_of} 00:00 UTC. Extracted {meta['extracted_at_utc']}; source SHA-256 {meta['parquet_sha256']}.\n\n"
    files={}
    for kind,frame in outputs.items():
        full=directory/f'{kind}.parquet';frame.to_parquet(full,index=False)
        table=tables/f'{prefix}{kind}.md';write_text(table,f'# Prior same-clinic shipment experience: {kind}\n\n'+note+markdown_table(frame)+'\n')
        for p in [full,table]:files[str(p.relative_to(ROOT))]=digest(p)
    write_text(directory/'manifest.json',json.dumps(dict(source=meta,files=files),indent=2)+'\n')
    click.echo(outputs['summary'].to_string(index=False));click.echo(f'Tables: {tables}')


@click.command()
@click.option('--start-date',default='2026-08-15',show_default=True)
@click.option('--end-date',default='2026-10-15',show_default=True)
@click.option('--as-of-date',default='2026-10-27',show_default=True)
@click.option('--cached',is_flag=True)
@click.option('--print-sql',is_flag=True)
def main(start_date,end_date,as_of_date,cached,print_sql):
    try:run(start_date,end_date,as_of_date,cached,print_sql)
    except (ValueError,OSError,KeyError,subprocess.CalledProcessError) as error:
        raise click.ClickException(str(error)) from error


if __name__=='__main__':main()

"""REFNUM 38: prior shipped prescription experience before the full cohort's orders."""
from datetime import date,datetime,timezone
import hashlib
import json
import re
import subprocess
import sys

import click
from jinja2 import Environment,StrictUndefined
import pandas as pd

from src.python import create_aged_customer_prior_shipped_prescriptions as prior
from src.python.create_cmpu_prescription_first_order_status import ROOT,RUNNER,digest
from src.python.markdown_tables import markdown_table,table_layout,write_text
from src.python.prior_shipment_history import summarize_history,FLAGS

NAME='cmpu-customer-prior-shipped-prescriptions'
TEMPLATE=ROOT/'src/sql/cmpu_customer_prior_shipped_prescriptions.sql'
ASSOCIATIONS=['rx_id','rx_customer_id','approval_channel','first_order_id','first_orderitem_id',
    'first_order_line_id','rx_creation_datetime','rx_source_rows','order_id','order_line_id',
    'customer_id','customer_variants','order_placed_time','order_placed_eastern','placed_variants',
    'eastern_variants','shipment_rows']
NOTE=('All CMPU vet-diet customers in the selected prescription-creation window/channel, regardless of order status, '
    'cancellation reason or reordering. One observation per known prescription customer. '
    'Reference = earliest cohort first-order placement; every matched cohort ORDER_ID and all its lines are excluded '
    'from prior history. All prescription associations must have matched customer/order/placement information '
    'to establish the earliest reference. Customers with incomplete references are unknown, not no-history customers. '
    'History requires a populated UTC ORDER_LINE_SHIPPED_DTTM strictly BEFORE reference order placement, '
    'matching RX_ID and customer ID. Delivery/full-order completion are not required. '
    'Inclusive pharmacy = Pharmacy, Compound, Over the Counter or IS_VET_DIET_FLAG=TRUE; '
    'vet diet uses that flag; CMPU vet diet also requires PRESCRIPTION_SOURCE=CMPU. '
    'Historical channels, products, pets and prescription dates are unrestricted. '
    'The three history flags are nested and not additive. Percentages of assessable customers exclude unknown references; '
    'percentages of all cohort customers retain them. Dates of observed history do not establish source retention bounds. '
    'Missing RX/customer matches remain audited, outside qualifying evidence. Complete records are in data/ Parquet. ')


def render_sql(start,end,as_of,channel='ALL'):
    start,end,as_of=map(date.fromisoformat,[start,end,as_of])
    if not start<end<=as_of<=datetime.now(timezone.utc).date():
        raise ValueError('require start < exclusive end <= as-of <= current UTC date')
    if not re.fullmatch('[A-Z][A-Z0-9_]*',channel):
        raise ValueError('approval channel must be ALL or an uppercase channel code')
    return Environment(undefined=StrictUndefined).from_string(TEMPLATE.read_text()).render(
        start_date=start.isoformat(),end_date=end.isoformat(),as_of_date=as_of.isoformat(),approval_channel=channel)


def unpack(raw):
    raw=raw.rename(columns=str.lower)
    if not raw.record_type.isin(['association','shipment']).all():raise ValueError('unexpected source record type')
    def frame(kind,cols):
        return pd.DataFrame([{k.lower():v for k,v in json.loads(p).items()}
            for p in raw.loc[raw.record_type.eq(kind),'payload']],columns=cols)
    return frame('association',ASSOCIATIONS),frame('shipment',prior.HISTORY)


def summarize(a,h,start,end,as_of,channel='ALL'):
    render_sql(start,end,as_of,channel)
    a,h=a.copy(),h.copy()
    if a.rx_id.isna().any() or a.rx_id.duplicated().any() or not a.rx_source_rows.eq(1).all():
        raise ValueError('missing or duplicate cohort prescription IDs')
    a['rx_creation_datetime']=pd.to_datetime(a.rx_creation_datetime,utc=True,format='mixed')
    if not a.rx_creation_datetime.between(pd.Timestamp(start,tz='UTC'),pd.Timestamp(end,tz='UTC'),inclusive='left').all():
        raise ValueError('prescription outside cohort window')
    if channel!='ALL' and not a.approval_channel.eq(channel).all():raise ValueError('unexpected approval channel')
    numeric=a.first_orderitem_id.astype('string').str.strip().str.fullmatch('[0-9]+').fillna(False)
    for row,valid in zip(a.itertuples(),numeric):
        expected=int(str(row.first_orderitem_id).strip()) if valid else None
        if (expected is None)!=pd.isna(row.first_order_line_id) or (expected is not None and expected!=row.first_order_line_id):
            raise ValueError('numeric first-order line key disagrees')
    matched=a.order_id.notna()
    if matched.ne(a.order_line_id.notna()).any() or (matched & (
        a.order_id.ne(a.first_order_id)|a.order_line_id.ne(a.first_order_line_id))).any():
        raise ValueError('first-order association keys disagree')
    if (not a.loc[matched,'customer_variants'].eq(1).all() or a.loc[matched,'placed_variants'].gt(1).any()
            or a.loc[matched,'eastern_variants'].gt(1).any()):
        raise ValueError('conflicting cohort customer or placement timestamps')
    a['order_placed_time']=pd.to_datetime(a.order_placed_time,utc=True,format='mixed').astype('datetime64[ns, UTC]')
    a['order_placed_eastern']=pd.to_datetime(a.order_placed_eastern,format='mixed').astype('datetime64[ns]')
    paired=a.order_placed_time.notna() & a.order_placed_eastern.notna()
    expected_eastern=a.order_placed_time.dt.tz_convert('America/New_York').dt.tz_localize(None)
    if a.loc[paired,'order_placed_eastern'].ne(expected_eastern.loc[paired]).any():
        raise ValueError('UTC/Eastern order placement companions disagree')
    lines=a.loc[matched,['order_id','order_line_id','customer_id','order_placed_time']].drop_duplicates()
    if lines.duplicated(['order_id','order_line_id']).any() or lines.groupby('order_id')[
            ['customer_id','order_placed_time']].nunique(dropna=False).gt(1).any().any():
        raise ValueError('conflicting repeated order/line placement or customer values')
    a['association_state']='Matched'
    a.loc[~matched,'association_state']='Unmatched line'
    a.loc[a.first_order_id.isna(),'association_state']='Missing order ID'
    a.loc[a.first_order_id.notna() & a.first_orderitem_id.isna(),'association_state']='Missing line ID'
    a.loc[a.first_order_id.notna() & a.first_orderitem_id.notna() & ~numeric,'association_state']='Invalid line ID'
    a.loc[matched & a.order_placed_time.isna(),'association_state']='Missing placement'
    a.loc[matched & a.order_placed_time.gt(pd.Timestamp(as_of,tz='UTC')),'association_state']='Placement after as-of'
    a.loc[matched & (a.customer_id.isna()|a.rx_customer_id.isna()|a.customer_id.ne(a.rx_customer_id)),
          'association_state']='Cohort customer mismatch'
    known=a.loc[a.rx_customer_id.notna()]
    customers=known.groupby('rx_customer_id').agg(cohort_prescriptions=('rx_id','size'),
        reference_placed_time=('order_placed_time','min'),
        incomplete_references=('association_state',lambda s:int(s.ne('Matched').sum()))).reset_index().rename(columns={'rx_customer_id':'customer_id'})
    customers.loc[customers.incomplete_references.gt(0),'reference_placed_time']=pd.NaT
    customers['assessable']=customers.reference_placed_time.notna()
    h=prior_history_evidence(h,customers,a.first_order_id.dropna())
    evaluated=customers.loc[customers.assessable].copy()
    result=summarize_history(evaluated,h)
    known_flags=result['customers']
    customers=customers.merge(known_flags[['customer_id',*FLAGS,'history_group']],on='customer_id',how='left',validate='one_to_one')
    for flag in FLAGS:customers[flag]=customers[flag].astype('boolean')
    customers.loc[~customers.assessable,'history_group']='Unknown reference placement'
    result['summary']=result['summary'].rename(columns={'percent_of_customers':'percent_of_assessable_customers'})
    result['summary'].loc[result['summary'].measure.eq('Customers'),'measure']='Assessable customers'
    denom=len(customers)
    result['summary']['percent_of_all_cohort_customers']=100*result['summary'].customers/denom if denom else None
    result['summary']=pd.concat([pd.DataFrame([dict(measure='All cohort customers',customers=denom,
        percent_of_assessable_customers=None,percent_of_all_cohort_customers=100. if denom else None)]),
        result['summary']],ignore_index=True)
    result['exclusive-groups']=customers.groupby('history_group').size().rename('customers').reset_index()
    result['exclusive-groups']['percent_of_all_cohort_customers']=100*result['exclusive-groups'].customers/denom if denom else None
    result['customers']=customers
    result['orders']=lines.groupby(['order_id','customer_id','order_placed_time'],dropna=False).size().reset_index(name='matched_order_lines')
    result['associations']=a
    audit=[dict(measure='Association: '+str(k),count=int(v)) for k,v in a.association_state.value_counts().items()]
    audit += [dict(measure='History: '+str(k),count=int(v)) for k,v in h.eligibility.value_counts().items()]
    audit += [dict(measure='Customers without an assessable reference',count=int((~customers.assessable).sum())),
        dict(measure='Prescriptions missing customer ID',count=int(a.rx_customer_id.isna().sum())),
        dict(measure='Matched lines missing Eastern companion',count=int((matched & a.order_placed_eastern.isna()).sum())),
        dict(measure='Collapsed history shipment rows',count=int(h.shipment_rows.sum())-len(h))]
    result['audit']=pd.DataFrame(audit)
    result['history-coverage']=pd.DataFrame([dict(earliest_observed_candidate_shipment_utc=h.shipped_at_utc.min(),
        latest_observed_candidate_shipment_utc=h.shipped_at_utc.max())])
    assert result['exclusive-groups'].customers.sum()==denom
    return result


def prior_history_evidence(h,customers,cohort_orders):
    if h[['order_id','order_line_id']].isna().any().any() or h.duplicated(['order_id','order_line_id','rx_id']).any():
        raise ValueError('missing or duplicate history order/line/RX keys')
    if not h.customer_variants.eq(1).all() or h.rx_source_rows.isna().any() or not h.rx_source_rows.isin([0,1]).all():
        raise ValueError('conflicting historical customer or prescription identities')
    if h.groupby(['order_id','order_line_id']).shipment_customer_id.nunique(dropna=False).gt(1).any():
        raise ValueError('conflicting customers across historical prescription associations')
    h['shipped_at_utc']=pd.to_datetime(h.shipped_at_utc,utc=True,format='mixed').astype('datetime64[ns, UTC]')
    h=h.merge(customers[['customer_id','reference_placed_time']],left_on='shipment_customer_id',right_on='customer_id',how='left',validate='many_to_one')
    h['is_cohort_order']=h.order_id.isin(cohort_orders)
    h['eligibility']='Eligible'
    h.loc[h.is_cohort_order,'eligibility']='Analysed cohort order'
    h.loc[h.shipped_at_utc.ge(h.reference_placed_time),'eligibility']='At/after reference placement'
    h.loc[h.shipped_at_utc.isna(),'eligibility']='Missing shipment time'
    h.loc[h.rx_customer_id.isna()|h.rx_customer_id.ne(h.shipment_customer_id),'eligibility']='RX/customer mismatch'
    h.loc[h.rx_source_rows.eq(0),'eligibility']='Unmatched RX_ID'
    h.loc[h.rx_id.isna(),'eligibility']='Missing RX_ID'
    h.loc[h.reference_placed_time.isna(),'eligibility']='Unknown reference placement'
    assert not (h.eligibility.eq('Eligible') & h.is_cohort_order).any()
    return h


def run(start,end,as_of,channel='ALL',cached=False,print_sql=False):
    sql=render_sql(start,end,as_of,channel)
    if print_sql:click.echo(sql);return
    period=f'{start}_{end}_as-of-{as_of}_channel-{channel.lower()}'
    directory=ROOT/'data'/NAME/period
    parquet,manifest=directory/'source.parquet',directory/'source.json'
    expected=dict(start_date=start,end_date_exclusive=end,as_of_date=as_of,approval_channel=channel,
                  sql_sha256=hashlib.sha256(sql.encode()).hexdigest(),time_zone='UTC')
    if cached:
        meta=json.loads(manifest.read_text())
        if any(meta.get(k)!=v for k,v in expected.items()) or meta.get('parquet_sha256')!=digest(parquet):
            raise ValueError('cached SQL, dates, channel or source fingerprint differs; refresh extract')
    else:
        directory.mkdir(parents=True,exist_ok=True)
        generated=ROOT/'src/autogenerated'/NAME/period;generated.mkdir(parents=True,exist_ok=True)
        query=generated/'cmpu_customer_prior_shipped_prescriptions.sql';write_text(query,sql+'\n')
        manifest.unlink(missing_ok=True)
        subprocess.run([sys.executable,str(RUNNER),str(query),'--output-parquet',str(parquet.relative_to(ROOT)),
            '--sql-log-dir',str((generated/'sql-history').relative_to(ROOT))],cwd=ROOT,check=True)
        meta=dict(expected,parquet_sha256=digest(parquet),extracted_at_utc=datetime.now(timezone.utc).isoformat())
    raw=pd.read_parquet(parquet);outputs=summarize(*unpack(raw),start,end,as_of,channel)
    meta['warehouse']=raw.rename(columns=str.lower).extraction_warehouse.dropna().unique().tolist()
    write_text(manifest,json.dumps(meta,indent=2)+'\n')
    tables,prefix=table_layout(ROOT,NAME,period);tables.mkdir(parents=True,exist_ok=True)
    note=NOTE+f"Cohort {start} inclusive to {end} exclusive; channel {channel}; as-of {as_of} 00:00 UTC. Source {meta['parquet_sha256']}; extracted {meta['extracted_at_utc']}.\n\n"
    files={}
    for kind,frame in outputs.items():
        full=directory/f'{kind}.parquet';frame.to_parquet(full,index=False)
        table=tables/f'{prefix}{kind}.md';write_text(table,f'# Shipment history before cohort order placement: {kind}\n\n'+note+markdown_table(frame)+'\n')
        for p in [full,table]:files[str(p.relative_to(ROOT))]=digest(p)
    write_text(directory/'manifest.json',json.dumps(dict(source=meta,files=files),indent=2)+'\n')
    click.echo(outputs['summary'].to_string(index=False));click.echo(f'Tables: {tables}')


@click.command()
@click.option('--start-date',default='2026-08-15',show_default=True)
@click.option('--end-date',default='2026-10-15',show_default=True)
@click.option('--as-of-date',default='2026-10-27',show_default=True)
@click.option('--approval-channel',default='ALL',show_default=True)
@click.option('--cached',is_flag=True)
@click.option('--print-sql',is_flag=True)
def main(start_date,end_date,as_of_date,approval_channel,cached,print_sql):
    try:run(start_date,end_date,as_of_date,approval_channel,cached,print_sql)
    except (ValueError,OSError,KeyError,subprocess.CalledProcessError) as error:
        raise click.ClickException(str(error)) from error


if __name__=='__main__':main()

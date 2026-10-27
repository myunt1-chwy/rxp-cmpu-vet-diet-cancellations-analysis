"""REFNUM 23: separate mature customer populations for 7/14-day reorder windows."""
from datetime import date, datetime, timedelta, timezone
import hashlib
import json
import subprocess
import sys

import click
from jinja2 import Environment, StrictUndefined
import pandas as pd

from src.python import create_aged_order_same_product_reorders as prior
from src.python.create_cmpu_prescription_first_order_status import ROOT, RUNNER, digest
from src.python.markdown_tables import markdown_table, table_layout
from src.python.markdown_tables import write_text

NAME='aged-order-reorder-windows'
TEMPLATE=ROOT/'src/sql/aged_order_reorder_windows.sql'
PET_TEMPLATE=ROOT/'src/sql/aged_order_reorder_windows_same_pet.sql'
PET_21_TEMPLATE=ROOT/'src/sql/aged_order_reorder_windows_same_pet_21_days.sql'
HORIZONS=[7,14]


def render_sql(start,end,as_of,require_same_pet=False,include_21_days=False):
    if include_21_days and not require_same_pet:
        raise ValueError('21-day mode requires same-pet matching')
    start,end,as_of=map(date.fromisoformat,[start,end,as_of])
    if not start<end<=as_of or as_of>datetime.now(timezone.utc).date():
        raise ValueError('require start < exclusive end <= as-of <= current UTC date')
    return Environment(undefined=StrictUndefined).from_string((PET_21_TEMPLATE if include_21_days else PET_TEMPLATE if require_same_pet else TEMPLATE).read_text()).render(
        start_date=start.isoformat(),end_date=end.isoformat(),as_of_date=as_of.isoformat())


def summarize(raw,start,end,as_of,require_same_pet=False,include_21_days=False):
    render_sql(start,end,as_of,require_same_pet,include_21_days)
    horizons=HORIZONS+([21] if include_21_days else [])
    frame=raw.rename(columns=str.lower).copy()
    if frame.followup_days.isna().any() or not frame.followup_days.isin(horizons).all():
        raise ValueError('unexpected follow-up window')
    if len(frame) and set(frame.followup_days)!=set(horizons):
        raise ValueError('missing follow-up population')
    results={kind:[] for kind in ['associations','cancellation-details','reorder-matches','customers','summary','audit']}
    for days in horizons:
        subset=frame.loc[frame.followup_days.eq(days)].copy()
        cancel=pd.to_datetime(subset.order_cancel_time,utc=True,format='mixed').astype('datetime64[ns, UTC]')
        expected_end=cancel+pd.Timedelta(days=days)
        actual_end=pd.to_datetime(subset.window_end_utc,utc=True,format='mixed').astype('datetime64[ns, UTC]')
        if not (expected_end.eq(actual_end)|(expected_end.isna()&actual_end.isna())).all():
            raise ValueError('SQL follow-up end differs from cancellation + horizon')
        complete=expected_end.notna()&expected_end.le(pd.Timestamp(as_of,tz='UTC'))
        if subset.followup_complete.isna().any() or not subset.followup_complete.eq(complete).all():
            raise ValueError('SQL follow-up maturity flag disagrees')
        associations,originals,matches,_,audit=prior.summarize(subset,start,end,as_of,followup_days=days,require_same_pet=require_same_pet)
        if require_same_pet:
            for col in ['candidate_reorder_lines','candidate_missing_pet_lines','candidate_ambiguous_pet_lines']:
                if subset[col].isna().any() or subset[col].nunique()>1:
                    raise ValueError('inconsistent candidate pet audit')
                audit.loc[len(audit)] = [f'All-horizon {col}',int(subset[col].iloc[0]) if len(subset) else 0]
        if len(matches) and not matches.eligibility.eq('Eligible').all():
            raise ValueError('immature or excluded cancellation contributed reorder evidence')
        eligible=originals.loc[originals.eligibility.eq('Eligible')]
        customers=eligible.groupby('original_customer_id').agg(
            eligible_cancellation_lines=('original_line_id','size'),
            eligible_canceled_orders=('original_order_id','nunique'),
            canceled_products=('original_product_id','nunique'),has_reordered=('has_reorder','any')).reset_index()
        summary=pd.DataFrame([dict(followup_days=days,
            latest_eligible_cancellation_utc=pd.Timestamp(as_of,tz='UTC')-pd.Timedelta(days=days),
            eligible_customers=len(customers),reordered_customers=int(customers.has_reordered.sum()),
            reorder_percent=100*customers.has_reordered.sum()/len(customers) if len(customers) else None)])
        for kind,data in [('associations',associations),('cancellation-details',originals),
                          ('reorder-matches',matches),('customers',customers),('audit',audit)]:
            results[kind].append(data.assign(followup_days=days))
        results['summary'].append(summary)
    outputs={kind:pd.concat(parts,ignore_index=True) for kind,parts in results.items()}
    a=outputs['associations']
    for days in horizons[1:]:
        if set(a.loc[a.followup_days.eq(7),'rx_id'])!=set(a.loc[a.followup_days.eq(days),'rx_id']):
            raise ValueError('prescription cohorts differ between horizons')
    original=outputs['cancellation-details']
    if original.groupby(prior.KEYS)[prior.ORIGINAL_COLUMNS+(['original_pet_id','original_pet_variants'] if require_same_pet else [])].nunique(dropna=False).gt(1).any().any():
        raise ValueError('original line source evidence differs between horizons')
    customers=outputs['customers']
    for shorter,longer in zip(horizons,horizons[1:]):
        small=set(customers.loc[customers.followup_days.eq(longer),'original_customer_id'])
        if not small<=set(customers.loc[customers.followup_days.eq(shorter),'original_customer_id']):
            raise ValueError(f'{longer}-day population is not a subset of {shorter}-day population')
        mature_keys=original.loc[original.followup_days.eq(longer)&original.eligibility.eq('Eligible'),prior.KEYS]
        shorter_matches=outputs['reorder-matches'].loc[outputs['reorder-matches'].followup_days.eq(shorter)]
        common=shorter_matches.merge(mature_keys,on=prior.KEYS,how='inner')
        reordered=set(customers.loc[customers.followup_days.eq(longer)&customers.has_reordered,'original_customer_id'])
        if not set(common.original_customer_id)<=reordered:
            raise ValueError(f'{longer}-day outcomes lost {shorter}-day evidence in the common mature population')
    return outputs


def load_source(start,end,as_of,cached,require_same_pet=False,include_21_days=False):
    sql=render_sql(start,end,as_of,require_same_pet,include_21_days)
    period=f'{start}_{end}_customer_upload_reorders-7d-14d_as-of-{as_of}'
    if include_21_days:period=period.replace('reorders-7d-14d_', 'reorders-7d-14d-21d_')
    if require_same_pet:period=period.replace('_customer_upload_', '_customer_upload_same-pet_')
    directory=ROOT/'data'/NAME/period;parquet=directory/'source.parquet';manifest=directory/'source.json'
    options=dict(start_date=start,end_date_exclusive=end,as_of_date=as_of,followup_days=HORIZONS+([21] if include_21_days else []))
    if require_same_pet:options['match_pet']=True
    if include_21_days:options['include_21_days']=True
    if cached:
        metadata=json.loads(manifest.read_text())
        if (metadata.get('sql')!=sql or metadata.get('sql_sha256')!=hashlib.sha256(sql.encode()).hexdigest()
                or metadata.get('parquet_sha256')!=digest(parquet)
                or any(metadata.get(k)!=v for k,v in options.items())):
            raise ValueError('cached SQL, dates, horizons or fingerprint differs; refresh extract')
        raw=pd.read_parquet(parquet)
    else:
        directory.mkdir(parents=True,exist_ok=True)
        generated=ROOT/'src/autogenerated'/NAME/period;generated.mkdir(parents=True,exist_ok=True)
        query=generated/'aged_order_reorder_windows.sql';write_text(query, sql+'\n');manifest.unlink(missing_ok=True)
        subprocess.run([sys.executable,str(RUNNER),str(query),'--output-parquet',str(parquet.relative_to(ROOT)),
                        '--sql-log-dir',str((generated/'sql-history').relative_to(ROOT))],cwd=ROOT,check=True)
        raw=pd.read_parquet(parquet).rename(columns=str.lower)
        summarize(raw,start,end,as_of,require_same_pet,include_21_days)
        metadata=dict(options,sql=sql,sql_sha256=hashlib.sha256(sql.encode()).hexdigest(),parquet_sha256=digest(parquet),
            extracted_at_utc=datetime.now(timezone.utc).isoformat(),warehouse=raw.extraction_warehouse.unique().tolist(),
            source_extracted_at=raw.extracted_at_session_time.unique().tolist())
        write_text(manifest, json.dumps(metadata,indent=2)+'\n')
    return raw,metadata,period


def write_outputs(raw,metadata,period):
    outputs=summarize(raw,metadata['start_date'],metadata['end_date_exclusive'],metadata['as_of_date'],metadata.get('match_pet',False),metadata.get('include_21_days',False))
    tables,prefix=table_layout(ROOT,NAME,period);tables.mkdir(parents=True,exist_ok=True)
    directory=ROOT/'data'/NAME/period;directory.mkdir(parents=True,exist_ok=True)
    note=(f"CMPU vet-diet CUSTOMER_UPLOAD prescriptions UTC [{metadata['start_date']}, {metadata['end_date_exclusive']}); "
        f"as-of {metadata['as_of_date']} 00:00 UTC. All selected horizons extracted in one source snapshot.\n\n" +
        ('Matching requires known, unambiguous PET_ID equality as well as CUSTOMER_ID and PRODUCT_ID. Missing/ambiguous original pet identities are excluded from rate populations and audited. '
         if metadata.get('match_pet') else '') +
        'Separate complete-follow-up populations: a cancellation qualifies for horizon H only when cancellation + H days '
        'is at or before as-of, with usable customer/product keys and recorded Aged Order reason. '
        'Customers enter a horizon population if they have at least one qualifying cancellation. A customer reorders '
        'if a different order for the exact same PRODUCT_ID is placed strictly after an eligible cancellation and '
        'at or before cancellation + H days (24-hour periods). Each customer counts once per horizon. Every horizon is cumulative; '
        'placed attempts count regardless of later status or shipment. Reorders from immature cancellations cannot '
        'contribute to either numerator. No channel/source restriction on reordered lines. '
        'First-order joins use both keys; shipment rows/prescription associations are deduplicated. PRODUCT_ID maps '
        'through the latest PDM.PRODUCT part-number snapshot; conflicts stop validation. Current statuses and source '
        'associations are extraction-time snapshots. UTC/Eastern timestamp conventions follow REFNUM 22. '
        'The populations differ, so raw reordered-customer counts need not increase with the horizon.\n\n'
        f"Source SHA-256 {metadata['parquet_sha256']}; extracted {metadata['extracted_at_utc']}.\n\n")
    hashes={}
    for kind,data in outputs.items():
        write_text(tables/f'{prefix}{kind}.md', f'# Reorder customers by follow-up window: {kind}\n\n'+note+markdown_table(data)+'\n')
        path=directory/f'{kind}.parquet';data.to_parquet(path,index=False);hashes[path.name]=digest(path)
    write_text(directory/'exports.json', json.dumps(dict(source_sha256=metadata['parquet_sha256'],files=hashes),indent=2)+'\n')
    return outputs['summary'],tables


@click.command()
@click.option('--start-date',default='2026-08-15',show_default=True)
@click.option('--end-date',default='2026-10-15',show_default=True)
@click.option('--as-of-date',default='2026-10-27',show_default=True)
@click.option('--cached',is_flag=True)
@click.option('--print-sql',is_flag=True)
@click.option('--include-21-days',is_flag=True,help='Include the separately matured 21-day population; requires --same-pet.')
@click.option('--same-pet',is_flag=True,help='Require the same known PET_ID; uses a separate cache/output variant.')
def main(start_date,end_date,as_of_date,cached,print_sql,same_pet,include_21_days):
    try:
        if print_sql:click.echo(render_sql(start_date,end_date,as_of_date,same_pet,include_21_days));return
        raw,metadata,period=load_source(start_date,end_date,as_of_date,cached,same_pet,include_21_days)
        summary,tables=write_outputs(raw,metadata,period)
        click.echo(summary.to_string(index=False));click.echo(f'Tables: {tables}')
    except (ValueError,OSError,KeyError,subprocess.CalledProcessError) as error:
        raise click.ClickException(str(error)) from error


if __name__=='__main__':main()

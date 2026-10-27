"""Entity-upload evidence for different prescriptions used on REFNUM 22 reorders."""
from datetime import date, datetime, timezone
import hashlib
import json
import subprocess
import sys

import click
from jinja2 import Environment, StrictUndefined
import pandas as pd

from src.python import create_aged_order_same_product_reorders as reorders
from src.python import create_aged_order_reorder_prescriptions as prescriptions
from src.python import create_aged_order_reorder_approval_channels as channels
from src.python.create_cmpu_prescription_first_order_status import ROOT, RUNNER, digest
from src.python.markdown_tables import markdown_table, table_layout
from src.python.markdown_tables import write_text

NAME='aged-order-reorder-uploads'
TEMPLATE=ROOT/'src/sql/aged_order_reorder_uploads.sql'
KEYS=['rx_id','customer_id']


def requests_for(pairs,channel_source):
    selected=pairs.loc[pairs.prescription_comparison.eq('Different prescription')].copy()
    requests=selected[['reorder_rx_ids','original_customer_id']].drop_duplicates().set_axis(KEYS,axis=1)
    if requests.rx_id.duplicated().any():
        raise ValueError('one prescription associated with different customers')
    lookup=channel_source.rename(columns=str.lower)
    if lookup.rx_id.duplicated().any():raise ValueError('duplicate approval-channel records')
    lookup=lookup[['rx_id','approval_channel']].copy()
    lookup['channel']=lookup.approval_channel.astype('string').str.strip().replace('',pd.NA).fillna('[Missing approval channel]')
    requests=requests.merge(lookup,on='rx_id',how='left',validate='one_to_one')
    if requests.channel.isna().any():raise ValueError('missing frozen approval-channel evidence')
    return selected,requests


def render_sql(requests,as_of):
    date.fromisoformat(as_of)
    if requests.empty:raise ValueError('no different prescriptions to check')
    records=[]
    for row in requests.sort_values(KEYS).itertuples():
        if pd.isna(row.customer_id) or row.customer_id!=int(row.customer_id):raise ValueError('invalid customer key')
        if not isinstance(row.rx_id,str) or not row.rx_id.strip():raise ValueError('invalid prescription key')
        records.append([row.rx_id,int(row.customer_id)])
    return Environment(undefined=StrictUndefined).from_string(TEMPLATE.read_text()).render(
        requested_json=json.dumps(records,separators=(',',':')).replace("'","''"),as_of_date=as_of)


def summarize(pairs,requests,raw,as_of):
    source=raw.rename(columns=str.lower).copy()
    for col in ['rx_created_at_utc','uploaded_at_utc']:
        source[col]=pd.to_datetime(source[col],utc=True,format='mixed').astype('datetime64[ns, UTC]')
    expected={(r.rx_id,int(r.customer_id)) for r in requests.itertuples()}
    actual={(r.rx_id,int(r.customer_id)) for r in source.itertuples()}
    if expected!=actual:raise ValueError('upload extract keys differ from frozen prescriptions')
    if (not source.prescription_rows.eq(1).all() or source.rx_customer_id.isna().any()
            or source.rx_customer_id.ne(source.customer_id).any()):raise ValueError('prescription/customer source disagreement')
    for col in ['invalid_related_upload_rows','invalid_related_customer_rows','other_customer_uploads']:
        if source.groupby(KEYS)[col].nunique(dropna=False).gt(1).any() or source[col].isna().any():
            raise ValueError('inconsistent related upload audit')
    if source.invalid_related_upload_rows.gt(0).any():raise ValueError('missing or duplicate related upload IDs')
    matched=source.upload_id.notna()
    if source.loc[matched].duplicated(KEYS+['upload_id']).any():raise ValueError('duplicate RX/upload association')
    if (source.loc[matched,'upload_customer_id'].ne(source.loc[matched,'customer_id']).any()
            or source.loc[matched,'upload_customer_id'].isna().any()
            or not source.loc[matched,'upload_source_rows'].eq(1).all()):raise ValueError('invalid matched upload evidence')
    if source.uploaded_at_utc.dropna().gt(pd.Timestamp(as_of,tz='UTC')).any():raise ValueError('upload after as-of cutoff')
    source['recorded_file']=source.uploaded_file_flag.astype('string').str.strip().str.lower().map({'true':True,'false':False,'1':True,'0':False}).astype('boolean')
    rows=[]
    for key,group in source.groupby(KEYS):
        uploads=group.loc[group.upload_id.notna()]
        dated=uploads.loc[uploads.uploaded_at_utc.notna()]
        rows.append(dict(rx_id=key[0],customer_id=key[1],matching_uploads=len(uploads),dated_uploads=len(dated),
            undated_uploads=int(uploads.uploaded_at_utc.isna().sum()),
            recorded_file_uploads=int(dated.recorded_file.fillna(False).sum()),
            first_upload_at_utc=dated.uploaded_at_utc.min(),last_upload_at_utc=dated.uploaded_at_utc.max(),
            rx_created_at_utc=group.rx_created_at_utc.iloc[0],
            upload_state='Matching upload by as-of' if len(dated) else 'Undated upload only' if len(uploads) else 'No matching upload',
            invalid_related_customer_rows=int(group.invalid_related_customer_rows.iloc[0]),
            other_customer_uploads=int(group.other_customer_uploads.iloc[0])))
    rx=requests.merge(pd.DataFrame(rows),on=KEYS,how='left',validate='one_to_one')
    rx['has_recorded_file_upload']=rx.recorded_file_uploads.gt(0)
    details=pairs.merge(rx,left_on=['reorder_rx_ids','original_customer_id'],right_on=KEYS,how='left',validate='many_to_one')
    details['order_cancel_time']=pd.to_datetime(details.order_cancel_time,utc=True,format='mixed')
    groups={key:group.loc[group.upload_id.notna()] for key,group in source.groupby(KEYS)}
    details['uploads_after_cancellation']=[int(groups[(r.rx_id,r.customer_id)].uploaded_at_utc.gt(r.order_cancel_time).sum()) for r in details.itertuples()]
    details['uploads_before_or_at_cancellation']=[int(groups[(r.rx_id,r.customer_id)].uploaded_at_utc.le(r.order_cancel_time).sum()) for r in details.itertuples()]
    summaries=[]
    for population,subset in [('All different reorder prescriptions',rx),('Different reorder prescriptions with shipped orders',
            rx.loc[rx.rx_id.isin(details.loc[details.shipped_by_as_of,'rx_id'])])]:
        for channel,group in [('All channels',subset),*list(subset.groupby('channel'))]:
            for state in ['Matching upload by as-of','Undated upload only','No matching upload']:
                count=int(group.upload_state.eq(state).sum())
                summaries.append(dict(population=population,channel=channel,measure=state,count=count,
                    denominator=len(group),percent=100*count/len(group) if len(group) else None))
            count=int(group.has_recorded_file_upload.sum())
            summaries.append(dict(population=population,channel=channel,measure='Dated entity with HAS_UPLOADED_FILE=true',count=count,
                denominator=len(group),percent=100*count/len(group) if len(group) else None))
    summary=pd.DataFrame(summaries)
    audit=pd.DataFrame([
        ('Different reorder prescriptions',len(rx)),('Customers with different-prescription reorders',details.original_customer_id.nunique()),
        ('Cancellation/reorder line pairs',len(details)),('Matched distinct upload entities',source.upload_id.nunique()),
        ('Matched RX/upload associations',int(matched.sum())),('Undated matched upload associations',int((matched & source.uploaded_at_utc.isna()).sum())),
        ('Matched upload associations with unknown file flag',int((matched & source.recorded_file.isna()).sum())),
        ('Prescriptions missing creation timestamp',int(rx.rx_created_at_utc.isna().sum())),
        ('Related uploads with invalid/missing customer',int(rx.invalid_related_customer_rows.sum())),
        ('Related other-customer upload associations',int(rx.other_customer_uploads.sum())),
        ('Line pairs with uploads after cancellation',int(details.uploads_after_cancellation.gt(0).sum())),
        ('Line pairs with uploads before/at cancellation',int(details.uploads_before_or_at_cancellation.gt(0).sum()))
    ],columns=['measure','count'])
    states=summary.loc[summary.measure.ne('Dated entity with HAS_UPLOADED_FILE=true')]
    if not states.groupby(['population','channel'])['count'].sum().eq(states.groupby(['population','channel']).denominator.first()).all():
        raise ValueError('upload presence counts do not reconcile')
    return rx,details,source,summary,audit


def load_source(requests,period,dependencies,as_of,cached):
    sql=render_sql(requests,as_of)
    directory=ROOT/'data'/NAME/period;parquet=directory/'source.parquet';manifest=directory/'source.json'
    if cached:
        meta=json.loads(manifest.read_text())
        if (meta.get('sql')!=sql or meta.get('sql_sha256')!=hashlib.sha256(sql.encode()).hexdigest()
                or meta.get('dependencies')!=dependencies or meta.get('parquet_sha256')!=digest(parquet)):
            raise ValueError('cached SQL, frozen inputs or fingerprint differs; refresh uploads')
        raw=pd.read_parquet(parquet)
    else:
        directory.mkdir(parents=True,exist_ok=True)
        generated=ROOT/'src/autogenerated'/NAME/period;generated.mkdir(parents=True,exist_ok=True)
        query=generated/'aged_order_reorder_uploads.sql';write_text(query, sql+'\n');manifest.unlink(missing_ok=True)
        subprocess.run([sys.executable,str(RUNNER),str(query),'--output-parquet',str(parquet.relative_to(ROOT)),
                        '--sql-log-dir',str((generated/'sql-history').relative_to(ROOT))],cwd=ROOT,check=True)
        raw=pd.read_parquet(parquet).rename(columns=str.lower)
        meta=dict(sql=sql,sql_sha256=hashlib.sha256(sql.encode()).hexdigest(),dependencies=dependencies,
            parquet_sha256=digest(parquet),extracted_at_utc=datetime.now(timezone.utc).isoformat(),
            warehouse=raw.extraction_warehouse.unique().tolist())
    return raw,meta,manifest


@click.command()
@click.option('--start-date',default='2026-08-15',show_default=True)
@click.option('--end-date',default='2026-10-15',show_default=True)
@click.option('--as-of-date',default='2026-10-27',show_default=True)
@click.option('--cached',is_flag=True)
@click.option('--print-sql',is_flag=True)
def main(start_date,end_date,as_of_date,cached,print_sql):
    try:
        base,bmeta,period=reorders.load_source(start_date,end_date,as_of_date,'CUSTOMER_UPLOAD',True)
        associations,_,matches,_,_=reorders.summarize(base,start_date,end_date,as_of_date)
        matches=matches.loc[matches.eligibility.eq('Eligible')].copy()
        evidence,rmeta,_=prescriptions.load_source(prescriptions.requested_keys(matches),period,bmeta['parquet_sha256'],True)
        pairs,*_=prescriptions.summarize(matches,associations,evidence)
        lines=channels.line_prescriptions(matches,evidence)
        channel_source,cmeta,_=channels.load_source(lines.rx_id.dropna().unique().tolist(),period,rmeta['parquet_sha256'],True)
        channels.summarize(lines,channel_source)
        selected,requests=requests_for(pairs,channel_source)
        if print_sql:click.echo(render_sql(requests,as_of_date));return
        deps=dict(baseline=bmeta['parquet_sha256'],prescriptions=rmeta['parquet_sha256'],channels=cmeta['parquet_sha256'])
        raw,meta,manifest=load_source(requests,period,deps,as_of_date,cached)
        outputs=summarize(selected,requests,raw,as_of_date)
        meta.update(start_date=start_date,end_date_exclusive=end_date,as_of_date=as_of_date)
        write_text(manifest, json.dumps(meta,indent=2)+'\n')
        tables,prefix=table_layout(ROOT,NAME,period);tables.mkdir(parents=True,exist_ok=True)
        note=(f'Frozen REFNUM 22 different-prescription seven-day reorders; original CMPU vet-diet CUSTOMER_UPLOAD '
            f'prescriptions created [{start_date}, {end_date}) UTC. Different RX_ID does not necessarily mean newly created. '
            f'DIET_PRESCRIPTION upload entities searched across all history through {as_of_date} 00:00 UTC inclusive; '
            'undated matching records are retained separately. Match expanded RX_ID and numeric CUSTOMER_ID; '
            'deduplicate repeated RX tokens and upload IDs. Same-prescription reuse is excluded. '
            'Matching entity presence and HAS_UPLOADED_FILE=true are separate measures; a matching entity alone '
            'does not prove a file was uploaded. Entity links and file flags are lookup-time state; '
            'the as-of cutoff filters entity creation time, not historical attachment/link changes. '
            'No uploaded-file, association, deletion or order-ID filter is applied. '
            'Upload presence does not require creation after cancellation; line-pair details report uploads before/at '
            'and after cancellation separately. Approval channel is the previously frozen lookup, without filtering '
            'to CUSTOMER_UPLOAD. Shipped means the existing by-as-of shipment evidence.\n\n'
            f"Source SHA-256 {meta['parquet_sha256']}; extracted {meta['extracted_at_utc']}.\n\n")
        hashes={}
        for kind,data in zip(['prescriptions','line-pairs','upload-associations','summary','audit'],outputs):
            write_text(tables/f'{prefix}{kind}.md', f'# Different reorder prescription uploads: {kind}\n\n'+note+markdown_table(data)+'\n')
            path=manifest.parent/f'{kind}.parquet';data.to_parquet(path,index=False);hashes[path.name]=digest(path)
        write_text(manifest.parent/'exports.json', json.dumps(dict(dependencies=deps,source_sha256=meta['parquet_sha256'],files=hashes),indent=2)+'\n')
        click.echo(outputs[3].to_string(index=False));click.echo(outputs[4].to_string(index=False));click.echo(f'Tables: {tables}')
    except (ValueError,OSError,KeyError,subprocess.CalledProcessError) as error:
        raise click.ClickException(str(error)) from error


if __name__=='__main__':main()

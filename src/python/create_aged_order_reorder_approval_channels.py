"""Approval channels of prescriptions on frozen REFNUM 22 reordered lines."""
from datetime import datetime, timezone
import hashlib
import json
import subprocess
import sys

import click
from jinja2 import Environment, StrictUndefined
import pandas as pd

from src.python import create_aged_order_same_product_reorders as reorders
from src.python import create_aged_order_reorder_prescriptions as prescriptions
from src.python.create_cmpu_prescription_first_order_status import ROOT, RUNNER, digest
from src.python.markdown_tables import markdown_table, table_layout
from src.python.markdown_tables import write_text

NAME='aged-order-reorder-approval-channels'
TEMPLATE=ROOT/'src/sql/aged_order_reorder_approval_channels.sql'
LINE_KEYS=['reorder_order_id','reorder_line_id']


def line_prescriptions(matches,source):
    rows=source.rename(columns=str.lower).rename(columns={'order_id':'reorder_order_id','order_line_id':'reorder_line_id'})
    columns=LINE_KEYS+['original_customer_id','shipped_by_as_of']
    lines=matches[columns].drop_duplicates()
    if lines.duplicated(LINE_KEYS).any():
        raise ValueError('conflicting frozen reorder line metadata')
    return lines.merge(rows[LINE_KEYS+['rx_id']].drop_duplicates(),on=LINE_KEYS,how='left',validate='one_to_many')


def render_sql(rx_ids):
    ids=sorted(set(rx_ids))
    if not ids or any(not isinstance(value,str) or not value.strip() for value in ids):
        raise ValueError('require populated prescription IDs')
    literal=json.dumps(ids,separators=(',',':')).replace("'","''")
    return Environment(undefined=StrictUndefined).from_string(TEMPLATE.read_text()).render(rx_ids_json=literal)


def summarize(lines,source):
    source=source.rename(columns=str.lower).copy()
    expected=set(lines.rx_id.dropna())
    if source.rx_id.isna().any() or set(source.rx_id)!=expected:
        raise ValueError('approval-channel keys do not match frozen prescription IDs')
    if (source.rx_id.duplicated().any() or not source.prescription_rows.isin([0,1]).all()
            or source.prescription_rows.eq(1).ne(source.matched_rx_id.notna()).any()
            or (source.matched_rx_id.notna() & source.rx_id.ne(source.matched_rx_id)).any()):
        raise ValueError('duplicate or inconsistent prescription source records')
    source['channel']=source.approval_channel.astype('string').str.strip().replace('',pd.NA).fillna('[Missing approval channel]')
    source.loc[source.prescription_rows.eq(0),'channel']='[Unmatched prescription]'
    details=lines.merge(source[['rx_id','approval_channel','channel','prescription_rows']],on='rx_id',how='left',validate='many_to_one')
    details.loc[details.rx_id.isna(),'channel']='[Missing prescription ID]'
    rows=[]
    for population,subset in [('All reorder attempts',details),('Shipped reorders',details.loc[details.shipped_by_as_of])]:
        for grain,keys in [('Reorder prescriptions',['rx_id']),('Reordered lines',LINE_KEYS),
                           ('Customers by channel combination',['original_customer_id'])]:
            selected=subset.loc[subset.rx_id.notna()] if grain=='Reorder prescriptions' else subset
            groups=selected.groupby(keys,dropna=False).channel.agg(lambda s:' + '.join(sorted(set(s))))
            for channel,count in groups.value_counts().items():
                rows.append(dict(population=population,grain=grain,channel=channel,count=int(count),
                                 denominator=len(groups),percent=100*count/len(groups),mutually_exclusive=True))
        denominator=subset.original_customer_id.nunique()
        for channel,group in subset.groupby('channel'):
            count=group.original_customer_id.nunique()
            rows.append(dict(population=population,grain='Customers with channel',channel=channel,count=count,
                             denominator=denominator,percent=100*count/denominator,mutually_exclusive=False))
    summary=pd.DataFrame(rows,columns=['population','grain','channel','count','denominator','percent','mutually_exclusive'])
    exclusive=summary.loc[summary.mutually_exclusive]
    if not exclusive.groupby(['population','grain'])['count'].sum().eq(exclusive.groupby(['population','grain']).denominator.first()).all():
        raise ValueError('approval-channel counts do not reconcile')
    audit=pd.DataFrame([
        ('Frozen distinct reordered lines',len(lines[LINE_KEYS].drop_duplicates())),
        ('Frozen reorder customers',lines.original_customer_id.nunique()),
        ('Requested distinct reorder prescriptions',len(expected)),
        ('Unmatched prescriptions',int(source.prescription_rows.eq(0).sum())),
        ('Prescriptions missing approval channel',int(source.channel.eq('[Missing approval channel]').sum())),
        ('Reordered lines missing prescription IDs',len(details.loc[details.rx_id.isna(),LINE_KEYS].drop_duplicates())),
        ('Customers using multiple channels',int(details.groupby('original_customer_id').channel.nunique().gt(1).sum()))
    ],columns=['measure','count'])
    return details,source,summary,audit


def load_source(rx_ids,period,frozen_sha,cached):
    sql=render_sql(rx_ids)
    directory=ROOT/'data'/NAME/period;parquet=directory/'source.parquet';manifest=directory/'source.json'
    if cached:
        metadata=json.loads(manifest.read_text())
        if (metadata.get('sql')!=sql or metadata.get('sql_sha256')!=hashlib.sha256(sql.encode()).hexdigest()
                or metadata.get('frozen_prescriptions_sha256')!=frozen_sha
                or metadata.get('parquet_sha256')!=digest(parquet)):
            raise ValueError('cached SQL, frozen prescriptions or fingerprint differs; refresh lookup')
        frame=pd.read_parquet(parquet)
    else:
        directory.mkdir(parents=True,exist_ok=True)
        generated=ROOT/'src/autogenerated'/NAME/period;generated.mkdir(parents=True,exist_ok=True)
        query=generated/'aged_order_reorder_approval_channels.sql';write_text(query, sql+'\n')
        manifest.unlink(missing_ok=True)
        subprocess.run([sys.executable,str(RUNNER),str(query),'--output-parquet',str(parquet.relative_to(ROOT)),
                        '--sql-log-dir',str((generated/'sql-history').relative_to(ROOT))],cwd=ROOT,check=True)
        frame=pd.read_parquet(parquet).rename(columns=str.lower)
        metadata=dict(sql=sql,sql_sha256=hashlib.sha256(sql.encode()).hexdigest(),
            frozen_prescriptions_sha256=frozen_sha,parquet_sha256=digest(parquet),
            extracted_at_utc=datetime.now(timezone.utc).isoformat(),warehouse=frame.extraction_warehouse.unique().tolist())
    return frame,metadata,manifest


@click.command()
@click.option('--start-date',default='2026-08-15',show_default=True)
@click.option('--end-date',default='2026-10-15',show_default=True)
@click.option('--as-of-date',default='2026-10-27',show_default=True)
@click.option('--cached',is_flag=True)
@click.option('--print-sql',is_flag=True)
def main(start_date,end_date,as_of_date,cached,print_sql):
    try:
        baseline,base_meta,period=reorders.load_source(start_date,end_date,as_of_date,'CUSTOMER_UPLOAD',True)
        associations,_,matches,_,_=reorders.summarize(baseline,start_date,end_date,as_of_date)
        matches=matches.loc[matches.eligibility.eq('Eligible')].copy()
        evidence,rx_meta,_=prescriptions.load_source(prescriptions.requested_keys(matches),period,base_meta['parquet_sha256'],True)
        prescriptions.summarize(matches,associations,evidence)
        lines=line_prescriptions(matches,evidence)
        ids=lines.rx_id.dropna().unique().tolist()
        if print_sql:
            click.echo(render_sql(ids));return
        source,metadata,manifest=load_source(ids,period,rx_meta['parquet_sha256'],cached)
        outputs=summarize(lines,source)
        metadata.update(baseline_sha256=base_meta['parquet_sha256'],start_date=start_date,end_date_exclusive=end_date,as_of_date=as_of_date)
        write_text(manifest, json.dumps(metadata,indent=2)+'\n')
        tables,prefix=table_layout(ROOT,NAME,period);tables.mkdir(parents=True,exist_ok=True)
        note=(f'Frozen REFNUM 22 eligible seven-day reorders, as-of {as_of_date} 00:00 UTC; original CMPU vet-diet '
            f'CUSTOMER_UPLOAD prescriptions created [{start_date}, {end_date}) UTC. No channel filter on reordered prescriptions.\n\n'
            'Approval channel comes from RXP_PRESCRIPTIONS matched to the RX_ID on each frozen reordered line. '
            'Channels are current lookup-time values, not guaranteed historical channel at order placement. '
            'Prescription counts deduplicate RX_ID; order-line counts deduplicate order/line pairs. Customer channel '
            'combinations are mutually exclusive; Customers with channel counts can overlap when a customer used several '
            'channels. Missing prescription IDs, unmatched prescriptions and missing channels are explicit. '
            'Shipped means shipment evidence by the original as-of cutoff, not proof of delivery/full quantity.\n\n'
            f"Frozen prescription evidence SHA-256 {metadata['frozen_prescriptions_sha256']}; channel extract SHA-256 "
            f"{metadata['parquet_sha256']}; extracted {metadata['extracted_at_utc']}.\n\n")
        hashes={}
        for kind,data in zip(['line-details','prescriptions','summary','audit'],outputs):
            write_text(tables/f'{prefix}{kind}.md', f'# Reorder prescription approval channels: {kind}\n\n'+note+markdown_table(data)+'\n')
            path=manifest.parent/f'{kind}.parquet';data.to_parquet(path,index=False);hashes[path.name]=digest(path)
        write_text(manifest.parent/'exports.json', json.dumps(dict(source_sha256=metadata['parquet_sha256'],files=hashes),indent=2)+'\n')
        click.echo(outputs[2].to_string(index=False));click.echo(outputs[3].to_string(index=False));click.echo(f'Tables: {tables}')
    except (ValueError,OSError,KeyError,subprocess.CalledProcessError) as error:
        raise click.ClickException(str(error)) from error


if __name__=='__main__':
    main()

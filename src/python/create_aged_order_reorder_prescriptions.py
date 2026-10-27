"""Compare actual line RX_ID evidence on frozen REFNUM 22 reorder matches."""
from datetime import datetime, timezone
import hashlib
import json
import subprocess
import sys

import click
from jinja2 import Environment, StrictUndefined
import pandas as pd

from src.python import create_aged_order_same_product_reorders as reorders
from src.python.create_cmpu_prescription_first_order_status import ROOT, RUNNER, digest
from src.python.markdown_tables import markdown_table, table_layout
from src.python.markdown_tables import write_text

NAME = 'aged-order-reorder-prescriptions'
TEMPLATE = ROOT / 'src/sql/aged_order_reorder_prescriptions.sql'


def requested_keys(matches):
    original = matches[['original_order_id','original_line_id']].set_axis(['order_id','order_line_id'],axis=1)
    reordered = matches[['reorder_order_id','reorder_line_id']].set_axis(['order_id','order_line_id'],axis=1)
    keys = pd.concat([original,reordered],ignore_index=True).drop_duplicates().sort_values(['order_id','order_line_id'])
    for value in keys.to_numpy().flat:
        if pd.isna(value) or value != int(value):
            raise ValueError('invalid order/line key')
    return keys


def render_sql(keys):
    if keys.empty:
        raise ValueError('no reorder line keys to extract')
    values = json.dumps([[int(r.order_id), int(r.order_line_id)] for r in keys.itertuples()], separators=(',', ':'))
    return Environment(undefined=StrictUndefined).from_string(TEMPLATE.read_text()).render(order_line_keys_json=values)


def summarize(matches, associations, raw):
    source = raw.rename(columns=str.lower).copy()
    keys = requested_keys(matches)
    expected = {(int(r.order_id),int(r.order_line_id)) for r in keys.itertuples()}
    actual = {(int(r.order_id),int(r.order_line_id)) for r in source.itertuples()}
    if actual != expected:
        raise ValueError('prescription extract keys do not match frozen reorder cohort')
    if source.duplicated(['order_id','order_line_id','rx_id','rx_usage_id']).any():
        raise ValueError('duplicate prescription/usage evidence')
    if source.shipment_rows.isna().any() or source.shipment_rows.lt(0).any() or source.shipment_rows.mod(1).ne(0).any():
        raise ValueError('invalid shipment evidence counts')
    if ((source.shipment_rows.eq(0)) & (source.rx_id.notna() | source.rx_usage_id.notna())).any():
        raise ValueError('prescription evidence on an unmatched line')
    evidence = {}
    for key, group in source.groupby(['order_id','order_line_id']):
        ids = set(group.rx_id.dropna().astype(str))
        usages = set(group.rx_usage_id.dropna().astype(str))
        evidence[key] = dict(ids=ids, usages=usages, incomplete=group.rx_id.isna().any(),
                             unmatched=group.shipment_rows.sum()==0)
    cohort = associations.loc[associations.original_order_id.notna()].groupby(
        ['original_order_id','original_line_id']).rx_id.agg(lambda s:set(s.astype(str))).to_dict()
    rows=[]
    for row in matches.to_dict(orient='records'):
        original=evidence[(row['original_order_id'],row['original_line_id'])]
        reordered=evidence[(row['reorder_order_id'],row['reorder_line_id'])]
        left,right=original['ids'],reordered['ids']
        category=('Unknown' if original['incomplete'] or reordered['incomplete'] or not left or not right
                  else 'Multiple prescriptions' if len(left)>1 or len(right)>1
                  else 'Same prescription' if left==right else 'Different prescription')
        reference=cohort[(row['original_order_id'],row['original_line_id'])]
        row.update(original_rx_ids=', '.join(sorted(left)),reorder_rx_ids=', '.join(sorted(right)),
            original_rx_usage_ids=', '.join(sorted(original['usages'])),
            reorder_rx_usage_ids=', '.join(sorted(reordered['usages'])),
            cohort_rx_ids=', '.join(sorted(reference)),prescription_comparison=category,
            original_rx_incomplete=bool(original['incomplete']),reorder_rx_incomplete=bool(reordered['incomplete']),
            original_line_missing=bool(original['unmatched']),reorder_line_missing=bool(reordered['unmatched']),
            has_shared_rx_id=bool(left & right),original_rx_matches_cohort=left==reference)
        rows.append(row)
    details=pd.DataFrame(rows)
    if details.empty:
        raise ValueError('no eligible reorder matches to compare')
    summary=[]
    for population, subset in [('All reorder attempts',details),('Shipped reorders',details.loc[details.shipped_by_as_of])]:
        for grain, group_keys in [('Cancellation/reorder line pairs',reorders.KEYS+['reorder_order_id','reorder_line_id']),
                                  ('Distinct reordered lines',['reorder_order_id','reorder_line_id']),
                                  ('Customers',['original_customer_id'])]:
            # A reorder/customer can link to several cancellations. Preserve the full evidence pattern.
            groups=subset.groupby(group_keys).prescription_comparison.agg(lambda s:' + '.join(sorted(set(s))))
            for category,count in groups.value_counts().items():
                summary.append(dict(population=population,grain=grain,category=category,
                    count=int(count),denominator=len(groups),percent=100*count/len(groups)))
    summary=pd.DataFrame(summary)
    customers=details.groupby('original_customer_id').agg(
        comparisons=('prescription_comparison',lambda s:' + '.join(sorted(set(s)))),
        has_same_prescription=('prescription_comparison',lambda s:s.eq('Same prescription').any()),
        has_different_prescription=('prescription_comparison',lambda s:s.eq('Different prescription').any()),
        has_unresolved=('prescription_comparison',lambda s:s.isin(['Unknown','Multiple prescriptions']).any()))
    audit=[('Eligible cancellation/reorder line pairs',len(details)),
        ('Distinct customers',len(customers)),('Requested distinct order/line keys',len(keys)),
        ('Extract shipment rows',int(source.shipment_rows.sum())),
        ('Original line RX_ID set differs from cohort prescription references',int((~details.original_rx_matches_cohort).sum())),
        ('Pairs with missing original RX_ID evidence',int(details.original_rx_incomplete.sum())),
        ('Pairs with missing reorder RX_ID evidence',int(details.reorder_rx_incomplete.sum())),
        ('Pairs with original line absent at enrichment',int(details.original_line_missing.sum())),
        ('Pairs with reorder line absent at enrichment',int(details.reorder_line_missing.sum())),
        ('Customers with any same-prescription reorder',int(customers.has_same_prescription.sum())),
        ('Customers with any different-prescription reorder',int(customers.has_different_prescription.sum())),
        ('Customers with both same and different',int((customers.has_same_prescription & customers.has_different_prescription).sum())),
        ('Customers with any unresolved prescription evidence',int(customers.has_unresolved.sum()))]
    if not summary.groupby(['population','grain'])['count'].sum().eq(
            summary.groupby(['population','grain']).denominator.first()).all():
        raise ValueError('prescription comparison counts do not reconcile')
    return details,customers.reset_index(),summary,pd.DataFrame(audit,columns=['measure','count'])


def load_source(keys,period,baseline_sha,cached):
    sql=render_sql(keys)
    directory=ROOT/'data'/NAME/period;parquet=directory/'source.parquet';manifest=directory/'source.json'
    if cached:
        metadata=json.loads(manifest.read_text())
        if (metadata.get('sql')!=sql or metadata.get('sql_sha256')!=hashlib.sha256(sql.encode()).hexdigest()
                or metadata.get('baseline_sha256')!=baseline_sha
                or metadata.get('parquet_sha256')!=digest(parquet)):
            raise ValueError('cached SQL, frozen cohort or fingerprint differs; refresh enrichment')
        frame=pd.read_parquet(parquet)
    else:
        directory.mkdir(parents=True,exist_ok=True)
        generated=ROOT/'src/autogenerated'/NAME/period;generated.mkdir(parents=True,exist_ok=True)
        query=generated/'aged_order_reorder_prescriptions.sql';write_text(query, sql+'\n')
        manifest.unlink(missing_ok=True)
        subprocess.run([sys.executable,str(RUNNER),str(query),'--output-parquet',str(parquet.relative_to(ROOT)),
                        '--sql-log-dir',str((generated/'sql-history').relative_to(ROOT))],cwd=ROOT,check=True)
        frame=pd.read_parquet(parquet).rename(columns=str.lower)
        metadata=dict(sql=sql,sql_sha256=hashlib.sha256(sql.encode()).hexdigest(),baseline_sha256=baseline_sha,
            parquet_sha256=digest(parquet),extracted_at_utc=datetime.now(timezone.utc).isoformat(),
            warehouse=frame.extraction_warehouse.unique().tolist())
        # Caller writes the manifest only after validating the complete comparison.
    return frame,metadata,manifest


@click.command()
@click.option('--start-date',default='2026-08-15',show_default=True)
@click.option('--end-date',default='2026-10-15',show_default=True)
@click.option('--as-of-date',default='2026-10-27',show_default=True)
@click.option('--cached',is_flag=True)
@click.option('--print-sql',is_flag=True)
def main(start_date,end_date,as_of_date,cached,print_sql):
    try:
        baseline,baseline_meta,period=reorders.load_source(start_date,end_date,as_of_date,'CUSTOMER_UPLOAD',True)
        associations,_,matches,_,_=reorders.summarize(baseline,start_date,end_date,as_of_date)
        matches=matches.loc[matches.eligibility.eq('Eligible')].copy()
        keys=requested_keys(matches)
        if print_sql:
            click.echo(render_sql(keys));return
        source,metadata,manifest=load_source(keys,period,baseline_meta['parquet_sha256'],cached)
        outputs=summarize(matches,associations,source)
        metadata.update(start_date=start_date,end_date_exclusive=end_date,as_of_date=as_of_date)
        write_text(manifest, json.dumps(metadata,indent=2)+'\n')
        tables,prefix=table_layout(ROOT,NAME,period);tables.mkdir(parents=True,exist_ok=True)
        note=(f'Frozen REFNUM 22 cohort, as-of {as_of_date} 00:00 UTC; original prescriptions created '
            f'[{start_date}, {end_date}) UTC, CMPU vet diet CUSTOMER_UPLOAD. Only eligible seven-day reorder matches.\n\n'
            'Compare RX_ID linked to the original and reordered order lines at enrichment extraction; RX_USAGE_ID is '
            'retained separately and does not define prescription identity. A single populated ID on each side gives '
            'Same prescription or Different prescription. Multiple IDs are reported separately; any missing/partial '
            'ID evidence is Unknown. No missing-ID fallback or arbitrary MIN(RX_ID) is used. Current line associations '
            'do not establish the historical prescription assignment at order placement. Cohort prescription references '
            'remain visible with an agreement flag. Customers with several reorders may have several evidence types; '
            'summary categories are mutually exclusive combinations, and customer flags allow nonexclusive any-type counts. '
            'Shipped means shipment evidence by the original as-of cutoff.\n\n'
            f"Baseline SHA-256 {metadata['baseline_sha256']}; enrichment SHA-256 {metadata['parquet_sha256']}; "
            f"enriched {metadata['extracted_at_utc']}.\n\n")
        hashes={}
        for kind,output in zip(['line-pairs','customers','summary','audit'],outputs):
            write_text(tables/f'{prefix}{kind}.md', f'# Reorder prescription comparison: {kind}\n\n'+note+markdown_table(output)+'\n')
            path=manifest.parent/f'{kind}.parquet';output.to_parquet(path,index=False);hashes[path.name]=digest(path)
        write_text(manifest.parent/'exports.json', json.dumps(dict(baseline_sha256=metadata['baseline_sha256'],
            source_sha256=metadata['parquet_sha256'],files=hashes),indent=2)+'\n')
        click.echo(outputs[2].to_string(index=False));click.echo(outputs[3].to_string(index=False));click.echo(f'Tables: {tables}')
    except (ValueError,OSError,KeyError,subprocess.CalledProcessError) as error:
        raise click.ClickException(str(error)) from error


if __name__=='__main__':
    main()

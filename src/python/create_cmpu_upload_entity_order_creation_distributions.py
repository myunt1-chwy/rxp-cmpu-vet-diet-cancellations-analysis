"""REFNUM 52: upload creation relative to first-order placement, one row per entity."""
from datetime import date, datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import altair as alt
import click
from jinja2 import Environment, StrictUndefined
import pandas as pd

from src.python import create_cmpu_upload_entity_state_change_distributions as entity
from src.python.markdown_tables import markdown_table, write_text

ROOT = Path(__file__).resolve().parents[2]
NAME = 'cmpu-upload-entity-order-creation-distributions'
TEMPLATE = ROOT/'src/sql/cmpu_upload_entity_order_creation_distributions.sql'
VERSION = 1
GROUPS = ['Overall', 'Aged orders']


def render_sql(start, end, upload_start, as_of):
    return Environment(undefined=StrictUndefined).from_string(TEMPLATE.read_text()).render(
        **entity.parameters(start, end, upload_start, as_of))


def prepare(frame, params):
    associations, entities, audit = entity.validate(frame, params)
    associations['order_placed_utc'] = pd.to_datetime(associations.order_placed_utc, utc=True, format='mixed', errors='raise')
    matched = associations.matched_order_id.notna()
    if not associations.loc[matched, 'placement_variants'].eq(1).all():
        raise ValueError('conflicting order placement timestamps across shipment rows')
    if (associations.loc[matched].groupby(['matched_order_id','matched_order_line_id'])
            .order_placed_utc.nunique(dropna=False).gt(1).any()):
        raise ValueError('conflicting order placement across associations')
    associations['created_ts_utc'] = pd.to_datetime(associations.created_ts_utc, utc=True, format='mixed', errors='raise')
    associations['upload_minus_order_hours'] = (associations.created_ts_utc-associations.order_placed_utc).dt.total_seconds()/3600
    # Earliest populated first-order placement is the same reference in both
    # populations. Key ties are deterministic; missing origins remain missing.
    ordered = associations.sort_values(['upload_id','order_placed_utc','matched_order_id','matched_order_line_id'], na_position='last')
    selected = ordered.drop_duplicates('upload_id')[['upload_id','order_placed_utc','matched_order_id','matched_order_line_id']]
    selected = selected.rename(columns={'matched_order_id':'selected_order_id','matched_order_line_id':'selected_order_line_id'})
    counts = associations.loc[matched].groupby('upload_id').agg(
        matched_orders=('matched_order_id','nunique'), order_placement_values=('order_placed_utc','nunique'))
    entities = entities.merge(selected, on='upload_id', how='left').merge(counts, on='upload_id', how='left')
    entities[['matched_orders','order_placement_values']] = entities[['matched_orders','order_placement_values']].fillna(0).astype(int)
    entities['multiple_orders'] = entities.matched_orders.gt(1)
    entities['missing_order_placement'] = entities.order_placed_utc.isna()
    entities['elapsed_hours'] = (entities.created_ts_utc-entities.order_placed_utc).dt.total_seconds()/3600
    entities['usable_duration'] = entities.elapsed_hours.notna()
    entities['negative_duration'] = entities.elapsed_hours.lt(0)
    entities['zero_duration'] = entities.elapsed_hours.eq(0)
    population_rows = pd.concat([entities.assign(state_label=GROUPS[0]),
        entities.loc[entities.aged_entity].assign(state_label=GROUPS[1])], ignore_index=True)
    stats = entity.statistics(population_rows, GROUPS).drop(columns='missing_state_change')
    stats['missing_order_placement'] = [int(population_rows.loc[population_rows.state_label.eq(g),'missing_order_placement'].sum()) for g in GROUPS]
    stats['multiple_orders'] = [int(population_rows.loc[population_rows.state_label.eq(g),'multiple_orders'].sum()) for g in GROUPS]
    stats = stats.rename(columns={'state_label':'population'})
    quality=[]
    for group in GROUPS:
        selected = population_rows.loc[population_rows.state_label.eq(group)]
        quality += [(group+': '+col, int(selected[col].sum())) for col in
            ['usable_duration','missing_creation','missing_order_placement','negative_duration','zero_duration','multiple_orders']]
    audit=pd.concat([audit,pd.DataFrame(quality,columns=['measure','count'])],ignore_index=True)
    return associations, entities, population_rows, stats, audit


def figure(rows, stats, params):
    values=rows.loc[rows.usable_duration,'elapsed_hours']
    lower=min(float(values.min()),0.) if len(values) else 0.
    upper=max(float(values.max()),0.) if len(values) else 0.
    domain=[lower*1.1 if lower<0 else -1/3600, upper*1.1 if upper>0 else 1/3600]
    chart=entity.boxplot(rows,stats.rename(columns={'population':'state_label'}),GROUPS,domain,
        'Upload creation relative to order creation',
        [f"CMPU vet diet · CUSTOMER_UPLOAD · Rx {params['start_date']} to {params['end_date']} exclusive (UTC)",
         f"Upload creation {params['upload_start_date']} to {params['upload_end_date']} exclusive (UTC) · Aged cancellation ≤ {params['as_of_date']} 00:00 UTC",
         'Upload CREATED_TS_UTC − order ORDER_PLACED_DTTM · Positive: upload after order · Negative: upload before order',
         'One observation per entity · Earliest matched first order · Median, quartiles, 1.5×IQR whiskers and all outliers',
         'Symmetric-log spacing · One-second linear region around zero · n = usable / total'])
    spec=chart.to_dict()
    # Keep all requested positive time ticks; include negative anchors and zero
    # so entities uploaded before ordering remain interpretable on the same axis.
    ticks=[-240,-72,-24,-6,-1,-.5,-5/60,-1/60,0,1/60,5/60,.5,1,6,24,48,72,120,240]
    axis=dict(values=[v for v in ticks if domain[0]<=v<=domain[1]],labelAngle=0,labelOverlap=False,
        labelLineHeight=16,labelPadding=8,
        labelExpr="datum.value == 0 ? ['0', ''] : abs(datum.value) < 1 ? [format(datum.value * 60, '.0f'), abs(datum.value) == 1/60 ? 'minute' : 'minutes'] : [format(datum.value, '.0f'), abs(datum.value) == 1 ? 'hour' : 'hours']")
    # Extra width allows signed minute/hour labels to remain horizontal.
    width=2600 if lower<0 and upper>0 else 1500
    spec['width']=width
    for layer in spec['layer']:
        encoding=layer.get('encoding',{})
        if 'y' in encoding:
            encoding['y']['title']='Population'
        if 'x' in encoding and 'field' in encoding['x']:
            encoding['x']['title']='Upload creation − order creation'
            encoding['x']['axis']=axis
        if encoding.get('text',{}).get('field')=='count_label':
            encoding['x']['value']=width
    return alt.LayerChart.from_dict(spec)


def write_outputs(frame, metadata, directory, charts, tables):
    associations, entities, rows, stats, audit=prepare(frame,metadata['parameters'])
    for path in [directory,charts,tables]:
        path.mkdir(parents=True,exist_ok=True)
    path=charts/'overall-and-aged-orders.png'
    figure(rows,stats,metadata['parameters']).save(path,scale_factor=2)
    note=('Elapsed hours = upload CREATED_TS_UTC − first-order ORDER_PLACED_DTTM. '
        'Positive means upload after order; negative means upload before order. '
        'Each UPLOAD_ID counts once per population, using the earliest populated matched first-order placement. '
        'The aged population is the subset with any qualifying aged first-order association; its entity durations use the same reference as overall. '
        'Multiple-order associations are flagged and all associations retained. Missing origins remain in exports/audits but not plotted durations. '
        'All current entity states, negative durations and outliers are retained. Linear quartiles and observed 1.5×IQR Tukey whiskers. '
        f"UTC windows: {json.dumps(metadata['parameters'])}. Extracted {metadata['extracted_at_utc']}; source SHA-256 {metadata['parquet_sha256']}.\n\n")
    exports={'associations':associations,'entities':entities,'population-entities':rows,'statistics':stats,'audit':audit}
    for name,data in exports.items():
        data.to_parquet(directory/f'{name}.parquet',index=False)
    for name,data in [('statistics',stats),('audit',audit),('entity-preview',entities.head(25))]:
        write_text(tables/f'{name}.md','# '+name+'\n\n'+note+markdown_table(data)+'\n')
    write_text(directory/'analysis.json',json.dumps(dict(metadata,
        implementation_sha256=entity.digest(Path(__file__)),
        generated_at_utc=datetime.now(timezone.utc).isoformat(),
        exports={name+'.parquet':entity.digest(directory/f'{name}.parquet') for name in exports}),indent=2)+'\n')
    return path, stats


def load_source(params,sql,cached):
    period=f"{params['start_date']}_{params['end_date']}_uploads-{params['upload_start_date']}_{params['upload_end_date']}_asof-{params['as_of_date']}"
    directory=ROOT/'data'/NAME/period
    parquet,manifest=directory/'source.parquet',directory/'source.json'
    if cached:
        metadata=json.loads(manifest.read_text())
        if (metadata.get('version')!=VERSION or metadata.get('parameters')!=params or metadata.get('sql')!=sql
                or metadata.get('parquet_sha256')!=entity.digest(parquet)):
            raise ValueError('cached SQL, dates or source fingerprint differs; rerun fresh')
        frame=pd.read_parquet(parquet)
    else:
        directory.mkdir(parents=True,exist_ok=True)
        query_dir=ROOT/'src/autogenerated'/NAME/period
        query_dir.mkdir(parents=True,exist_ok=True)
        query=query_dir/'extract.sql'
        write_text(query,sql+'\n')
        manifest.unlink(missing_ok=True)
        subprocess.run([sys.executable,str(ROOT/'.agents/skills/rxp-sql/scripts/run_snowflake_query.py'),str(query),
            '--output-parquet',str(parquet.relative_to(ROOT)),
            '--sql-log-dir',str((query_dir/'sql-history').relative_to(ROOT))],cwd=ROOT,check=True)
        frame=pd.read_parquet(parquet)
        prepare(frame,params)
        metadata=dict(version=VERSION,parameters=params,sql=sql,
            parquet_sha256=entity.digest(parquet),extracted_at_utc=datetime.now(timezone.utc).isoformat())
        write_text(manifest,json.dumps(metadata,indent=2)+'\n')
    prepare(frame,params)
    return frame,metadata,directory


@click.command()
@click.option('--start-date',default='2026-08-15')
@click.option('--end-date',default='2026-10-15')
@click.option('--upload-start-date',default='2026-08-01')
@click.option('--as-of-date',default='2026-10-27')
@click.option('--cached',is_flag=True)
@click.option('--print-sql',is_flag=True)
def main(start_date,end_date,upload_start_date,as_of_date,cached,print_sql):
    try:
        params=entity.parameters(start_date,end_date,upload_start_date,as_of_date)
        sql=render_sql(start_date,end_date,upload_start_date,as_of_date)
        if print_sql:
            click.echo(sql)
            return
        frame,metadata,directory=load_source(params,sql,cached)
        dated=f'{start_date}_{date.fromisoformat(end_date)-timedelta(days=1)}'
        path,stats=write_outputs(frame,metadata,directory,ROOT/'outputs/charts'/dated/NAME,ROOT/'outputs/tables'/dated/NAME)
        click.echo(stats.to_string(index=False))
        click.echo(f'Figure: {path}')
    except (ValueError,OSError,KeyError,subprocess.CalledProcessError) as error:
        raise click.ClickException(str(error)) from error


if __name__=='__main__':
    main()

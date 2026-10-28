"""REFNUM 43: clinic-history distribution for unique 21-day reordered customers."""
import hashlib
import json

import click
import pandas as pd

from src.python import create_aged_customer_prior_same_clinic_shipments as clinics
from src.python import create_aged_order_reorder_windows as windows
from src.python.create_aged_order_reorder_daily_customers import daily_counts
from src.python.create_cmpu_prescription_first_order_status import ROOT,digest
from src.python.markdown_tables import markdown_table,table_layout,write_text

NAME='aged-customer-21d-reorder-clinic-history'
NOTE=('One observation per customer who reordered within 21 days after an eligible aged cancellation. '
    'Reorders require identical known customer/product/pet IDs and placement in (cancellation,cancellation+21 days]. '
    'Only cancellations with complete 21-day follow-up at the UTC as-of cutoff qualify. '
    'The exported representative pair is the established shortest-delay selection, with deterministic ties. '
    'Clinic-history classification is unchanged from REFNUM 42: prior shipped prescription from the same recorded '
    'order-line CLINIC_ID before any qualifying aged order placement, excluding all aged-cancelled order IDs. '
    'It considers all of the customer’s qualifying aged orders, including orders other than the representative reorder anchor. '
    'Unknown remains separate from no qualifying prior shipments; positive-match precedence is retained. '
    'Percentages use the 21-day reordered-customer denominator and separately its assessable subset. '
    'Inputs are fingerprint-validated frozen exports; this target does not query the warehouse. '
    'Full customer details are retained in the corresponding data/ Parquet export. ')


def load_inputs(start,end,as_of):
    window_sql=windows.render_sql(start,end,as_of,require_same_pet=True,include_21_days=True)
    clinic_sql=clinics.render_sql(start,end,as_of)
    period=f'{start}_{end}_customer_upload_same-pet_reorders-7d-14d-21d_as-of-{as_of}'
    wp=ROOT/'data'/windows.NAME/period
    cp=ROOT/'data'/clinics.NAME/f'{start}_{end}_as-of-{as_of}_order-line-clinic'
    wm=json.loads((wp/'source.json').read_text());we=json.loads((wp/'exports.json').read_text())
    cm=json.loads((cp/'source.json').read_text());ce=json.loads((cp/'manifest.json').read_text())
    expected=dict(start_date=start,end_date_exclusive=end,as_of_date=as_of)
    if (any(wm.get(k)!=v or cm.get(k)!=v for k,v in expected.items())
        or wm.get('sql')!=window_sql or wm.get('sql_sha256')!=hashlib.sha256(window_sql.encode()).hexdigest()
        or wm.get('followup_days')!=[7,14,21] or wm.get('match_pet') is not True or wm.get('include_21_days') is not True
        or cm.get('sql_sha256')!=hashlib.sha256(clinic_sql.encode()).hexdigest()
        or cm.get('clinic_source')!=clinics.CLINIC_SOURCE):
        raise ValueError('input SQL, cohort options or clinic source fingerprint differs; refresh prerequisite targets')
    if (digest(wp/'source.parquet')!=wm.get('parquet_sha256') or we.get('source_sha256')!=wm.get('parquet_sha256')
        or digest(cp/'source.parquet')!=cm.get('parquet_sha256') or ce.get('source')!=cm):
        raise ValueError('input source fingerprint differs; refresh prerequisite targets')
    dependencies={}
    for p,sha in [(wp/'customers.parquet',we['files']['customers.parquet']),
        (wp/'reorder-matches.parquet',we['files']['reorder-matches.parquet']),
        (cp/'customers.parquet',ce['files'][str((cp/'customers.parquet').relative_to(ROOT))])]:
        if digest(p)!=sha:raise ValueError(f'input export fingerprint differs: {p}')
        dependencies[str(p.relative_to(ROOT))]=sha
    dependencies.update(reorder_source=wm['parquet_sha256'],clinic_source=cm['parquet_sha256'])
    return pd.read_parquet(wp/'customers.parquet'),pd.read_parquet(wp/'reorder-matches.parquet'),pd.read_parquet(cp/'customers.parquet'),dependencies


def summarize(population,matches,history):
    m=matches.loc[matches.followup_days.eq(21)]
    for original,reorder in [('original_customer_id','reorder_customer_id'),('original_product_id','reorder_product_id'),
                             ('original_pet_id','reorder_pet_id')]:
        if m[[original,reorder]].isna().any().any() or not m[original].eq(m[reorder]).all():
            raise ValueError('21-day reorder must match known customer, product and pet IDs')
    selected,_,eligible=daily_counts(matches,population,21)
    if (history.customer_id.isna().any() or history.customer_id.duplicated().any()
        or not history.group.isin(clinics.GROUPS).all()
        or not history.assessable.eq(history.group.ne('Unknown')).all()
        or not history.has_prior_same_clinic.eq(history.group.eq(clinics.GROUPS[0])).all()):
        raise ValueError('invalid source clinic customer classifications')
    if not set(selected.original_customer_id)<=set(history.customer_id):
        raise ValueError('reordered customers missing from clinic cohort; refresh prerequisite targets')
    chosen=selected[['original_customer_id','original_order_id','original_line_id','reorder_order_id',
        'reorder_line_id','order_cancel_time','reorder_placed_at_utc','elapsed_ns','day']]
    customers=chosen.merge(history,left_on='original_customer_id',right_on='customer_id',validate='one_to_one')
    total=len(customers);assessable=int(customers.assessable.sum())
    summary=customers.group.value_counts().reindex(clinics.GROUPS,fill_value=0).rename_axis('group').reset_index(name='customers')
    summary['percent_of_21d_reordered_customers']=100*summary.customers/total if total else None
    summary['percent_of_assessable_reordered_customers']=100*summary.customers/assessable if assessable else None
    summary.loc[summary.group.eq('Unknown'),'percent_of_assessable_reordered_customers']=None
    summary['all_aged_customers']=summary.group.map(history.group.value_counts()).fillna(0).astype(int)
    summary['percent_of_all_aged_customers']=100*summary.all_aged_customers/len(history) if len(history) else None
    audit=pd.DataFrame([dict(measure=label,customers=count) for label,count in [
        ('All clinic-history customers',len(history)),('Eligible complete-21-day customers',eligible),
        ('21-day reordered customers',total),('Assessable reordered customers',assessable),
        ('Unknown reordered customers',total-assessable)]])
    if summary.customers.sum()!=total or customers.customer_id.duplicated().any():raise ValueError('customer distribution does not reconcile')
    return {'summary':summary,'customers':customers,'audit':audit}


@click.command()
@click.option('--start-date',default='2026-08-15',show_default=True)
@click.option('--end-date',default='2026-10-15',show_default=True)
@click.option('--as-of-date',default='2026-10-27',show_default=True)
@click.option('--cached',is_flag=True,help='Inputs always use validated cached exports; no warehouse query.')
@click.option('--print-sql',is_flag=True,help='Print the two prerequisite extraction queries only.')
def main(start_date,end_date,as_of_date,cached,print_sql):
    try:
        window_sql=windows.render_sql(start_date,end_date,as_of_date,True,True)
        clinic_sql=clinics.render_sql(start_date,end_date,as_of_date)
        if print_sql:
            click.echo('-- Prerequisite reorder-window extraction\n'+window_sql+';\n\n-- Prerequisite clinic-history extraction\n'+clinic_sql)
            return
        population,matches,history,dependencies=load_inputs(start_date,end_date,as_of_date)
        outputs=summarize(population,matches,history)
        period=f'{start_date}_{end_date}_as-of-{as_of_date}_same-customer-product-pet'
        directory=ROOT/'data'/NAME/period;directory.mkdir(parents=True,exist_ok=True)
        tables,prefix=table_layout(ROOT,NAME,period);tables.mkdir(parents=True,exist_ok=True)
        note=NOTE+f'Cohort {start_date} inclusive to {end_date} exclusive; as-of {as_of_date} 00:00 UTC.\n\n'
        files={}
        for kind,frame in outputs.items():
            full=directory/f'{kind}.parquet';frame.to_parquet(full,index=False)
            table=tables/f'{prefix}{kind}.md';write_text(table,f'# Clinic history among 21-day reordered customers: {kind}\n\n'+note+markdown_table(frame)+'\n')
            for p in [full,table]:files[str(p.relative_to(ROOT))]=digest(p)
        write_text(directory/'manifest.json',json.dumps(dict(dependencies=dependencies,files=files,followup_days=21,
            match_keys=['customer_id','product_id','pet_id'],classification_scope='unchanged REFNUM 42 customer history'),indent=2)+'\n')
        click.echo(outputs['summary'].to_string(index=False));click.echo(f'Tables: {tables}')
    except (ValueError,OSError,KeyError) as error:
        raise click.ClickException(str(error)+'; prerequisite targets: aged-order-reorder-windows MATCH_PET=1 INCLUDE_21_DAYS=1 and aged-customer-prior-same-clinic-shipments') from error


if __name__=='__main__':main()

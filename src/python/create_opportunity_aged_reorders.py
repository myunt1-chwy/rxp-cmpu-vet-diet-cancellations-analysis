"""Non-cancelled same-customer/part-number/pet reorders after aged cancellations."""
from datetime import date, timedelta, datetime, timezone
import hashlib
import json
from pathlib import Path
import click
import duckdb
from jinja2 import Environment, StrictUndefined
import pandas as pd
import pyarrow as pa
from src.python import create_opportunity_order_cancellation_summary as base
from src.python.markdown_tables import markdown_table, write_text
from src.python import opportunity_report_tables as report_tables

ROOT=base.ROOT
KEYS=['original_order_id','original_line_id']
REORDER_KEYS=['reorder_order_id','reorder_line_id']
STUDIES=['same-part-pet','same-pet-different-part','any-vet-diet']
SCOPE_SQL={
 'same-part-pet': "original_pet_id=reorder_pet_id AND original_product_part_number=reorder_product_part_number AND NULLIF(TRIM(original_product_part_number),'') IS NOT NULL AND NULLIF(TRIM(reorder_product_part_number),'') IS NOT NULL",
 'same-pet-different-part': "original_pet_id=reorder_pet_id AND original_product_part_number<>reorder_product_part_number AND reorder_is_vet_diet=TRUE AND NULLIF(TRIM(original_product_part_number),'') IS NOT NULL AND NULLIF(TRIM(reorder_product_part_number),'') IS NOT NULL",
 'any-vet-diet': 'reorder_is_vet_diet=TRUE',
 'any-chewy': 'TRUE',
}


def scope_mask(frame,study):
    if study=='any-chewy':return pd.Series(True,index=frame.index)
    if study=='any-vet-diet':return frame.reorder_is_vet_diet.eq(True).fillna(False)
    pet=(frame.original_pet_id.notna() & frame.reorder_pet_id.notna() & frame.original_pet_id.eq(frame.reorder_pet_id))
    part=(frame.original_product_part_number.notna() & frame.reorder_product_part_number.notna()
          & frame.original_product_part_number.astype('string').str.strip().ne('') & frame.reorder_product_part_number.astype('string').str.strip().ne(''))
    if study=='same-part-pet':return (pet & part & frame.original_product_part_number.eq(frame.reorder_product_part_number)).fillna(False)
    if study=='same-pet-different-part':return (pet & part & frame.original_product_part_number.ne(frame.reorder_product_part_number) & frame.reorder_is_vet_diet.eq(True)).fillna(False)
    raise ValueError('unknown follow-up study')


def analyze(raw, frozen, days, as_of, source_days=None, study="same-part-pet", broad_source=False):
    f=raw.rename(columns=str.lower).copy()
    for col in KEYS+REORDER_KEYS+['original_customer_id','original_pet_id','reorder_customer_id','reorder_pet_id']:
        f[col]=f[col].map(base.identifier)
    for col in ['original_product_part_number','reorder_product_part_number']:
        f[col]=f[col].astype('string')
    f['original_cancel_utc']=pd.to_datetime(f.original_cancel_utc,utc=True,format='mixed')
    f['reorder_placed_utc']=pd.to_datetime(f.reorder_placed_utc,utc=True,format='mixed')
    f['reorder_shipped_utc']=pd.to_datetime(f.reorder_shipped_utc,utc=True,format='mixed')
    originals=f.drop_duplicates(KEYS).copy()
    if set(map(tuple,originals[KEYS].to_numpy()))!=set(map(tuple,frozen[KEYS].to_numpy())):
        raise ValueError('original keys differ from frozen aged membership')
    if 'registry_variants' in f and f.registry_variants.gt(1).any():
        raise ValueError('conflicting original prescription registry eligibility')
    if f[['customer_variants','pet_variants','part_variants','cancel_variants','reason_variants']].gt(1).any().any():
        raise ValueError('conflicting original source values')
    evidence=originals.merge(frozen,on=KEYS,validate='one_to_one',suffixes=('','_frozen'))
    if not (evidence.original_customer_id.eq(evidence.customer_id)
            & evidence.original_cancel_utc.eq(evidence.cancelled_at_utc)
            & evidence.original_reason.eq('aged order')).all():
        raise ValueError('aged source differs from frozen customer/cancellation evidence')
    originals['usable_match_keys']=(originals.original_customer_id.notna() & originals.original_pet_id.notna()
        & originals.original_product_part_number.notna() & originals.original_product_part_number.ne(''))
    if study in ['any-vet-diet','any-chewy']:
        originals['usable_match_keys']=originals.original_customer_id.notna()
    originals['complete_followup']=originals.original_cancel_utc.add(pd.Timedelta(days=days)).le(pd.Timestamp(as_of,tz='UTC'))
    matches=f.loc[f.reorder_order_id.notna()].copy()
    if matches.source_variants.gt(1).any(): raise ValueError('conflicting reorder source values')
    if not (matches.original_customer_id.eq(matches.reorder_customer_id)
            & matches.original_order_id.ne(matches.reorder_order_id)
            & matches.reorder_placed_utc.gt(matches.original_cancel_utc)
            & matches.reorder_placed_utc.le(matches.original_cancel_utc+pd.Timedelta(days=source_days or days))
            & matches.reorder_placed_utc.le(pd.Timestamp(as_of,tz='UTC'))).all():
        raise ValueError('reorder matching/window evidence differs')
    if not broad_source and not scope_mask(matches,study).all():
        raise ValueError('reorder matching/window evidence differs')
    matches=matches.loc[matches.reorder_placed_utc.le(matches.original_cancel_utc+pd.Timedelta(days=days))].copy()
    matches['qualifying_non_cancelled']=(matches.reorder_order_has_cancellation.eq(0)
        & matches.reorder_order_has_unknown_status.eq(0))
    eligible=originals.loc[originals.usable_match_keys & originals.complete_followup,KEYS]
    matches=matches.merge(eligible,on=KEYS,validate='many_to_one')
    # A later order may match several original cancellations. Count its lines/money once.
    matches['reorder_known_net_sales']=matches.reorder_known_net_sales.map(base.money)
    candidates=matches.copy()
    matches=matches.loc[scope_mask(matches,study)].copy()
    selected=matches.loc[matches.qualifying_non_cancelled]
    if selected.groupby(REORDER_KEYS)[['reorder_known_net_sales','missing_sales_records']].nunique(dropna=False).gt(1).any().any():
        raise ValueError('conflicting repeated reorder amounts')
    reorders=selected.drop_duplicates(REORDER_KEYS).copy()
    missing=int(reorders.missing_sales_records.sum())
    known=base.decimal_sum(reorders.reorder_known_net_sales)
    measures=dict(aged_orders=originals.original_order_id.nunique(),aged_lines=len(originals),
        aged_customers=originals.original_customer_id.nunique(),
        aged_lines_missing_match_keys=int((~originals.usable_match_keys).sum()),
        aged_lines_incomplete_followup=int((~originals.complete_followup).sum()),
        eligible_aged_orders=originals.loc[originals.usable_match_keys & originals.complete_followup].original_order_id.nunique(),
        eligible_aged_customers=originals.loc[originals.usable_match_keys & originals.complete_followup].original_customer_id.nunique(),
        matched_non_cancelled_orders=reorders.reorder_order_id.nunique(),matched_non_cancelled_lines=len(reorders),
        customers_with_non_cancelled_reorder=reorders.original_customer_id.nunique(),
        aged_orders_with_non_cancelled_reorder=selected.original_order_id.nunique(),
        candidate_orders_excluded_for_cancellation=matches.loc[matches.reorder_order_has_cancellation.eq(1)].reorder_order_id.nunique(),
        candidate_orders_excluded_for_unknown_status=matches.loc[matches.reorder_order_has_unknown_status.eq(1)].reorder_order_id.nunique(),
        missing_sales_records=missing)
    with duckdb.connect() as c:
        # Explicit precision avoids DuckDB's sampled pandas Decimal inference
        # choosing a type too small for later rows in a larger horizon.
        table=pa.Table.from_pandas(candidates.drop(columns=['reorder_known_net_sales']),preserve_index=False)
        table=table.append_column('reorder_known_net_sales',pa.array(
            candidates.reorder_known_net_sales.tolist(),type=pa.decimal128(38,5)))
        c.register('matches',table)
        counts=c.execute('''SELECT COUNT(DISTINCT reorder_order_id),COUNT(DISTINCT(reorder_order_id,reorder_line_id)),
          COUNT(DISTINCT original_customer_id),COUNT(DISTINCT original_order_id)
          FROM matches WHERE qualifying_non_cancelled AND ('''+SCOPE_SQL[study]+')').fetchone()
        amount=c.execute('''SELECT COALESCE(SUM(CAST(reorder_known_net_sales AS DECIMAL(38,5))),0)
          FROM (SELECT DISTINCT reorder_order_id,reorder_line_id,reorder_known_net_sales
                FROM matches WHERE qualifying_non_cancelled AND ('''+SCOPE_SQL[study]+'))').fetchone()[0]
    if counts!=(measures['matched_non_cancelled_orders'],len(reorders),measures['customers_with_non_cancelled_reorder'],measures['aged_orders_with_non_cancelled_reorder']) or amount!=known:
        raise ValueError('independent reorder counts/sales do not reconcile')
    summary=pd.DataFrame(measures.items(),columns=['measure','count'])
    sales=dict(known_matching_line_net_sales=str(known),matching_line_net_sales=None if missing else str(known))
    return dict(originals=originals,matches=matches,reorders=reorders,summary=summary),sales


def render_sql(start_date,end_date,as_of_date,days,all_studies=False,all_chewy=False):
    params=base.parameters(start_date,end_date)
    date.fromisoformat(as_of_date)
    if days<1: raise ValueError('follow-up must be positive')
    template='opportunity_chewy_follow_up.sql' if all_chewy else 'opportunity_aged_reorders.sql'
    return Environment(undefined=StrictUndefined).from_string((ROOT/'src/sql'/template).read_text()).render(
        **params,followup_days=days,as_of_date=as_of_date,all_studies=all_studies)


def window_table(summary,params,as_of_date,study="same-part-pet"):
    first=date.fromisoformat(params['start_date']).strftime('%B %-d, %Y')
    last=(date.fromisoformat(params['end_date'])-timedelta(days=1)).strftime('%B %-d, %Y')
    if summary.cohort_customers.nunique()!=1:raise ValueError('cohort denominator differs across windows')
    denominator=int(summary.cohort_customers.iloc[0])
    body=[]
    for r in summary.itertuples():
        amount='Incomplete' if pd.isna(r.actual_net_sales) else f'{r.actual_net_sales:,.2f}'
        percentage='N/A' if pd.isna(r.cohort_percentage) else f'{r.cohort_percentage:.2f}'+r'\%'
        body.append(f'{r.followup_days} & {r.customers:,} & {percentage} & {r.orders:,} & {amount}'+r' \\')
    text = r'''\clearpage
\subsubsection{Non-cancelled reorders after aged cancellation}
Table~\ref{tab:financial-opportunity-reorder-windows} summarizes cumulative
follow-up windows after CMPU vet-diet \texttt{CUSTOMER\_UPLOAD} aged cancellations
from '''+first+' through '+last+r''', inclusive, UTC.

\begin{table}[!htbp]
\centering
\caption{Customers, non-cancelled reorder orders and matching-line net sales within FOLLOWUP_DAYS days after aged cancellation.}
\label{tab:financial-opportunity-reorder-windows}
\begin{tabular}{@{}rrrrr@{}}
\toprule
Follow-up (days) & Customers & Cohort (\%) & Orders & Net sales \\
\midrule
'''+ '\n'.join(body)+r'''
\bottomrule
\end{tabular}

\begin{minipage}{\linewidth}
\footnotesize
\textit{Notes:} Match exact customer ID, \texttt{PRODUCT\_PART\_NUMBER} and non-null
\texttt{PET\_ID} on a different order, placed strictly after cancellation through
the indicated number of days, inclusive. Original eligibility is selected by
cancellation date, with no prescription-creation or first-order restriction.
All windows use the same source snapshot and require complete follow-up through
'''+as_of_date+r''' 00:00 UTC. Reorders may use any approval channel or prescription
source within the certified RxP order-line view. Exclude orders if any line has
status X, a recorded cancellation reason or cancellation timestamp; also exclude
orders with unknown line status. Statuses reflect the extraction snapshot.
Each customer and reorder order counts once within a window, even when linked
to several original cancellations. Windows overlap; do not add their counts.
Net sales sum \texttt{ORDER\_LINE\_NET\_SALES} on matching reorder lines only,
once per shipment/line contribution, preserving zero and negative amounts.
Sales may be recorded after the placement window; this is recorded matching-line
sales, not proof of recovered revenue. Missing sales make the total incomplete.
Amounts display two decimals; exports retain five.
\end{minipage}
\end{table}
'''

    labels=summary.followup_days.astype(str).tolist()
    horizon_text=(', '.join(labels[:-1])+' and '+labels[-1]) if len(labels)>1 else labels[0]
    text=text.replace('FOLLOWUP_DAYS',horizon_text)
    match_note = r"""Match exact customer ID, \texttt{PRODUCT\_PART\_NUMBER} and non-null
\texttt{PET\_ID} on a different order, placed strictly after cancellation through
the indicated number of days, inclusive."""
    if study=='same-pet-different-part':
        text=text.replace('Non-cancelled reorders after aged cancellation','Non-cancelled vet-diet reorders: same pet, different product')
        text=text.replace('Customers, non-cancelled reorder orders and matching-line net sales within',
            'Same-pet, different-product vet-diet reorders: customers, orders and net sales within')
        text=text.replace(match_note,
            r'Use a different order placed strictly after cancellation through the indicated day limit, inclusive. Match exact customer ID and non-null \texttt{PET\_ID}; require vet-diet lines with a nonblank \texttt{PRODUCT\_PART\_NUMBER} different from the original.')
        text=text.replace('tab:financial-opportunity-reorder-windows','tab:financial-opportunity-reorder-same-pet-different-part')
    elif study=='any-vet-diet':
        text=text.replace('Non-cancelled reorders after aged cancellation','Non-cancelled vet-diet reorders: any pet or product')
        text=text.replace('Customers, non-cancelled reorder orders and matching-line net sales within',
            'Any vet-diet reorders: customers, orders and net sales within')
        text=text.replace(match_note,
            'Use a different order placed strictly after cancellation through the indicated day limit, inclusive. Match exact customer ID and require vet-diet lines; purchases may be for any pet and any product part number.')
        text=text.replace('tab:financial-opportunity-reorder-windows','tab:financial-opportunity-reorder-any-vet-diet')
    elif study=='any-chewy':
        text=text.replace('Non-cancelled reorders after aged cancellation','Non-cancelled follow-up purchases: all Chewy')
        text=text.replace('Customers, non-cancelled reorder orders and matching-line net sales within',
            'All-Chewy follow-up purchases: customers, non-cancelled orders and net sales within')
        text=text.replace(match_note,
            'Use a different order placed strictly after cancellation through the indicated day limit, inclusive. Match customer ID only; include all Chewy product categories and all pets.')
        text=text.replace('tab:financial-opportunity-reorder-windows','tab:financial-opportunity-reorder-all-chewy')
        text=text.replace('Reorders may use any approval channel or prescription\nsource within the certified RxP order-line view.',
            r'Follow-up orders come from \texttt{EDLDB.ECOM.ORDER\_LINE}; no prescription, vet-diet, product or pet restriction applies.')
        text=text.replace(r'\texttt{ORDER\_LINE\_NET\_SALES} on matching reorder lines only,',
            r'\texttt{NET\_SALES} on all qualifying ECOM order lines,')
        text=text.replace('once per shipment/line contribution, preserving zero and negative amounts.',
            'once per physical order line, preserving zero and negative amounts. Exact source duplicates collapse and conflicting line values fail validation.')
        text=text.replace('exports retain five.', 'ECOM supplies four-decimal amounts, retained exactly in five-decimal exports.')
    text=text.replace('Windows overlap; do not add their counts.', 'Windows and studies overlap; do not add their counts.')
    text=text.replace('Customers, non-cancelled reorder orders and matching-line net sales within',
        'Customers, cohort percentages, non-cancelled reorder orders and matching-line net sales within')
    text=text.replace('customers, orders and net sales within','customers, cohort percentages, orders and net sales within')
    text=text.replace('customers, non-cancelled orders and net sales within','customers, cohort percentages, non-cancelled orders and net sales within')
    text=text.replace('Amounts display two decimals;',f'Every cohort percentage divides returning customers by the same full aged-customer cohort of {denominator:,}, including customers with no qualifying reorder or unusable matching keys. A zero cohort is shown as N/A. Amounts display two decimals;')
    return text


def customer_order_frequency(reorders,days,expected_customers,expected_orders):
    """One distinct qualifying-order count for each returning customer."""
    counts=reorders.groupby('reorder_customer_id').reorder_order_id.nunique().rename('orders').reset_index()
    with duckdb.connect() as c:
        c.register('lines',reorders[['reorder_customer_id','reorder_order_id']])
        independent=dict(c.execute('SELECT reorder_customer_id,COUNT(DISTINCT reorder_order_id) FROM lines GROUP BY reorder_customer_id').fetchall())
    if independent!=counts.set_index('reorder_customer_id').orders.to_dict():
        raise ValueError('customer order-frequency verification failed')
    if len(counts)!=expected_customers or counts.orders.sum()!=expected_orders:
        raise ValueError('customer order-frequency does not reconcile to follow-up summary')
    counts.insert(0,'followup_days',days)
    return counts


def frequency_exports(customer_counts,summary,directory,tables,params,as_of):
    summary=summary.loc[summary.study.eq('same-part-pet')] if 'study' in summary else summary
    final=summary.loc[summary.followup_days.idxmax()]
    denominator=int(final.customers);denominator_days=int(final.followup_days)
    maximum=max(1,int(customer_counts.orders.max())) if len(customer_counts) else 1
    rows=[]
    for r in summary.itertuples():
        counts=customer_counts.loc[customer_counts.followup_days.eq(r.followup_days),'orders'].value_counts()
        for orders in range(1,maximum+1):
            n=int(counts.get(orders,0))
            rows.append(dict(followup_days=r.followup_days,orders=orders,customers=n,
                denominator_customers=denominator,denominator_followup_days=denominator_days,percentage=100*n/denominator if denominator else None))
    distribution=pd.DataFrame(rows)
    if distribution.groupby('followup_days').customers.sum().tolist()!=summary.customers.tolist():
        raise ValueError('frequency customer totals do not reconcile')
    customer_counts.to_parquet(directory/'same-part-pet-customer-order-counts.parquet',index=False)
    distribution.to_parquet(directory/'same-part-pet-customer-order-frequency.parquet',index=False)
    wide=distribution.pivot(index='followup_days',columns='orders',values='percentage')
    display=wide.map(lambda v:'N/A' if pd.isna(v) else f'{v:.2f}%').reset_index()
    display.columns=['Follow-up (days)']+[str(n) for n in range(1,maximum+1)]
    note=(f"Aged cancellations [{params['start_date']}, {params['end_date']}) UTC; as of {as_of} 00:00 UTC. "
          'Same customer, pet ID and product part number, using the existing whole-order non-cancellation rules. '
          'Each column is a distinct order count per returning customer, pooled over all qualifying matched pets/products and original cancellation windows. '
          'An order counts once per customer regardless of matching lines or associations. '
          f'Every cell divides its customer count by the final {denominator_days}-day total of {denominator:,} same-part/pet returning customers, then multiplies by 100. '
          'There is no zero-order column. Earlier row totals show the share of final-window customers who have reordered by that day; the final row totals 100% before rounding. N/A means the final-window customer count is zero.\n\n')
    write_text(tables/'same-part-pet-customer-order-frequency.md','# Same-part/pet orders per returning customer\n\n'+note+markdown_table(display)+'\n')
    write_text(directory/'same-part-pet-customer-order-frequency-verification.sql',
        'SELECT reorder_customer_id,COUNT(DISTINCT reorder_order_id) AS orders FROM reorders GROUP BY reorder_customer_id;\n')
    body=[]
    for r in display.itertuples(index=False,name=None):
        body.append(' & '.join(str(v).replace('%',r'\%') for v in r)+r' \\')
    first=date.fromisoformat(params['start_date']).strftime('%B %-d, %Y')
    last=(date.fromisoformat(params['end_date'])-timedelta(days=1)).strftime('%B %-d, %Y')
    latex=r"""\clearpage
\subsubsection{Same-pet, same-product orders per returning customer}
Table~\ref{tab:financial-opportunity-customer-order-frequency} shows the
percentage distribution of distinct orders per returning customer for the
same-pet, same-product follow-up in Table~\ref{tab:financial-opportunity-reorder-windows}.
The original CMPU vet-diet \texttt{CUSTOMER\_UPLOAD} aged cancellations occurred
from """+first+' through '+last+r""", inclusive, UTC.

\begin{table}[!htbp]
\centering
\caption{Same-pet, same-product follow-up: percentage of final """+str(denominator_days)+r"""-day returning customers by number of distinct non-cancelled orders.}
\label{tab:financial-opportunity-customer-order-frequency}
\begingroup
\footnotesize
\setlength{\tabcolsep}{3pt}
\resizebox{\linewidth}{!}{%
\begin{tabular}{@{}r"""+('r'*maximum)+r"""@{}}
\toprule
Follow-up (days) & \multicolumn{"""+str(maximum)+r"""}{c}{Number of orders per customer} \\
 & """+ ' & '.join(str(n) for n in range(1,maximum+1))+r""" \\
\midrule
"""+ '\n'.join(body)+r"""
\bottomrule
\end{tabular}}
\endgroup

\begin{minipage}{\linewidth}
\footnotesize
\textit{Notes:} For each follow-up window, divide the customers with the indicated
number of distinct qualifying orders by the same final """+str(denominator_days)+r"""-day total of """+f'{denominator:,}'+r""" returning
customers in Table~\ref{tab:financial-opportunity-reorder-windows}, then multiply by 100.
No zero-order column is shown. Match exact customer,
\texttt{PET\_ID} and \texttt{PRODUCT\_PART\_NUMBER}; use the same non-cancelled-order
rules and complete follow-up through """+as_of+r""" 00:00 UTC.
Count each order once per customer, regardless of lines, shipments or repeated
original cancellations. Pool all qualifying matching pets/products and
cancellation windows per customer. Earlier rows sum to the percentage of final-window customers who have reordered by that day; only the final row totals 100\% before rounding.
N/A denotes a zero final-window customer count. Windows overlap.
\end{minipage}
\end{table}
"""
    write_text(directory/'same-part-pet-customer-order-frequency-table.tex',latex)
    return latex


@click.command()
@click.option('--start-date',default='2026-05-01')
@click.option('--end-date',default='2026-08-01',help='Exclusive UTC original cancellation end.')
@click.option('--as-of-date',default='2026-10-28',show_default=True)
@click.option('--followup-days',default=7,type=click.IntRange(min=1))
@click.option('--all-windows',is_flag=True,help='Summarize 7, 14, 21, 28, 35, 42, 49, 56, 63 and 70 days from one extract.')
@click.option('--all-studies',is_flag=True,help='Also analyze same-pet/different-product and any vet-diet orders.')
@click.option('--all-chewy',is_flag=True,help='Use ECOM.ORDER_LINE for all-category customer follow-up.')
@click.option('--write-latex',is_flag=True)
@click.option('--cached',is_flag=True)
@click.option('--print-sql',is_flag=True)
def main(start_date,end_date,as_of_date,followup_days,all_windows,all_studies,all_chewy,write_latex,cached,print_sql):
    params=base.parameters(start_date,end_date)
    if all_chewy and all_studies:raise click.UsageError('--all-chewy and --all-studies are separate source modes')
    horizons=[7,14,21,28,35,42,49,56,63,70] if all_windows else [followup_days]
    maximum=max(horizons)
    if date.fromisoformat(as_of_date)<date.fromisoformat(end_date)+timedelta(days=maximum):
        raise click.ClickException('as-of must allow complete follow-up for every cancellation')
    sql=render_sql(start_date,end_date,as_of_date,maximum,all_studies=all_studies,all_chewy=all_chewy)
    if print_sql:click.echo(sql);return
    variant='-'.join(f'{n}d' for n in horizons)
    studies=['any-chewy'] if all_chewy else (STUDIES if all_studies else ['same-part-pet'])
    root_name='aged-chewy-follow-up' if all_chewy else ('aged-reorder-studies' if all_studies else 'aged-reorder-windows')
    directory=ROOT/'data/opportunity'/root_name/f'{start_date}_{end_date}_{variant}_as-of-{as_of_date}'
    directory.mkdir(parents=True,exist_ok=True)
    source=directory/'source.parquet';manifest=directory/'source.json'
    identity=dict(version=3,**params,as_of_date=as_of_date,horizons=horizons,studies=studies,
                  sql_sha256=hashlib.sha256(sql.encode()).hexdigest())
    if cached:
        meta=json.loads(manifest.read_text())
        if meta['identity']!=identity or meta['source_sha256']!=base.digest(source):raise click.ClickException('cache fingerprint differs; rerun fresh')
    else:
        manifest.unlink(missing_ok=True)
        query=directory/'query.sql';write_text(query,sql+'\n')
        engine=base.extract(query,source,directory)
        meta=dict(identity=identity,source_sha256=base.digest(source),extracted_at_utc=datetime.now(timezone.utc).isoformat(),**engine)
    raw=pd.read_parquet(source).rename(columns=str.lower)
    if all_chewy and raw.candidate_missing_line_keys.fillna(0).gt(0).any():
        raise ValueError('ECOM candidate lines have missing identifiers')
    frozen=raw[KEYS+['original_customer_id','original_cancel_utc']].drop_duplicates().rename(
        columns={'original_customer_id':'customer_id','original_cancel_utc':'cancelled_at_utc'})
    for col in KEYS+['customer_id']:frozen[col]=frozen[col].map(base.identifier)
    frozen['cancelled_at_utc']=pd.to_datetime(frozen.cancelled_at_utc,utc=True,format='mixed')
    if frozen.duplicated(KEYS).any():raise click.ClickException('conflicting aged membership')
    if not frozen.cancelled_at_utc.between(pd.Timestamp(start_date,tz='UTC'),pd.Timestamp(end_date,tz='UTC'),inclusive='left').all():
        raise click.ClickException('original cancellations outside requested dates')
    combined=[];study_sets={};frequency_counts=[]
    for study in studies:
        old_orders=set();old_lines=set();old_customers=set()
        for days in horizons:
            results,sales=analyze(raw,frozen,days,as_of_date,source_days=maximum,study=study,broad_source=all_studies or all_chewy)
            measures=results['summary'].set_index('measure')['count']
            r=results['reorders']
            orders=set(r.reorder_order_id);lines=set(map(tuple,r[REORDER_KEYS].to_numpy()));customers=set(r.original_customer_id)
            if not (old_orders<=orders and old_lines<=lines and old_customers<=customers):raise ValueError('follow-up populations do not nest')
            old_orders,old_lines,old_customers=orders,lines,customers
            study_sets[(study,days)]=(orders,lines,customers)
            denominator=int(measures['aged_customers'])
            returning=int(measures['customers_with_non_cancelled_reorder'])
            combined.append(dict(study=study,followup_days=days,customers=returning,
                cohort_customers=denominator,cohort_percentage=100*returning/denominator if denominator else None,
                orders=int(measures['matched_non_cancelled_orders']),matching_lines=len(r),
                actual_net_sales=base.money(sales['matching_line_net_sales']),
                known_net_sales=base.money(sales['known_matching_line_net_sales']),
                missing_sales_records=int(measures['missing_sales_records'])))
            if study=='same-part-pet':
                frequency_counts.append(customer_order_frequency(r,days,int(measures['customers_with_non_cancelled_reorder']),int(measures['matched_non_cancelled_orders'])))
            prefix=study+'-' if all_studies else ''
            for name,frame in results.items():frame.to_parquet(directory/f'{prefix}{days}d-{name}.parquet',index=False)
    if all_studies:
        for days in horizons:
            if not all(a<=b for a,b in zip(study_sets[('same-pet-different-part',days)],study_sets[('any-vet-diet',days)])):
                raise ValueError('same-pet different-product population is not a subset of any-vet-diet')
    summary=pd.DataFrame(combined)
    if not all_studies:summary=summary.drop(columns='study')
    base.write_parquet(summary,directory/'summary.parquet')
    inclusive_end=date.fromisoformat(end_date)-timedelta(days=1)
    tables=ROOT/'outputs/tables/opportunity'/f'{start_date}_{inclusive_end}'
    tables.mkdir(parents=True,exist_ok=True)
    shown=summary[(['study'] if all_studies else [])+['followup_days','customers','cohort_customers','cohort_percentage','orders','actual_net_sales']].copy()
    shown['cohort_percentage']=shown.cohort_percentage.map(lambda v:'N/A' if pd.isna(v) else f'{v:.2f}%')
    shown['actual_net_sales']=shown.actual_net_sales.map(lambda v:'Incomplete' if pd.isna(v) else f'{v:,.2f}')
    note=(f'Original aged cancellations [{start_date}, {end_date}) UTC; as-of {as_of_date} 00:00 UTC. '
      'Original prescriptions: CMPU, vet diet, CUSTOMER_UPLOAD; study-specific customer/part/pet/vet-diet matching. '
      'same-part-pet matches exact customer, part number and non-null pet; same-pet-different-part requires the same pet, a different nonblank part and vet-diet TRUE; any-vet-diet requires the same customer and vet-diet TRUE for any pet/product. '
      'Strictly after cancellation through each day limit inclusive. Reorders can use any channel/source. '
      'Exclude an order with any cancelled or unknown-status line. Customers, orders and matching-line sales are deduplicated within each cumulative window. '
      'Current extraction statuses; studies and windows overlap and must not be added together. Missing/ambiguous keys and source conflicts are audited or rejected.\n\n')
    if all_chewy:
        note=(f'Original aged cancellations [{start_date}, {end_date}) UTC; as-of {as_of_date} 00:00 UTC. '
          'Original prescriptions are CMPU, vet diet and CUSTOMER_UPLOAD. Later purchases come from EDLDB.ECOM.ORDER_LINE across all categories, matching customer ID only on a different order. '
          'Placement must be strictly after cancellation through each day limit inclusive. No product, pet, vet-diet, prescription or approval-channel filter applies to later purchases. '
          'Exclude an order if any line/order has cancellation evidence, or any line has unknown status. Current snapshot statuses. '
          'Sum the view-published NET_SALES once per physical order/line key; exact duplicates collapse and conflicting line values fail validation. '
          'The view publishes four decimals; five-decimal exports retain them exactly. Zero and negative amounts remain included, and missing amounts make totals incomplete. '
          'Customers/orders/money are deduplicated across repeated aged associations within each window. Studies/windows overlap and cannot be added.\n\n')
    note+='Cohort percentages divide each window’s returning customers by the fixed full aged-customer cohort, including zero-return customers and missing matching keys; zero denominators show N/A.\n\n'
    title='# All-Chewy non-cancelled follow-up purchases' if all_chewy else '# Non-cancelled follow-up studies'
    write_text(tables/f"aged-{variant}-{'all-chewy' if all_chewy else ('all-studies' if all_studies else 'same-part-pet')}-non-cancelled-reorders.md",
        title+'\n\n'+note+markdown_table(shown)+'\n')
    frequency_latex=frequency_exports(pd.concat(frequency_counts,ignore_index=True),summary,directory,tables,params,as_of_date) if frequency_counts else ''
    study_tables={study:window_table(summary.loc[summary.study.eq(study)] if all_studies else summary,params,as_of_date,study) for study in studies}
    latex='\n'.join(study_tables.values())+('\n'+frequency_latex if frequency_latex else '')
    write_text(directory/'reorder-windows-table.tex',latex)
    if frequency_counts:
        meta['customer_order_frequency']=dict(study='same-part-pet',denominator='returning customers in the final follow-up window of the same study',denominator_followup_days=max(horizons),orders='distinct qualifying orders per customer pooled across matching pairs and cancellation windows',verification='DuckDB verifies every customer order count; customer and weighted order totals reconcile to follow-up summary',percentage_display_decimals=2)
    if all_chewy:
        meta['source_definition']=dict(table='EDLDB.ECOM.ORDER_LINE',financial_grain=['order_id','order_line_id'],net_sales_field='NET_SALES',native_scale=4,timezone='UTC',definition_verified='data/opportunity/ecom-schema/order-line-view.sql')
    meta['cohort_percentage']=dict(denominator='all distinct aged customers before matching-key exclusions',fixed_across_windows=True)
    meta.update(independent_verification='DuckDB distinct counts and exact-decimal sums for every horizon; nested population sets checked',
        exports={p.name:base.digest(p) for p in directory.glob('*.parquet')})
    write_text(manifest,json.dumps(meta,indent=2)+'\n')
    if write_latex:
        appendix=ROOT/'src/latex/appendix';appendix.mkdir(parents=True,exist_ok=True)
        filename='financial_opportunity_chewy_follow_up.tex' if all_chewy else 'financial_opportunity_reorders.tex'
        write_text(appendix/filename,latex)
        if not all_chewy:
            for study,text in study_tables.items():write_text(appendix/(report_tables.WHOLE_FILES[study]+'.tex'),text)
        if frequency_latex:write_text(appendix/(report_tables.FREQUENCY+'.tex'),frequency_latex)
        report_tables.update_follow_up_inputs(appendix/'financial_opportunity.tex')
    click.echo(summary.to_string(index=False));click.echo(f'Outputs: {directory}')


if __name__=='__main__':main()

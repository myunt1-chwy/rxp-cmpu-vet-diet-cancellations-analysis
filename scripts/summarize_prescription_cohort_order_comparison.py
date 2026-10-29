"""REFNUM 60: first/all-order cancellation comparison and exact net sales."""
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import click
import duckdb
from jinja2 import Environment, StrictUndefined
import pandas as pd

from src.python import create_opportunity_order_cancellation_summary as opportunity
from src.python.markdown_tables import markdown_table, write_text

PARENT = ROOT/'data/opportunity/prescription-cohort-orders/2026-08-15_2026-10-15'
DIRECTORY = ROOT/'data/opportunity/prescription-cohort-order-comparison/2026-08-15_2026-10-15_as-of-2026-10-27'
TEMPLATE = ROOT/'src/sql/prescription_cohort_order_sales.sql'
CUTOFF = pd.Timestamp('2026-10-27',tz='UTC')
KEYS = opportunity.KEYS
MONEY = 'order_line_net_sales'


def summarize(frozen, raw):
    frozen, raw = frozen.copy(), raw.rename(columns=str.lower).copy()
    for frame in [frozen,raw]:
        for col in KEYS+['customer_id']:
            frame[col]=frame[col].map(opportunity.identifier)
    raw['shipment_key']=raw.shipment_key.map(opportunity.identifier)
    if frozen[KEYS].isna().any().any() or frozen.duplicated(KEYS).any():
        raise ValueError('invalid frozen physical-line membership')
    if raw[KEYS].isna().any().any():
        raise ValueError('missing financial physical-line keys')
    if set(map(tuple,raw[KEYS].to_numpy()))!=set(map(tuple,frozen[KEYS].to_numpy())):
        raise ValueError('financial source keys differ from frozen cohort')
    raw[MONEY]=raw[MONEY].map(opportunity.money).astype(object)
    for col in ['order_placed_utc','order_cancel_utc']:
        raw[col]=pd.to_datetime(raw[col],utc=True,format='mixed',errors='raise')
    raw['reason_key']=raw.order_cancel_reason.astype('string').str.strip().str.casefold().replace('',pd.NA).fillna(opportunity.MISSING_REASON)
    if raw.groupby(KEYS)[['customer_id','reason_key','order_placed_utc','order_cancel_utc']].nunique(dropna=False).gt(1).any().any():
        raise ValueError('conflicting financial line identity or cancellation/placement evidence')
    if raw.groupby(KEYS+['shipment_key'],dropna=False)[MONEY].nunique(dropna=False).gt(1).any():
        raise ValueError('conflicting sales on the same financial source key')
    ships=raw.drop_duplicates(KEYS+['shipment_key']).copy()
    ships['missing_sales']=ships[MONEY].isna()
    amounts=ships.groupby(KEYS,dropna=False).agg(
        known_net_sales=(MONEY,opportunity.decimal_sum),
        missing_sales_records=('missing_sales','sum'),shipment_records=('shipment_key','size')).reset_index()
    identity=ships.drop_duplicates(KEYS)[KEYS+['customer_id','reason_key','order_placed_utc','order_cancel_utc']]
    compare=frozen.merge(identity,on=KEYS,validate='one_to_one',suffixes=('','_current'))
    if not compare.customer_id.eq(compare.customer_id_current).all() or not compare.reason.eq(compare.reason_key).all():
        raise ValueError('financial source identity/reason differs from frozen comparison')
    expected_aged=(compare.reason_key.eq('aged order') & compare.order_cancel_utc.le(CUTOFF))
    if not expected_aged.eq(compare.aged_by_prior_cutoff.eq(1)).all():
        raise ValueError('aged-cancellation membership differs from frozen cutoff')
    lines=frozen.merge(amounts,on=KEYS,validate='one_to_one')
    lines['actual_net_sales']=lines.known_net_sales.where(lines.missing_sales_records.eq(0),None)
    rows=[]
    def row(g,label,kind):
        r=dict(row_type=kind,cancellation_reason=label)
        for prefix,part in [('first',g.loc[g.first_order_line.eq(1)]),('all',g)]:
            missing=int(part.missing_sales_records.sum())
            known=opportunity.decimal_sum(part.known_net_sales)
            r.update({prefix+'_orders':part.order_id.nunique(),prefix+'_lines':len(part),
                prefix+'_net_sales':None if missing else known,
                prefix+'_known_net_sales':known,prefix+'_missing_sales_records':missing})
        return r
    for reason,g in lines.groupby('report_reason',sort=True):
        label=reason if reason.startswith('[') else reason.capitalize()
        rows.append(row(g,label,'reason'))
    rows.append(row(lines,'TOTAL','total'))
    summary=pd.DataFrame(rows)
    for prefix in ['first','all']:
        detail=summary.loc[summary.row_type.eq('reason')]
        total=summary.loc[summary.row_type.eq('total')].iloc[0]
        if (detail[prefix+'_lines'].sum()!=total[prefix+'_lines'] or
                opportunity.decimal_sum(detail[prefix+'_known_net_sales'])!=total[prefix+'_known_net_sales']):
            raise ValueError('reason subtotals do not reconcile')
    return ships,lines,summary


def verify(frozen,raw,summary):
    # Another engine recomputes counts and money directly from unique source
    # shipment records and the frozen line flags/reason labels.
    sql="""WITH financial AS (
       SELECT DISTINCT CAST(order_id AS DECIMAL(38,0)) AS order_id,
         CAST(order_line_id AS DECIMAL(38,0)) AS order_line_id,
         CAST(shipment_key AS DECIMAL(38,0)) AS shipment_key,
         CAST(order_line_net_sales AS DECIMAL(38,5)) AS sales FROM source
    ), linked AS (
       SELECT s.*,f.first_order_line,f.report_reason FROM financial s JOIN frozen f
        ON s.order_id=CAST(f.order_id AS DECIMAL(38,0)) AND s.order_line_id=CAST(f.order_line_id AS DECIMAL(38,0))
    ), populations AS (
       SELECT 'all' AS scope,* FROM linked
       UNION ALL SELECT 'first',* FROM linked WHERE first_order_line=1
    ) SELECT scope,'reason',report_reason,COUNT(DISTINCT order_id),COUNT(DISTINCT(order_id,order_line_id)),
      CASE WHEN COUNT(*) FILTER(WHERE sales IS NULL)>0 THEN NULL ELSE COALESCE(SUM(sales),0) END
      FROM populations GROUP BY scope,report_reason
      UNION ALL SELECT scope,'total','TOTAL',COUNT(DISTINCT order_id),COUNT(DISTINCT(order_id,order_line_id)),
      CASE WHEN COUNT(*) FILTER(WHERE sales IS NULL)>0 THEN NULL ELSE COALESCE(SUM(sales),0) END
      FROM populations GROUP BY scope"""
    with duckdb.connect() as c:
        c.register('source',raw.rename(columns=str.lower))
        c.register('frozen',frozen)
        results=c.execute(sql).fetchall()
    observed={(scope,kind,reason.casefold()):(orders,n,amount) for scope,kind,reason,orders,n,amount in results}
    expected={}
    for r in summary.to_dict('records'):
        for scope in ['first','all']:
            value=r[scope+'_net_sales']
            expected[(scope,r['row_type'],r['cancellation_reason'].casefold())]=(r[scope+'_orders'],r[scope+'_lines'],None if pd.isna(value) else value)
    # SQL omits a completely empty first-order reason group. Its additive
    # contribution is explicitly zero in the report table.
    for key,value in expected.items():
        if key not in observed and value==(0,0,Decimal('0.00000')):
            observed[key]=value
    if observed!=expected:
        raise ValueError('independent source-based counts or net sales differ')
    return dict(engine='DuckDB raw shipment/source aggregation',sql=sql,verified_cells=len(expected))


def fmt_money(value):
    return 'Incomplete' if pd.isna(value) else f'{value:,.2f}'


def latex_table(summary):
    def escape(value):
        for old,new in [('\\',r'\textbackslash{}'),('&',r'\&'),('%',r'\%'),('_',r'\_'),('#',r'\#')]:
            value=value.replace(old,new)
        return value
    body=[]
    for r in summary.to_dict('records'):
        if r['row_type']=='total':body.append(r'\midrule')
        values=['{'+escape(r['cancellation_reason'])+'}']
        for scope in ['first','all']:
            amount = fmt_money(r[scope+'_net_sales'])
            if r['row_type'] == 'reason' and r['cancellation_reason'] != opportunity.MISSING_REASON:
                amount = r'\textcolor{gray}{'+amount+'}'
            values += [f"{r[scope+'_orders']:,}",f"{r[scope+'_lines']:,}",amount]
        body.append(' & '.join(values)+r' \\')
    return r'''% BEGIN FIRST-ALL-ORDER-CANCELLATION-COMPARISON
\begin{table}[htbp]
\centering
\caption{Cancellation reasons, order counts and net sales for first orders and all linked orders.}
\label{tab:first-all-order-cancellations}
\small
\setlength{\tabcolsep}{5pt}
\begin{tabular}{@{}>{\raggedright\arraybackslash}p{0.28\linewidth}rrrrrr@{}}
\toprule
 & \multicolumn{3}{c}{First orders} & \multicolumn{3}{c}{All orders} \\
\cmidrule(lr){2-4}\cmidrule(lr){5-7}
Cancellation reason & Orders & Lines & Net sales & Orders & Lines & Net sales \\
\midrule
'''+ '\n'.join(body)+r'''
\bottomrule
\end{tabular}

\begin{minipage}{\linewidth}
\footnotesize
\textit{Notes:} CMPU vet-diet \texttt{CUSTOMER\_UPLOAD} prescriptions created
August 15--October 14, 2026, UTC. All orders includes first and subsequent linked
orders, without an order-placement window. Qualifying aged cancellations are
observed on or before October 27, 2026, 00:00 UTC; current aged reasons outside
that cutoff are shown separately for reconciliation. Other reasons reflect
the comparison snapshot. Counts are distinct orders and physical lines within
each group. Net sales sum \texttt{ORDER\_LINE\_NET\_SALES} once per
shipment/line record, for qualifying lines only. Amounts are displayed
to two decimals; five-decimal values remain in the data exports.
Gray net-sales amounts have a recorded cancellation reason and represent
unrealized sales, not realized revenue. TOTAL includes these gray amounts.
The validated comparison snapshot contains one additional matched first-order
line/order relative to the earlier frozen population in Table~\ref{tab:study-population-counts}.
\end{minipage}
\end{table}
% END FIRST-ALL-ORDER-CANCELLATION-COMPARISON
'''


def write_exports(ships,lines,summary,metadata,write_latex):
    for name,frame in [('shipments',ships),('order-lines-with-sales',lines),('summary',summary)]:
        # Extend the existing exact-decimal writer to both population columns.
        money_cols=[c for c in frame if c.endswith('net_sales')]
        import pyarrow as pa
        import pyarrow.parquet as pq
        table=pa.Table.from_pandas(frame.drop(columns=money_cols),preserve_index=False)
        for col in money_cols:
            table=table.append_column(col,pa.array(frame[col].tolist(),type=pa.decimal128(38,5)))
        pq.write_table(table,DIRECTORY/f'{name}.parquet')
    shown=summary[['cancellation_reason','first_orders','first_lines','first_net_sales','all_orders','all_lines','all_net_sales']].copy()
    for col in shown:
        if col.endswith('net_sales'):shown[col]=shown[col].map(fmt_money)
        elif col!='cancellation_reason':shown[col]=shown[col].map(lambda n:f'{n:,}')
    tables=ROOT/'outputs/tables/opportunity/2026-08-15_2026-10-14'
    tables.mkdir(parents=True,exist_ok=True)
    note=('Uses the fingerprint-verified all-order comparison membership and the inclusive October 27, 2026, 00:00 UTC aged cutoff. '
          'First orders are a subset of all orders; do not add the two populations. Net sales sum unique shipment/line contributions, '
          'preserving zero and negative sales. Five-decimal precision remains in Parquet; only display is rounded. '
          f"Financial source extracted {metadata['extracted_at_utc']}.\n\n")
    write_text(tables/'first-all-order-cancellation-comparison.md','# First/all-order cancellation and net-sales comparison\n\n'+note+markdown_table(shown)+'\n')
    write_text(DIRECTORY/'comparison-table.tex',latex_table(summary))
    write_text(DIRECTORY/'analysis.json',json.dumps(dict(metadata,exports={p.name:opportunity.digest(p) for p in DIRECTORY.glob('*.parquet')}),indent=2)+'\n')
    if write_latex:
        target=ROOT/'src/latex/appendix/study_population_analysis.tex'
        text=target.read_text()
        start='% BEGIN FIRST-ALL-ORDER-CANCELLATION-COMPARISON'
        end='% END FIRST-ALL-ORDER-CANCELLATION-COMPARISON'
        if start in text:
            left=text.index(start);right=text.index(end,left)+len(end)
            text=text[:left]+latex_table(summary).rstrip()+text[right:]
        else:text=text.rstrip()+'\n\n'+latex_table(summary)
        write_text(target,text)


@click.command()
@click.option('--refresh',is_flag=True,help='Fetch current sales for the frozen comparison line keys.')
@click.option('--write-latex',is_flag=True,help='Update the labelled table in the report appendix.')
def main(refresh,write_latex):
    parent=json.loads((PARENT/'analysis.json').read_text())
    frozen_path=PARENT/'cutoff-order-lines.parquet'
    parent_hash=opportunity.digest(frozen_path)
    if parent['files']['cutoff-order-lines.parquet']!=parent_hash:
        raise click.ClickException('frozen membership fingerprint mismatch')
    frozen=pd.read_parquet(frozen_path)
    keys=sorted(set(map(tuple,frozen[KEYS].astype(str).to_numpy())))
    sql=Environment(undefined=StrictUndefined).from_string(TEMPLATE.read_text()).render(keys_json=json.dumps(keys,separators=(',',':')))
    DIRECTORY.mkdir(parents=True,exist_ok=True)
    raw_path=DIRECTORY/'source.parquet'
    manifest=DIRECTORY/'source.json'
    if refresh:
        manifest.unlink(missing_ok=True)
        query=DIRECTORY/'query.sql'
        write_text(query,sql+'\n')
        engine=opportunity.extract(query,raw_path,DIRECTORY)
        metadata=dict(parent_membership_sha256=parent_hash,sql_sha256=hashlib.sha256(sql.encode()).hexdigest(),
            parquet_sha256=opportunity.digest(raw_path),extracted_at_utc=datetime.now(timezone.utc).isoformat(),**engine)
    else:
        metadata=json.loads(manifest.read_text())
        if (metadata['parent_membership_sha256']!=parent_hash or metadata['sql_sha256']!=hashlib.sha256(sql.encode()).hexdigest()
                or metadata['parquet_sha256']!=opportunity.digest(raw_path)):
            raise click.ClickException('cached financial extract or frozen membership fingerprint differs; use --refresh')
    raw=pd.read_parquet(raw_path)
    ships,lines,summary=summarize(frozen,raw)
    metadata['independent_verification']=verify(frozen,raw,summary)
    aged=summary.loc[summary.cancellation_reason.eq('Aged order')].iloc[0]
    if (int(aged.first_orders),int(aged.first_lines),int(aged.all_orders),int(aged.all_lines))!=(24408,26443,24409,26445):
        raise click.ClickException('aged counts differ from the agreed cutoff comparison')
    write_text(manifest,json.dumps(metadata,indent=2)+'\n')
    write_exports(ships,lines,summary,metadata,write_latex)
    print(summary.to_string(index=False))


if __name__=='__main__':main()

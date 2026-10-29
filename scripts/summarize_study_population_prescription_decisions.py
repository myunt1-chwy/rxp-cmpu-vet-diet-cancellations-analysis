"""REFNUM 55: summarize prescription decisions for the report's matched first-order rows."""
from pathlib import Path
import json
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))

import duckdb
import pandas as pd

from src.python.markdown_tables import markdown_table, write_text
from src.python.create_cmpu_upload_entity_state_change_distributions import digest

DIRECTORY=ROOT/'data/cmpu-study-population-prescription-decisions'
POPULATIONS=['All approval channels','CUSTOMER_UPLOAD','CUSTOMER_UPLOAD aged-cancellation subset']


def summarize(frame):
    f=frame.rename(columns=str.lower).copy()
    for column in ['rx_creation_datetime','rx_first_approved_datetime','rx_first_denied_datetime',
                   'cancel_time','line_last_denied_datetime']:
        f[column]=pd.to_datetime(f[column],utc=True,format='mixed',errors='raise')
    if f.rx_id.isna().any() or f[['order_id','order_line_id']].isna().any().any():
        raise ValueError('missing prescription or matched first-order keys')
    if f.order_id.ne(f.first_order_id).any() or f.order_line_id.ne(f.first_order_line_id).any():
        raise ValueError('both first-order keys must match')
    if (not f.approval_flag_variants.eq(1).all() or not f.reason_variants.eq(1).all()
            or f.cancel_variants.gt(1).any()):
        raise ValueError('conflicting shipment approval/cancellation evidence')
    attributes=[c for c in f.columns if c not in ['extracted_at_session_time','shipment_rows']]
    if f.groupby('rx_id')[attributes].nunique(dropna=False).gt(1).any().any():
        raise ValueError('conflicting prescription source values')
    f=f.drop_duplicates('rx_id').copy()
    if not f.rx_creation_datetime.between(pd.Timestamp('2026-08-15',tz='UTC'),pd.Timestamp('2026-10-15',tz='UTC'),inclusive='left').all():
        raise ValueError('prescription outside study window')
    # Certified line PRESCRIPTION_APPROVED is a Boolean copy of registry
    # APPROVED_NUMERATOR; validate before using the same approval definition.
    equal=(f.prescription_approved.eq(f.approved_numerator)
           | (f.prescription_approved.isna() & f.approved_numerator.isna())).fillna(False)
    if not equal.all():
        raise ValueError('line and registry prescription approval flags disagree')
    approved=f.approved_numerator.eq(True).fillna(False)
    rejected=f.rx_status.astype('string').str.strip().str.upper().eq('DENIED').fillna(False)
    f['decision']='Unknown'
    f.loc[rejected,'decision']='Rejected'
    f.loc[approved,'decision']='Approved'
    f['aged_subset']=(f.approval_channel.eq('CUSTOMER_UPLOAD')
        & f.cancel_reason.eq('aged order')
        & f.cancel_time.le(pd.Timestamp('2026-10-27',tz='UTC'))).fillna(False)
    rows=[]
    for label,mask in zip(POPULATIONS,[pd.Series(True,index=f.index),f.approval_channel.eq('CUSTOMER_UPLOAD'),f.aged_subset]):
        g=f.loc[mask]
        rows.append(dict(population=label,prescriptions=len(g),approved=int(g.decision.eq('Approved').sum()),
                         unknown=int(g.decision.eq('Unknown').sum()),rejected=int(g.decision.eq('Rejected').sum())))
    summary=pd.DataFrame(rows)
    if not summary[['approved','unknown','rejected']].sum(axis=1).eq(summary.prescriptions).all():
        raise ValueError('decision counts do not reconcile')
    return f,summary


def main():
    metadata=json.loads((DIRECTORY/'source.json').read_text())
    if digest(DIRECTORY/'source.parquet')!=metadata['parquet_sha256']:
        raise ValueError('source fingerprint mismatch')
    source=pd.read_parquet(DIRECTORY/'source.parquet').rename(columns=str.lower)
    baseline_dir=ROOT/'data/cmpu-first-order-line-status/2026-08-15_2026-10-15_uploads-from-2026-08-01_uploads-end-2026-10-26_accepted-state-change_order-placed_block-reasons'
    baseline_metadata=json.loads((baseline_dir/'source.json').read_text())
    if digest(baseline_dir/'source.parquet')!=baseline_metadata['parquet_sha256']:
        raise ValueError('baseline population source fingerprint mismatch')
    baseline=pd.read_parquet(baseline_dir/'source.parquet').rename(columns=str.lower)
    baseline=baseline.loc[baseline.line_source_rows.gt(0)]
    if not baseline.rx_id.is_unique:
        raise ValueError('baseline prescription IDs are not unique')
    omitted=source.loc[~source.rx_id.isin(baseline.rx_id)].copy()
    source=source.loc[source.rx_id.isin(baseline.rx_id)].copy()
    if set(source.rx_id)!=set(baseline.rx_id):
        raise ValueError('missing current decision evidence for frozen report cohort')
    check=source.merge(baseline[['rx_id','first_order_id','first_order_line_id','approval_channel']],on='rx_id',suffixes=('','_baseline'),validate='one_to_one')
    for col in ['first_order_id','first_order_line_id','approval_channel']:
        if not check[col].eq(check[col+'_baseline']).all():
            raise ValueError('current first-order/channel membership differs from frozen report cohort')
    details,summary=summarize(source)
    if summary.prescriptions.tolist()!=[103516,95073,26443]:
        raise ValueError('population counts differ from the report baseline')
    with duckdb.connect() as con:
        con.register('source',source)
        independent=con.sql('''WITH distinct_rx AS (
            SELECT DISTINCT rx_id,approval_channel,approved_numerator,rx_status,cancel_reason,cancel_time FROM source
        ), categories AS (
            SELECT *, CASE WHEN approved_numerator=TRUE THEN 'Approved'
                           WHEN upper(trim(rx_status))='DENIED' THEN 'Rejected' ELSE 'Unknown' END AS decision
            FROM distinct_rx
        ), populations AS (
            SELECT 0 AS population,* FROM categories
            UNION ALL SELECT 1,* FROM categories WHERE approval_channel='CUSTOMER_UPLOAD'
            UNION ALL SELECT 2,* FROM categories WHERE approval_channel='CUSTOMER_UPLOAD'
             AND cancel_reason='aged order' AND CAST(cancel_time AS TIMESTAMP_NS)<=TIMESTAMP '2026-10-27'
        ) SELECT population,count(*),count(*) FILTER(WHERE decision='Approved'),
          count(*) FILTER(WHERE decision='Unknown'),count(*) FILTER(WHERE decision='Rejected')
        FROM populations GROUP BY population ORDER BY population''').df()
    if independent.iloc[:,1:].to_numpy().tolist()!=summary.iloc[:,1:].to_numpy().tolist():
        raise ValueError('independent distinct aggregation disagrees')
    omitted.to_parquet(DIRECTORY/'excluded-newly-linked-prescriptions.parquet',index=False)
    details.to_parquet(DIRECTORY/'prescriptions.parquet',index=False)
    summary.to_parquet(DIRECTORY/'summary.parquet',index=False)
    unknown=details.loc[details.decision.eq('Unknown')].groupby(['rx_status','rx_lifecycle_state'],dropna=False).size().reset_index(name='prescriptions')
    unknown.to_parquet(DIRECTORY/'unknown-status-audit.parquet',index=False)
    note=('Count distinct RX_IDs in the same matched-first-order populations as tab:study-population-counts. '
        'Approved = APPROVED_NUMERATOR TRUE, checked against line PRESCRIPTION_APPROVED. '
        'Rejected = current RX_STATUS DENIED with no approval flag. Unknown = remaining prescriptions, including cancellations and pending records. '
        'Approval takes precedence if historical denial and approval evidence coexist. A false approval flag alone is not rejection. '
        'UTC prescription creation [2026-08-15, 2026-10-15), aged cancellation <= 2026-10-27 00:00. '
        'Decision evidence is the current snapshot, without an approval/denial-time cutoff. '
        f'Uses frozen first-order membership from the existing population table; {len(omitted)} newly linked current prescriptions are excluded and audited. '
        f"Extracted {metadata['extracted_at_utc']}; query {metadata['query_id']}.\n\n")
    tables=ROOT/'outputs/tables/2026-08-15_2026-10-14'
    tables.mkdir(parents=True,exist_ok=True)
    write_text(tables/'study-population-prescription-decisions.md','# Prescription decisions by study population\n\n'+note+markdown_table(summary)+'\n\n## Unknown status audit\n\n'+markdown_table(unknown)+'\n')
    write_text(DIRECTORY/'analysis.json',json.dumps(dict(metadata,definition=note,baseline_sha256=baseline_metadata['parquet_sha256'],exports={n:digest(DIRECTORY/n) for n in
        ['prescriptions.parquet','summary.parquet','unknown-status-audit.parquet','excluded-newly-linked-prescriptions.parquet']}),indent=2)+'\n')
    print(summary.to_string(index=False))
    print('Independent distinct aggregation and population reconciliation passed.')


if __name__=='__main__':
    main()

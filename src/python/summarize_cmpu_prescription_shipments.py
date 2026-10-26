"""Summarize documented prescription-item shipments and canceled-order overlap."""
from pathlib import Path
import hashlib
import json

import pandas as pd

from src.python.markdown_tables import markdown_table

NAME = 'cmpu-later-cancelled-orders/2026-09-01_2026-09-16'


def main():
    base = Path('data') / NAME
    frame = pd.read_parquet(base / 'shipments.parquet').rename(columns=str.lower)
    links = pd.read_parquet(base / 'links.parquet').rename(columns=str.lower)
    if frame.rx_id.isna().any() or not frame.rx_source_rows.eq(1).all():
        raise ValueError('missing or duplicate prescription source IDs')
    if set(frame.rx_id) != set(links.rx_id):
        raise ValueError('shipping and cancellation extracts use different cohorts')
    lines = frame.loc[frame.order_line_id.notna()]
    if lines.duplicated(['rx_id', 'order_line_id', 'shipment_key']).any():
        raise ValueError('duplicate prescription/order-line/shipment keys')
    for actual, expected in [('order_placed_at_eastern', 'expected_placed_at_eastern'),
                             ('shipped_at_eastern', 'expected_shipped_at_eastern')]:
        paired = frame[actual].notna() & frame[expected].notna()
        if not paired.any() or frame.loc[paired, actual].ne(frame.loc[paired, expected]).any():
            raise ValueError('missing or contradictory UTC/Eastern timestamp evidence')
    shipped = lines.loc[lines.shipped_at_utc.notna()]
    if shipped.order_id.isna().any() or shipped.order_placed_at_utc.isna().any():
        raise ValueError('shipped line missing order ID or placement timestamp')
    if shipped.shipped_at_utc.lt(shipped.order_placed_at_utc).any():
        raise ValueError('shipment precedes order placement')
    later = shipped.loc[shipped.order_placed_at_utc.gt(shipped.rx_creation_datetime)]
    canceled = links.loc[links.order_placed_at_utc.gt(links.rx_creation_datetime)
                         & links.order_status_description.eq('Canceled'), ['rx_id', 'order_id']].drop_duplicates()
    canceled_ids = set(canceled.rx_id)
    same = shipped.merge(canceled, on=['rx_id', 'order_id'], validate='many_to_one')
    coverage = canceled.merge(lines[['rx_id', 'order_id']].drop_duplicates(),
        on=['rx_id', 'order_id'], how='left', indicator=True, validate='one_to_one')
    metrics = {
        'Cohort prescriptions': frame.rx_id.nunique(),
        'Prescriptions with a recorded item shipment on any linked order': shipped.rx_id.nunique(),
        'Prescriptions with a shipment on an order placed after prescription creation': later.rx_id.nunique(),
        'Distinct later-placed orders with prescription-item shipments': later.order_id.nunique(),
        'Prescriptions with a later canceled order': len(canceled_ids),
        'Canceled-order subset with a shipment on any order': shipped.loc[shipped.rx_id.isin(canceled_ids), 'rx_id'].nunique(),
        'Canceled-order subset with a shipment on a later-placed order': later.loc[later.rx_id.isin(canceled_ids), 'rx_id'].nunique(),
        'Prescriptions with a recorded shipment on the same later canceled order': same.rx_id.nunique(),
        'Later canceled orders with a recorded prescription-item shipment': same.order_id.nunique(),
        'Later canceled prescription/order pairs lacking an order-line record': int(coverage._merge.eq('left_only').sum()),
        'Cohort prescriptions without any order-line record': len(set(frame.rx_id) - set(lines.rx_id)),
        'Delivered rows missing a shipped timestamp': int((lines.delivered_at_utc.notna() & lines.shipped_at_utc.isna()).sum()),
    }
    text = (
        '# Actual prescription-item shipments: September CMPU vet-diet cohort\n\n'
        'The cohort contains CMPU vet-diet prescriptions created September 1–15, 2026, inclusive. '
        'Shipment evidence is a non-null ORDER_LINE_SHIPPED_DTTM on '
        'EDLDB.BT_HCA_HCDM.ORDER_LINE_COST_MEASURES_RXP, joined by RX_ID. '
        'Each prescription counts once, even with multiple lines or shipments. '
        'There is no shipment/order date upper bound; the extract timestamp is recorded below.\n\n'
        + markdown_table(pd.DataFrame([{'metric': k, 'count': int(v)} for k, v in metrics.items()]))
        + f'\n\nThe canceled-order subset contains {canceled.order_id.nunique():,} distinct canceled orders '
        f'and {len(canceled):,} prescription/order pairs. Shipment on another order does not mean '
        'the canceled order shipped. The broader any-order counts include orders placed before '
        'prescription creation.\n\n'
        'Current order status alone is not used as shipment evidence. Absence of a recorded shipment '
        'is not proof of no shipment where source coverage is missing. Missing order-line coverage '
        'is audited above. UTC/Eastern timestamp checks, source-key checks, cohort equality, '
        'and shipment/placement ordering checks passed.\n\n'
        f'Shipment extract timestamp(s): {frame.extracted_at_session_time.unique().tolist()}.\n'
    )
    output = Path('outputs/tables') / NAME
    output.mkdir(parents=True, exist_ok=True)
    (output / 'shipments.md').write_text(text)
    (base / 'shipment-summary.json').write_text(json.dumps({
        'metrics': {k: int(v) for k, v in metrics.items()},
        'shipments_sha256': hashlib.sha256((base / 'shipments.parquet').read_bytes()).hexdigest(),
        'cancellation_links_sha256': hashlib.sha256((base / 'links.parquet').read_bytes()).hexdigest(),
        'sql_sha256': hashlib.sha256(Path('src/sql/cmpu_prescription_shipments.sql').read_bytes()).hexdigest(),
    }, indent=2) + '\n')
    print(text)


if __name__ == '__main__':
    main()

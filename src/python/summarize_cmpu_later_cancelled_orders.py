"""Count cohort prescriptions with later-placed, currently canceled orders."""
from pathlib import Path
import hashlib
import json

import click
import pandas as pd

from src.python.markdown_tables import markdown_table, table_layout

NAME = 'cmpu-later-cancelled-orders/2026-09-01_2026-09-16'


def summarize(frame):
    frame = frame.rename(columns=str.lower).copy()
    if frame.rx_id.isna().any() or not frame.rx_source_rows.eq(1).all():
        raise ValueError('missing or duplicate prescription source IDs')
    if frame.duplicated(['rx_id', 'order_id']).any() or frame.order_source_rows.gt(1).any():
        raise ValueError('duplicate prescription/order pairs or order source rows')
    if frame[['rx_id', 'rx_creation_datetime']].drop_duplicates().rx_id.duplicated().any():
        raise ValueError('inconsistent prescription creation timestamps')
    audits = {}
    for source, expected in [('order_placed_at_eastern', 'expected_placed_at_eastern'),
                             ('cancelled_at_eastern', 'expected_cancelled_at_eastern')]:
        paired = frame[source].notna() & frame[expected].notna()
        audits[source + '_paired_rows'] = int(paired.sum())
        if frame.loc[paired, source].ne(frame.loc[paired, expected]).any():
            raise ValueError('order UTC/Eastern timestamp evidence disagrees')
    later = frame.order_source_rows.eq(1) & frame.order_placed_at_utc.gt(frame.rx_creation_datetime)
    canceled = frame.order_status_description.astype('string').str.strip().str.lower().isin(['canceled', 'cancelled'])
    eligible = frame.loc[later & canceled].copy()
    if not eligible.empty and not audits['order_placed_at_eastern_paired_rows']:
        raise ValueError('no paired order timestamps to validate the UTC interpretation')
    if eligible.cancelled_at_utc.lt(eligible.order_placed_at_utc).any():
        raise ValueError('cancellation timestamp precedes order placement')
    eligible['reason'] = eligible.order_cancel_reason.astype('string').str.strip().replace('', pd.NA).fillna('[Missing reason]')
    reasons = eligible.groupby('reason').agg(prescriptions=('rx_id', 'nunique'),
        orders=('order_id', 'nunique'), prescription_order_pairs=('rx_id', 'size')).reset_index()
    reasons = reasons.sort_values(['orders', 'reason'], ascending=[False, True])
    total = frame.rx_id.nunique()
    matched = eligible.rx_id.nunique()
    linked = frame.order_id.notna()
    metrics = {
        'Cohort prescriptions': total,
        'Prescriptions with a valid order ID link': frame.loc[linked, 'rx_id'].nunique(),
        'Prescriptions with a matched order record': frame.loc[frame.order_source_rows.eq(1), 'rx_id'].nunique(),
        'Prescriptions with any later-placed order': frame.loc[later, 'rx_id'].nunique(),
        'Prescriptions with a later-placed canceled order': matched,
        'Prescriptions without an observed qualifying order': total - matched,
        'Distinct qualifying canceled orders': eligible.order_id.nunique(),
        'Qualifying prescription/order pairs': len(eligible),
        'Qualifying prescriptions linked via usage': eligible.loc[eligible.via_usage.eq(1), 'rx_id'].nunique(),
        'Qualifying prescriptions linked via first order': eligible.loc[eligible.via_first_order.eq(1), 'rx_id'].nunique(),
        'Qualifying prescriptions with multiple canceled orders': int(eligible.groupby('rx_id').order_id.nunique().gt(1).sum()),
        'Qualifying orders missing cancellation reasons': eligible.loc[eligible.order_cancel_reason.isna() | eligible.order_cancel_reason.astype('string').str.strip().eq(''), 'order_id'].nunique(),
        'Qualifying orders missing cancellation timestamps': eligible.loc[eligible.cancelled_at_utc.isna(), 'order_id'].nunique(),
        'Unmatched linked order IDs': frame.loc[linked & frame.order_source_rows.eq(0), 'order_id'].nunique(),
        'Matched orders missing placement timestamps': frame.loc[frame.order_source_rows.eq(1) & frame.order_placed_at_utc.isna(), 'order_id'].nunique(),
        'Matched orders missing status descriptions': frame.loc[frame.order_source_rows.eq(1) & frame.order_status_description.isna(), 'order_id'].nunique(),
        'Prescriptions with invalid usage order IDs': frame.loc[frame.invalid_order_id.eq(1), 'rx_id'].nunique(),
        'Prescriptions with missing usage order IDs': frame.loc[frame.missing_order_id.eq(1), 'rx_id'].nunique(),
        'Qualifying pairs with deletion-flagged usage history': int(eligible.deletion_flagged.eq(1).sum()),
    }
    if int(reasons.orders.sum()) != metrics['Distinct qualifying canceled orders']:
        raise ValueError('reason totals do not reconcile to distinct orders')
    if int(reasons.prescription_order_pairs.sum()) != len(eligible):
        raise ValueError('reason totals do not reconcile to pairs')
    return metrics, reasons, eligible, audits


@click.command()
@click.option('--input', 'input_path', type=click.Path(path_type=Path), default=f'data/{NAME}/links.parquet')
@click.option('--output-dir', type=click.Path(path_type=Path), default=None, help='Override the default flat dated table folder')
def main(input_path, output_dir):
    table_prefix = ''
    if output_dir is None:
        analysis, period = NAME.split('/', 1)
        output_dir, table_prefix = table_layout(Path('.'), analysis, period)
    frame = pd.read_parquet(input_path)
    metrics, reasons, eligible, audits = summarize(frame)
    total = metrics['Cohort prescriptions']
    matched = metrics['Prescriptions with a later-placed canceled order']
    rate = 100 * matched / total if total else None
    percentage = f'{rate:.2f}%' if rate is not None else 'N/A'
    snapshot = frame.rename(columns=str.lower).extracted_at_session_time.unique().tolist()
    text = (
        '# Later canceled orders for September CMPU vet-diet prescriptions\n\n'
        f'**{matched:,} of {total:,} prescriptions ({percentage})** have a linked order placed '
        'strictly after prescription creation and currently recorded as canceled.\n\n'
        'The prescription cohort is CMPU, vet diet, created September 1 inclusive through '
        'September 16 exclusive, 2026. Orders are linked through FIRST_ORDER_ID and all available '
        'RXP_RX_USAGE_ACTIONS.ORDER_ID history, deduplicated by RX_ID/order ID. No order-placement '
        'or cancellation date upper bound is imposed. Missing reasons remain included.\n\n'
        f'Extraction timestamp(s): {snapshot}.\n\n'
        + markdown_table(pd.DataFrame([{'metric': k, 'count': v} for k, v in metrics.items()]))
        + '\n\n## Cancellation reasons\n\n' + markdown_table(reasons) + '\n\n'
        'Prescription counts by reason can overlap when a prescription has multiple canceled orders. '
        'Distinct order counts are additive across reasons. Each prescription counts once in the headline.\n\n'
        'Order status/reason is the latest snapshot, not reconstructed historical status. '
        'Order placement and RX_CREATION_DATETIME are compared on a UTC interpretation; '
        'order timestamp UTC/Eastern companion values are validated where both are available. '
        'Historical usage links, including deletion-flagged records, are retained and audited. '
        'A link establishes recorded association, not causation.\n\n'
        'Validation passed: unique source keys and prescription/order pairs, consistent prescription '
        'creation timestamps, UTC/Eastern companion checks, no observed cancellation before placement '
        'among qualifying orders, and reason totals reconcile. Missing timestamps/status/links are audited above.\n'
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / (table_prefix + 'summary.md')).write_text(text)
    (output_dir / (table_prefix + 'cancellation-reasons.md')).write_text(markdown_table(reasons) + '\n')
    columns = ['rx_id', 'rx_creation_datetime', 'order_id', 'order_placed_at_utc',
               'cancelled_at_utc', 'reason', 'via_first_order', 'via_usage', 'deletion_flagged']
    (output_dir / (table_prefix + 'qualifying-links.md')).write_text(markdown_table(eligible[columns]) + '\n')
    sql = Path('src/sql/cmpu_later_cancelled_orders.sql')
    metadata = {'metrics': {k: int(v) for k, v in metrics.items()}, 'match_percent': rate,
                'timestamp_audits': audits, 'extracted_at_session_time': snapshot,
                'sql_sha256': hashlib.sha256(sql.read_bytes()).hexdigest(),
                'input_sha256': hashlib.sha256(input_path.read_bytes()).hexdigest()}
    (input_path.parent / 'summary.json').write_text(json.dumps(metadata, indent=2) + '\n')
    print(text)


if __name__ == '__main__':
    main()

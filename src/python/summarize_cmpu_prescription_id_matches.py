"""Summarize the direct Segment-properties/RX_ID join and compare associations."""
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json

import click
import pandas as pd

from src.python.markdown_tables import markdown_table

BASE = 'cmpu-upload-event-matches/2026-09-01_2026-09-16'


def summarize(frame):
    frame = frame.rename(columns=str.lower)
    if frame[['event_present', 'cohort_present']].isna().all(axis=1).any():
        raise ValueError('join row has neither an event nor a prescription')
    events = frame.loc[frame.event_present.notna()].copy()
    cohort = frame.loc[frame.cohort_present.notna(),
        ['rx_id', 'rx_customer_id', 'rx_product_id', 'rx_creation_datetime', 'rx_source_rows']].drop_duplicates()
    if cohort.rx_id.isna().any() or cohort.rx_id.duplicated().any() or not cohort.rx_source_rows.eq(1).all():
        raise ValueError('missing, duplicate or inconsistent prescription IDs')
    if events.duplicated(['event_id', 'event_product_id']).any():
        raise ValueError('duplicate event/product rows after join')
    events['conflict'] = (events.nested_prescription_id.notna() & events.root_prescription_id.notna()
                          & events.nested_prescription_id.ne(events.root_prescription_id))
    events['has_id'] = events.event_prescription_id.notna()
    events['direct_match'] = events.rx_id.notna()
    cohort_ids = set(cohort.rx_id)
    direct_ids = set(events.rx_id.dropna())
    conflict_free_ids = set(events.loc[~events.conflict, 'rx_id'].dropna())

    # Reproduce the prior numeric customer/product association as a comparison.
    events['customer_key'] = pd.to_numeric(events.event_customer_id, errors='coerce').astype('Int64')
    events['product_key'] = pd.to_numeric(events.event_product_id, errors='coerce').astype('Int64')
    cohort['customer_key'] = pd.to_numeric(cohort.rx_customer_id, errors='raise').astype('Int64')
    cohort['product_key'] = pd.to_numeric(cohort.rx_product_id, errors='raise').astype('Int64')
    pairs = events.dropna(subset=['customer_key', 'product_key'])[['customer_key', 'product_key']].drop_duplicates()
    pair_ids = set(cohort.dropna(subset=['customer_key', 'product_key']).merge(
        pairs, on=['customer_key', 'product_key'], validate='many_to_one').rx_id)
    both = direct_ids & pair_ids
    neither = cohort_ids - (direct_ids | pair_ids)
    if len(direct_ids) + len(cohort_ids - direct_ids) != len(cohort_ids):
        raise ValueError('direct counts do not reconcile')
    if sum(map(len, [both, direct_ids - pair_ids, pair_ids - direct_ids, neither])) != len(cohort_ids):
        raise ValueError('method comparison does not reconcile')
    metrics = {
        'Total CMPU vet-diet prescriptions': len(cohort_ids),
        'Matched by prescription ID': len(direct_ids),
        'Unmatched by prescription ID': len(cohort_ids - direct_ids),
        'Matched by customer/product': len(pair_ids),
        'Matched by both methods': len(both),
        'Prescription ID only': len(direct_ids - pair_ids),
        'Customer/product only': len(pair_ids - direct_ids),
        'Neither method': len(neither),
        'Either method (includes customer/product associations)': len(direct_ids | pair_ids),
        'Matched by prescription ID excluding conflicting events': len(conflict_free_ids),
        'Deduplicated event/product rows': len(events),
        'Distinct non-null event IDs': events.event_id.nunique(),
        'Event rows with nested prescriptionId': int(events.nested_prescription_id.notna().sum()),
        'Event rows with root prescriptionId': int(events.root_prescription_id.notna().sum()),
        'Event rows with either prescriptionId': int(events.has_id.sum()),
        'Event rows with conflicting IDs': int(events.conflict.sum()),
        'Event rows matching cohort by prescription ID': int(events.direct_match.sum()),
        'Event rows with ID outside or absent from cohort': int((events.has_id & ~events.direct_match).sum()),
        'Direct-match event rows lacking customer or product': int((events.direct_match &
            (events.customer_key.isna() | events.product_key.isna())).sum()),
        'Direct-match rows with a different recorded customer': int((events.direct_match &
            events.customer_key.notna() & events.customer_key.ne(pd.to_numeric(events.rx_customer_id, errors='coerce'))).sum()),
        'Direct-match rows with a different recorded product': int((events.direct_match &
            events.product_key.notna() & events.product_key.ne(pd.to_numeric(events.rx_product_id, errors='coerce'))).sum()),
    }
    coverage = events.groupby(['event_category', 'event_label'], dropna=False).agg(
        event_product_rows=('event_present', 'size'),
        nested_id_filled=('nested_prescription_id', 'count'),
        root_id_filled=('root_prescription_id', 'count'),
        either_id_filled=('has_id', 'sum'), conflicting_ids=('conflict', 'sum'),
        direct_match_rows=('direct_match', 'sum'), distinct_matched_rx=('rx_id', 'nunique')).reset_index()
    if int(coverage.event_product_rows.sum()) != len(events):
        raise ValueError('event coverage does not reconcile')
    return metrics, coverage


@click.command()
@click.option('--input', 'input_path', type=click.Path(path_type=Path),
              default=f'data/{BASE}/prescription-id/matches.parquet', show_default=True)
@click.option('--output-dir', type=click.Path(path_type=Path),
              default=f'outputs/tables/{BASE}/prescription-id', show_default=True)
def main(input_path, output_dir):
    metrics, coverage = summarize(pd.read_parquet(input_path))
    total = metrics['Total CMPU vet-diet prescriptions']
    rate = 100 * metrics['Matched by prescription ID'] / total if total else None
    output_dir.mkdir(parents=True, exist_ok=True)
    table = pd.DataFrame([{'metric': k, 'count': v} for k, v in metrics.items()])
    percent = f'{rate:.2f}%' if rate is not None else 'N/A'
    text = (
        '# Segment prescription-ID matches: September 1–15, 2026\n\n'
        f'Direct match rate: **{percent}**. Source: EDLDB.SEGMENT.SEGMENT_HITS_PRODUCTS_UNION.\n\n'
        'Both event session dates and prescription creation timestamps use September 1 inclusive '
        'through September 16 exclusive. Prescriptions require CMPU and IS_VET_DIET_FLAG = TRUE. '
        'The original auth-file-submit, upload-preview-upload and upload-success filters are retained; '
        'the broader example event-label list is not added. Events are deduplicated by event_id/product_id.\n\n'
        'Use COALESCE(properties:eventData:prescriptionId, properties:prescriptionId), trimming blanks '
        'and treating JSON null as missing. Match the selected ID exactly to RX_ID; no customer/product '
        'or timestamp-order requirement is added. Conflicts prefer the nested ID and are audited below.\n\n'
        + markdown_table(table) + '\n\n## Field coverage by event type\n\n'
        + markdown_table(coverage) + '\n\n'
        'Coverage counts event/product rows; a single event may contain multiple products. '
        'Distinct matched prescriptions across event types are non-additive. IDs outside the '
        'cohort may belong to older prescriptions, other prescription sources/categories, or absent records; '
        'this analysis does not distinguish those cases. Customer/product matches remain candidate '
        'associations and are reported separately from direct ID matches. Preview/click events do not '
        'necessarily indicate a successful upload.\n\n'
        'Validation: unique/nonmissing cohort RX_IDs, unique event/product rows, full matched/unmatched '
        'and method-overlap reconciliation, and complete event-type coverage checks passed.\n'
    )
    (output_dir / 'summary.md').write_text(text)
    (output_dir / 'field-coverage.md').write_text(markdown_table(coverage) + '\n')
    sql = Path('src/sql/cmpu_upload_prescription_id_matches.sql')
    metadata = {'summarized_at_utc': datetime.now(timezone.utc).isoformat(),
                'input': str(input_path), 'input_sha256': hashlib.sha256(input_path.read_bytes()).hexdigest(),
                'sql': str(sql), 'sql_sha256': hashlib.sha256(sql.read_bytes()).hexdigest(),
                'direct_match_percent': rate, 'metrics': metrics}
    (input_path.parent / 'summary.json').write_text(json.dumps(metadata, indent=2) + '\n')
    print(text)


if __name__ == '__main__':
    main()

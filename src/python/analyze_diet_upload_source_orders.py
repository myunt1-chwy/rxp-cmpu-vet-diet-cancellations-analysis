"""Compare ECOM cancellation reasons for diet-upload source order populations."""
import hashlib
import json
from pathlib import Path

import pandas as pd

from src.python.analyze_null_resource_uploads import numeric_id
from src.python.create_upload_data_verification import SOURCES, latex_escape
from src.python.markdown_tables import markdown_table, write_text

ROOT = Path(__file__).resolve().parents[2]
NAME = 'diet-upload-source-cancellation-reasons'
DATA = ROOT/'data'/NAME


def main():
    uploads = pd.read_parquet(DATA/'uploads.parquet')
    orders = pd.read_parquet(DATA/'orders.parquet')
    for frame in (uploads, orders):
        frame.columns = frame.columns.str.lower()
    if set(uploads.source_table) != set(SOURCES):
        raise ValueError('Expected both documented upload sources')
    if orders.order_id.isna().any() or orders.order_id.duplicated().any():
        raise ValueError('ECOM order IDs must be populated and unique before joining')
    orders['order_id'] = orders.order_id.map(int).astype(object)
    uploads['order_id'] = pd.Series([numeric_id(v) for v in uploads.order_id_text], dtype=object)
    if (uploads.order_id_text.notna() & uploads.order_id.isna()).any():
        raise ValueError('A populated order ID is blank or invalid; resolve before comparing sources')
    if uploads.duplicated(['source_table', 'upload_id']).any():
        raise ValueError('Unexpected duplicate upload IDs within a source')
    eligible = uploads[uploads.order_id.notna()]
    source_orders = eligible[['source_table', 'order_id']].drop_duplicates()
    linked = source_orders.merge(orders, on='order_id', how='left', validate='many_to_one', indicator=True)
    linked['reason'] = linked.order_cancel_reason.fillna('[SQL NULL]')
    linked.loc[linked._merge == 'left_only', 'reason'] = '[No matching ECOM order]'
    summary = []
    for source in SOURCES:
        raw = uploads[uploads.source_table == source]
        subset = linked[linked.source_table == source]
        summary.append({
            'Source': source, 'Diet upload entries': len(raw),
            'Entries with order ID': int(raw.order_id.notna().sum()),
            'Entries without order ID': int(raw.order_id.isna().sum()),
            'Distinct order IDs': len(subset),
            'Matched orders': int((subset._merge == 'both').sum()),
            'Unmatched order IDs': int((subset._merge == 'left_only').sum()),
            'Canceled orders': int(subset.order_status_description.eq('Canceled').sum()),
            'Canceled orders with NULL reason': int((subset.order_status_description.eq('Canceled') & subset.order_cancel_reason.isna()).sum()),
        })
    coverage = pd.DataFrame(summary)
    denominators = dict(zip(coverage.Source, coverage['Distinct order IDs']))
    counts = linked.groupby(['reason', 'source_table']).size().unstack(fill_value=0).reindex(columns=SOURCES, fill_value=0)
    counts = counts.loc[counts.sum(axis=1).sort_values(ascending=False).index]
    if any(int(counts[source].sum()) != denominators[source] for source in SOURCES):
        raise ValueError('Reason counts do not reconcile to distinct source order counts')
    comparison = pd.DataFrame({'Order cancellation reason': counts.index})
    for source in SOURCES:
        comparison[source] = [f'{n:,} ({100*n/denominators[source]:.2f}%)' for n in counts[source]]
    differences = counts[SOURCES[1]] - counts[SOURCES[0]]
    total_difference = denominators[SOURCES[1]] - denominators[SOURCES[0]]
    if int(differences.sum()) != total_difference:
        raise ValueError('Reason differences do not reconcile to the source-total difference')
    comparison['Difference (notification minus HCDM orders)'] = [f'{n:+,}' if n else '0' for n in differences]
    comparison.loc[len(comparison)] = [
        'Total', *[f'{denominators[s]:,} (100.00%)' for s in SOURCES],
        f'{total_difference:+,}' if total_difference else '0',
    ]
    sets = [set(source_orders.loc[source_orders.source_table == source, 'order_id']) for source in SOURCES]
    metadata = {
        'scope': "associated_resource_type = 'DIET_PRESCRIPTION', valid non-null associated order ID, all dates and order statuses; no order-item, upload-type, or replication filters",
        'order_id_fields': {SOURCES[0]: 'ORDER_ID', SOURCES[1]: 'context:orderId'},
        'grain': 'one distinct order ID per source; percentages include unmatched order IDs',
        'difference': 'notification-service distinct-order count minus HCDM distinct-order count',
        'uploads_extracted_at': uploads.extracted_at_session_time.unique().tolist(),
        'orders_extracted_at': orders.extracted_at_session_time.unique().tolist(),
        'shared_order_ids': len(sets[0] & sets[1]),
        'hcdm_only_order_ids': len(sets[0] - sets[1]),
        'notification_only_order_ids': len(sets[1] - sets[0]),
        'source_sha256': {name: hashlib.sha256((DATA/name).read_bytes()).hexdigest() for name in ['uploads.parquet', 'orders.parquet']},
        'sql_sha256': {name: hashlib.sha256((ROOT/'src/sql'/name).read_bytes()).hexdigest() for name in ['diet_upload_source_orders.sql', 'diet_upload_linked_orders.sql']},
    }
    notes = ('All available `DIET_PRESCRIPTION` source entries with an associated order ID. '
             'Order IDs come from HCDM `ORDER_ID` and notification-service `context:orderId`. '
             'Reasons come from `EDLDB.ECOM.ORDERS`. Each distinct order counts once per source; '
             'percentages use each source’s complete distinct-order population, including unmatched IDs. '
             'Difference is notification-service order count minus HCDM order count. '
             'SQL NULL means no recorded reason, which can include canceled orders. '
             f'Upload extraction: {metadata["uploads_extracted_at"][0]}; '
             f'order extraction: {metadata["orders_extracted_at"][0]}.\n\n')
    table_dir = ROOT/'outputs/tables'/NAME
    table_dir.mkdir(parents=True, exist_ok=True)
    for name, frame in [('order-cancel-reasons', comparison), ('source-coverage', coverage)]:
        write_text(table_dir/f'{name}.md', '# Diet-upload source comparison\n\n' + notes + markdown_table(frame) + '\n')
        frame.to_parquet(DATA/f'{name}.parquet', index=False)
    linked.to_parquet(DATA/'source-order-links.parquet', index=False)
    counts.reset_index().to_parquet(DATA/'reason-counts.parquet', index=False)
    write_text(DATA/'analysis.json', json.dumps(metadata, indent=2) + '\n')

    first, second = summary
    tex = [
        r'This comparison includes entries with \texttt{associated\_resource\_type = DIET\_PRESCRIPTION} '
        r'and a non-null associated order ID in each source. HCDM uses '
        r'\texttt{ORDER\_ID}; the notification-service source uses \texttt{context:orderId}. '
        r'Cancellation reasons are joined from \texttt{EDLDB.ECOM.ORDERS}. '
        r'No date, CMPU, study-cohort, order-item, upload-type, or replication filters are applied.',
        f'In HCDM, {first["Entries with order ID"]:,} of {first["Diet upload entries"]:,} diet-upload entries '
        f'have an order ID, representing {first["Distinct order IDs"]:,} distinct orders. '
        f'In the notification-service source, {second["Entries with order ID"]:,} of '
        f'{second["Diet upload entries"]:,} entries have an order ID, representing '
        f'{second["Distinct order IDs"]:,} distinct orders. '
        r'Table~\ref{tab:diet-upload-source-cancel-reasons} compares the cancellation reasons side by side. '
        r'Each order counts once within each source regardless of the number of uploads.',
        r'\begin{longtable}{@{}lrrr@{}}',
        r'\caption{Order cancellation reasons for diet-prescription uploads with associated order IDs.}',
        r'\label{tab:diet-upload-source-cancel-reasons}\\',
        r'\toprule',
        r'Order cancellation reason & '
        r'\shortstack{\texttt{EDLDB.BT\_HCA\_HCDM.}\\\texttt{rxp\_upload\_entity}\\Orders (\%)} & '
        r'\shortstack{\texttt{rxp\_notification\_service.}\\\texttt{upload\_entity}\\Orders (\%)} & '
        r'\shortstack{Difference\\Notification\\minus HCDM} \\',
        r'\midrule', r'\endfirsthead',
        r'\toprule Order cancellation reason & HCDM orders (\%) & Notification orders (\%) & Difference \\',
        r'\midrule', r'\endhead',
    ]
    labels = {'[SQL NULL]': 'No recorded reason (SQL NULL)', '[No matching ECOM order]': 'No matching ECOM order'}
    for row in comparison.itertuples(index=False, name=None):
        if row[0] == 'Total':
            tex.append(r'\midrule')
        tex.append('{' + latex_escape(labels.get(row[0], row[0])) + '} & ' +
                   ' & '.join(latex_escape(cell) for cell in row[1:]) + r' \\')
    tex.extend([
        r'\bottomrule', r'\end{longtable}',
        r'\noindent\textit{Notes:} Percentages use each source\textquotesingle s distinct-order total, '
        r'and the difference is the notification-service order count minus the HCDM order count. '
        r'Totals include unmatched IDs; the two source populations are not restricted to their intersection. '
        f'{metadata["shared_order_ids"]:,} order IDs occur in both sources, '
        f'{metadata["hcdm_only_order_ids"]:,} occur only in HCDM and '
        f'{metadata["notification_only_order_ids"]:,} occur only in the notification-service source. '
        f'Unmatched order IDs: {first["Unmatched order IDs"]:,} in HCDM and '
        f'{second["Unmatched order IDs"]:,} in the notification-service source. '
        r'A NULL reason does not imply that an order was not canceled. '
        f'Of {first["Canceled orders"]:,} HCDM-linked orders and '
        f'{second["Canceled orders"]:,} notification-linked orders with status \\texttt{{Canceled}}, '
        f'{first["Canceled orders with NULL reason"]:,} and '
        f'{second["Canceled orders with NULL reason"]:,}, respectively, have a NULL reason. '
        r'Percentages may not sum to 100\% because of rounding. '
        r'Upload extraction: ' + latex_escape(metadata['uploads_extracted_at'][0]) +
        r'; order extraction: ' + latex_escape(metadata['orders_extracted_at'][0]) + r' (UTC).',
    ])
    tex_path = ROOT/'src/autogenerated'/NAME/'order-cancel-reasons.tex'
    tex_path.parent.mkdir(parents=True, exist_ok=True)
    write_text(tex_path, '\n'.join(tex) + '\n')
    print(coverage.to_string(index=False))
    print(comparison.to_string(index=False))


if __name__ == '__main__':
    main()

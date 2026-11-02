"""Reconcile vet-diet upload coverage by prescription source and RX_STATUS."""
import hashlib
import json
from pathlib import Path

import pandas as pd

from src.python.create_upload_data_verification import latex_escape
from src.python.markdown_tables import markdown_table, write_text

ROOT = Path(__file__).resolve().parents[2]
NAME = 'cmpu-approved-prescription-upload-coverage'
DATA = ROOT/'data'/NAME


def coverage_counts(frame):
    h, n = frame.has_hcdm_upload, frame.has_notification_upload
    result = dict(eligible_prescriptions=len(frame), any_hcdm=int(h.sum()),
                  any_notification=int(n.sum()), both_sources=int((h & n).sum()),
                  hcdm_only=int((h & ~n).sum()), notification_only=int((~h & n).sum()),
                  neither_source=int((~h & ~n).sum()))
    if sum(result[key] for key in ['both_sources', 'hcdm_only', 'notification_only', 'neither_source']) != len(frame):
        raise ValueError('Coverage partition does not reconcile to the prescription population')
    return result


def main():
    source = pd.read_parquet(DATA/'source.parquet')
    validation = pd.read_parquet(DATA/'validation.parquet')
    for frame in (source, validation):
        frame.columns = frame.columns.str.lower()
    if source.rx_id.isna().any() or source.rx_id.str.strip().eq('').any() or source.rx_id.duplicated().any():
        raise ValueError('Qualifying prescriptions must have populated, unique rx_id values')
    if not source.prescription_source_rows.map(int).eq(1).all():
        raise ValueError('Prescription source grain is not unique by rx_id')
    for field in ['has_hcdm_upload', 'has_notification_upload']:
        if source[field].isna().any() or not source[field].isin([True, False]).all():
            raise ValueError('Coverage flags must be populated booleans')
    counts = coverage_counts(source)
    overall = validation[validation.is_overall]
    if len(overall) != 1:
        raise ValueError('Expected one independent overall validation row')
    audit = overall.iloc[0]
    if int(audit.source_rows) != len(source) or int(audit.missing_rx_ids) != 0:
        raise ValueError('Independent source-grain check differs from the prescription extract')
    for key, value in counts.items():
        if int(audit[key]) != value:
            raise ValueError(f'Independent Snowflake coverage count differs: {key}')
    source['status_label'] = source.rx_status.map(lambda v: '[SQL NULL]' if pd.isna(v) else str(v))
    status_audit = validation[~validation.is_overall & validation.is_source_rollup].copy()
    status_audit['status_label'] = status_audit.rx_status.map(lambda v: '[SQL NULL]' if pd.isna(v) else str(v))
    if status_audit.status_label.duplicated().any() or set(status_audit.status_label) != set(source.status_label):
        raise ValueError('Independent status groups do not match the prescription extract')
    status_audit = status_audit.set_index('status_label')
    records = []
    for status, group in source.groupby('status_label'):
        group_counts = coverage_counts(group)
        audit_row = status_audit.loc[status]
        if int(audit_row.source_rows) != len(group) or int(audit_row.missing_rx_ids) != 0:
            raise ValueError(f'Independent source-grain check differs for status {status}')
        for key, value in group_counts.items():
            if int(audit_row[key]) != value:
                raise ValueError(f'Independent coverage count differs for status {status}: {key}')
        records.append(dict(rx_status=status, **group_counts))
    status_counts = pd.DataFrame(records).sort_values('eligible_prescriptions', ascending=False)
    for key, value in counts.items():
        if int(status_counts[key].sum()) != value:
            raise ValueError(f'Status counts do not reconcile to the overall {key}')
    def source_label(value):
        return '[SQL NULL]' if pd.isna(value) else '[empty string]' if value == '' else str(value)

    source['source_label'] = source.prescription_source.map(source_label)
    validation['source_label'] = validation.prescription_source.map(source_label)
    validation['status_label'] = validation.rx_status.map(lambda v: '[SQL NULL]' if pd.isna(v) else str(v))
    detail_audit = validation[~validation.is_source_rollup & ~validation.is_status_rollup]
    if detail_audit.duplicated(['source_label', 'status_label']).any():
        raise ValueError('Duplicate independent prescription-source/status groups')
    detail_audit = detail_audit.set_index(['source_label', 'status_label'])
    pairs = set(source[['source_label', 'status_label']].itertuples(index=False, name=None))
    if set(detail_audit.index) != pairs:
        raise ValueError('Independent prescription-source/status groups differ')
    detail_records = []
    for (prescription_source, status), group in source.groupby(['source_label', 'status_label']):
        group_counts = coverage_counts(group)
        audit_row = detail_audit.loc[(prescription_source, status)]
        if int(audit_row.source_rows) != len(group) or int(audit_row.missing_rx_ids) != 0:
            raise ValueError('Independent prescription-source/status grain differs')
        for key, value in group_counts.items():
            if int(audit_row[key]) != value:
                raise ValueError(f'Coverage differs for {prescription_source}/{status}: {key}')
        detail_records.append(dict(prescription_source=prescription_source, rx_status=status, **group_counts))
    source_status_counts = pd.DataFrame(detail_records)
    source_audit = validation[~validation.is_source_rollup & validation.is_status_rollup]
    if source_audit.source_label.duplicated().any() or set(source_audit.source_label) != set(source.source_label):
        raise ValueError('Independent prescription-source subtotal groups differ')
    source_audit = source_audit.set_index('source_label')
    source_records = []
    for prescription_source, group in source.groupby('source_label'):
        group_counts = coverage_counts(group)
        audit_row = source_audit.loc[prescription_source]
        for key, value in group_counts.items():
            if int(audit_row[key]) != value:
                raise ValueError(f'Coverage subtotal differs for {prescription_source}: {key}')
            if int(source_status_counts.loc[source_status_counts.prescription_source == prescription_source, key].sum()) != value:
                raise ValueError('Prescription-source/status groups do not reconcile to source subtotals')
        source_records.append(dict(prescription_source=prescription_source, **group_counts))
    source_counts = pd.DataFrame(source_records).sort_values('eligible_prescriptions', ascending=False)
    for key, value in counts.items():
        if int(source_counts[key].sum()) != value:
            raise ValueError('Prescription-source subtotals do not reconcile to the overall total')
    for status_row in status_counts.to_dict('records'):
        subset = source_status_counts[source_status_counts.rx_status == status_row['rx_status']]
        if any(int(subset[key].sum()) != status_row[key] for key in counts):
            raise ValueError('Prescription-source/status groups do not reconcile to status subtotals')
    timestamps = source.extracted_at_utc.unique()
    if len(timestamps) != 1:
        raise ValueError('Expected one extraction timestamp')
    rows = []
    display_records = []
    for subtotal in source_counts.to_dict('records'):
        name = subtotal['prescription_source']
        detail = source_status_counts[source_status_counts.prescription_source == name].sort_values('eligible_prescriptions', ascending=False)
        display_records.extend(detail.to_dict('records'))
        display_records.append(dict(rx_status='All statuses', **subtotal))
    display_records.append(dict(prescription_source='All sources', rx_status='All statuses', **counts))
    for record in display_records:
        total = record['eligible_prescriptions']
        def with_share(field):
            value = record[field]
            return f'{value:,} ({100*value/total:.2f}%)' if total else '0 (0.00%)'
        rows.append([record['prescription_source'], record['rx_status'], f'{total:,}', with_share('any_hcdm'),
                     with_share('any_notification'), with_share('both_sources'),
                     f'{record["hcdm_only"]:,}', f'{record["notification_only"]:,}',
                     with_share('neither_source')])
    table = pd.DataFrame(rows, columns=['PRESCRIPTION_SOURCE', 'RX_STATUS', 'Eligible prescriptions', 'HCDM: n (%)',
                        'Notification: n (%)', 'Both: n (%)', 'HCDM only', 'Notification only', 'Neither: n (%)'])
    notes = ('Source: EDLDB.BT_HCA_HCDM.RXP_PRESCRIPTIONS. Eligibility: '
             "IS_VET_DIET_FLAG = TRUE, APPROVAL_CHANNEL = 'CUSTOMER_UPLOAD', "
             "RX_CREATION_DATETIME >= '2026-07-30 00:00:00' UTC. "
             'All prescription sources and current RX_STATUS values are included, with SQL NULL status explicit when present. '
             'No upper creation-date bound or deletion filter. '
             'Match only on rx_id after splitting and trimming HCDM RX_ID and notification-service '
             'ASSOCIATED_RESOURCE_IDS. Missing, blank and zero ID tokens are excluded. '
             'Distinct upload-source prescription-ID sets prevent multiple uploads from multiplying prescriptions. '
             'No customer, order, upload-date or associated-resource-type restriction. '
             'Within each prescription-source/status group, source-match counts overlap; '
             'both / HCDM only / notification only / neither form a disjoint partition. '
             'Percentages use the eligible count on that row. All statuses rows are source subtotals; '
             'All sources / All statuses is the overall total. Subtotals are not additive with their detail rows. '
             'No current match does not establish that an upload never existed. '
             f'Extracted: {timestamps[0]} UTC.\n\n')
    table_path = ROOT/'outputs/tables'/NAME/'coverage.md'
    table_path.parent.mkdir(parents=True, exist_ok=True)
    write_text(table_path, '# Vet-diet customer-upload coverage by prescription source and RX_STATUS\n\n' + notes + markdown_table(table) + '\n')
    table.to_parquet(DATA/'coverage.parquet', index=False)
    status_counts.to_parquet(DATA/'status-counts.parquet', index=False)
    source_status_counts.to_parquet(DATA/'source-status-counts.parquet', index=False)
    source_counts.to_parquet(DATA/'prescription-source-counts.parquet', index=False)
    metadata = {
        'extracted_at_utc': str(timestamps[0]), 'counts': counts,
        'counts_by_rx_status': status_counts.to_dict('records'),
        'counts_by_prescription_source': source_counts.to_dict('records'),
        'counts_by_source_and_status': source_status_counts.to_dict('records'),
        'filters': dict(prescription_source=None, approval_channel='CUSTOMER_UPLOAD',
                        is_vet_diet_flag=True,
                        rx_status=None, inclusive_start_utc='2026-07-30 00:00:00', upper_bound=None),
        'join': 'rx_id only; distinct normalized upload-source ID sets',
        'source_sha256': {name: hashlib.sha256((DATA/name).read_bytes()).hexdigest()
                          for name in ['source.parquet', 'validation.parquet']},
        'sql_sha256': {name: hashlib.sha256((ROOT/'src/sql'/name).read_bytes()).hexdigest()
                       for name in ['cmpu_approved_prescription_upload_coverage.sql',
                                    'cmpu_approved_prescription_upload_coverage_validation.sql']},
    }
    write_text(DATA/'analysis.json', json.dumps(metadata, indent=2) + '\n')
    tex = [
        r'Table~\ref{tab:cmpu-approved-prescription-upload-coverage} starts from all vet-diet prescriptions in '
        r'\texttt{EDLDB.BT\_HCA\_HCDM.RXP\_PRESCRIPTIONS} with '
        r'\texttt{IS\_VET\_DIET\_FLAG = TRUE} and '
        r'\texttt{APPROVAL\_CHANNEL = CUSTOMER\_UPLOAD}, created on or after July 30, 2026, 00:00 UTC, '
        r'and shows upload-source coverage by \texttt{PRESCRIPTION\_SOURCE} and current \texttt{RX\_STATUS}. '
        r'All statuses and prescription sources are included; there is no upper creation-date bound. '
        r'Each qualifying prescription counts once.',
        r'\begin{longtable}{@{}llrrrrrrr@{}}',
        r'\caption{Upload-source coverage by prescription source and current status for vet-diet customer-upload prescriptions created on or after July 30, 2026.}',
        r'\label{tab:cmpu-approved-prescription-upload-coverage}\\',
        r'\toprule \shortstack[l]{Prescription\\source} & \texttt{RX\_STATUS} & Eligible & HCDM (\%) & Notification (\%) & Both (\%) & '
        r'\shortstack{HCDM\\only} & \shortstack{Notification\\only} & Neither (\%) \\',
        r'\midrule', r'\endfirsthead',
        r'\toprule \shortstack[l]{Prescription\\source} & \texttt{RX\_STATUS} & Eligible & HCDM (\%) & Notification (\%) & Both (\%) & '
        r'\shortstack{HCDM\\only} & \shortstack{Notification\\only} & Neither (\%) \\',
        r'\midrule', r'\endhead',
    ]
    for row in table.itertuples(index=False, name=None):
        if row[1] == 'All statuses':
            tex.append(r'\midrule')
        labels = ['{' + latex_escape(row[0]) + '}', '{' + latex_escape(row[1]) + '}']
        tex.append(' & '.join([*labels, *[latex_escape(v) for v in row[2:]]]) + r' \\')
        if row[1] == 'All statuses' and row[0] != 'All sources':
            tex.append(r'\addlinespace[2pt]')
    tex.extend([
        r'\bottomrule', r'\end{longtable}',
        r'\Needspace{12\baselineskip}',
        r'\noindent\textit{Notes:} Coverage requires at least one current upload-source entry '
        r'with the same \texttt{rx\_id}. HCDM \texttt{RX\_ID} and notification-service '
        r'\texttt{ASSOCIATED\_RESOURCE\_IDS} are split into individual trimmed IDs; '
        r'NULL, blank and zero tokens are excluded. Each upload source is reduced to a distinct '
        r'set of prescription IDs before joining, so multiple uploads do not increase the prescription count. '
        r'The join uses \texttt{rx\_id} only, without customer, order, upload-date or '
        r'associated-resource-type restrictions. HCDM and Notification count any match in that source '
        r'and overlap. Within each prescription-source/status group, Both, HCDM only, Notification only '
        r'and Neither partition the eligible prescriptions. Percentages use the eligible count on that row. '
        r'All statuses rows are prescription-source subtotals; All sources / All statuses is the overall total. '
        r'Do not add subtotals to their detail rows. The two only columns show counts. '
        r'SQL NULL source or status is retained when present. Percentages may not sum to 100\% after rounding. '
        r'No current match does not establish that an upload never existed. '
        r'The row-level joins and independent Snowflake aggregates agree for every source/status group, '
        r'source subtotal, status subtotal and overall. Extraction: ' +
        latex_escape(timestamps[0]) + r' UTC.',
    ])
    generated = ROOT/'src/autogenerated'/NAME/'coverage.tex'
    generated.parent.mkdir(parents=True, exist_ok=True)
    write_text(generated, '\n'.join(tex) + '\n')
    print(table.to_string(index=False))


if __name__ == '__main__':
    main()

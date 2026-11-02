"""Compare registry approval channels for distinct uploaded vet-diet RX IDs."""
import hashlib
import json
from pathlib import Path

import pandas as pd

from src.python.create_upload_data_verification import SOURCES, latex_escape
from src.python.markdown_tables import markdown_table, write_text

ROOT = Path(__file__).resolve().parents[2]
NAME = 'upload-vet-diet-approval-channels'
DATA = ROOT/'data'/NAME


def main():
    source = pd.read_parquet(DATA/'source.parquet')
    validation = pd.read_parquet(DATA/'validation.parquet')
    for frame in (source, validation):
        frame.columns = frame.columns.str.lower()
    if set(source.source_table) != set(SOURCES):
        raise ValueError('Expected both upload sources')
    if source.rx_id.isna().any() or source.duplicated(['source_table', 'rx_id']).any():
        raise ValueError('Expected one populated prescription ID per source')
    matched = source.matched_rx_id.notna()
    diet = source.is_vet_diet_flag.eq(True).fillna(False)
    non_diet = source.is_vet_diet_flag.eq(False).fillna(False)
    source['match_category'] = 'Unmatched RX_ID'
    source.loc[matched, 'match_category'] = 'Unknown vet-diet flag'
    source.loc[matched & non_diet, 'match_category'] = 'Non-vet diet'
    source.loc[matched & diet, 'match_category'] = 'Vet diet'
    vets = source[source.match_category.eq('Vet diet')].copy()

    def channel(value):
        return '[SQL NULL]' if pd.isna(value) else '[empty string]' if value == '' else str(value)

    vets['channel'] = vets.approval_channel.map(channel)
    expected = {}
    for name, group in source.groupby('source_table'):
        for category, subset in group.groupby('match_category'):
            if category == 'Vet diet':
                for value, count in subset.approval_channel.map(channel).value_counts().items():
                    expected[(name, category, value)] = int(count)
            else:
                expected[(name, category, None)] = len(subset)
    actual = {}
    for row in validation.itertuples():
        if int(row.joined_rows) != int(row.prescriptions):
            raise ValueError('Independent registry join is not unique by prescription ID')
        key = (row.source_table, row.match_category,
               channel(row.approval_channel) if row.match_category == 'Vet diet' else None)
        if key in actual:
            raise ValueError('Duplicate independent validation bucket')
        actual[key] = int(row.prescriptions)
    if expected != actual:
        raise ValueError('Independent warehouse approval-channel or join-coverage counts differ')
    coverage = source.groupby(['source_table', 'match_category']).size().unstack(fill_value=0).reindex(index=SOURCES, fill_value=0)
    categories = ['Vet diet', 'Non-vet diet', 'Unknown vet-diet flag', 'Unmatched RX_ID']
    coverage = coverage.reindex(columns=categories, fill_value=0)
    coverage['All source prescription IDs'] = coverage.sum(axis=1)
    counts = vets.groupby(['channel', 'source_table']).size().unstack(fill_value=0).reindex(columns=SOURCES, fill_value=0)
    counts = counts.loc[counts.sum(axis=1).sort_values(ascending=False).index]
    denominators = {name: int(coverage.loc[name, 'Vet diet']) for name in SOURCES}
    if any(int(counts[name].sum()) != denominators[name] for name in SOURCES):
        raise ValueError('Channel distribution does not reconcile to the matched vet-diet population')
    table = pd.DataFrame({'Approval channel': counts.index})
    for name in SOURCES:
        table[name] = [f'{int(n):,} ({100*int(n)/denominators[name]:.2f}%)' if denominators[name] else '0 (0.00%)'
                       for n in counts[name]]
    differences = counts[SOURCES[1]] - counts[SOURCES[0]]
    table['Difference (notification minus HCDM)'] = [f'{int(n):+,}' if n else '0' for n in differences]
    total_difference = denominators[SOURCES[1]] - denominators[SOURCES[0]]
    if int(differences.sum()) != total_difference:
        raise ValueError('Channel differences do not reconcile to the total difference')
    table.loc[len(table)] = ['Total', *[f'{denominators[name]:,} (100.00%)' for name in SOURCES],
                             f'{total_difference:+,}' if total_difference else '0']
    timestamps = source.extracted_at_utc.unique()
    if len(timestamps) != 1:
        raise ValueError('Expected one extraction timestamp')
    metadata = {
        'extracted_at_utc': str(timestamps[0]),
        'scope': 'All normalized upload-source prescription IDs; matched registry IS_VET_DIET_FLAG = TRUE for channel denominators',
        'join': 'rx_id only; one distinct prescription per source',
        'filters_not_applied': ['creation date', 'prescription source/CMPU', 'approval channel', 'prescription status', 'upload resource type'],
        'denominators': denominators,
        'source_sha256': {name: hashlib.sha256((DATA/name).read_bytes()).hexdigest() for name in ['source.parquet', 'validation.parquet']},
        'sql_sha256': {name: hashlib.sha256((ROOT/'src/sql'/name).read_bytes()).hexdigest()
                       for name in ['upload_vet_diet_approval_channels.sql', 'upload_vet_diet_approval_channels_validation.sql']},
    }
    write_text(DATA/'analysis.json', json.dumps(metadata, indent=2) + '\n')
    notes = ('All distinct normalized prescription IDs in each upload source are joined on rx_id only to '
             'EDLDB.BT_HCA_HCDM.RXP_PRESCRIPTIONS. Approval-channel percentages use only matched '
             'IS_VET_DIET_FLAG = TRUE prescriptions in that source. There are no date, CMPU, channel, '
             'status or upload-resource-type filters. Repeated uploads of the same prescription count once '
             'per source. Missing approval channels are retained; unmatched RX IDs, non-vet-diet matches '
             'and unknown vet-diet flags are excluded from channel denominators and recorded in coverage. '
             'Difference is notification-service count minus HCDM count. '
             f'Extracted: {timestamps[0]} UTC.\n\n')
    target = ROOT/'outputs/tables'/NAME
    target.mkdir(parents=True, exist_ok=True)
    for name, frame in [('approval-channels', table), ('join-coverage', coverage.reset_index())]:
        write_text(target/f'{name}.md', '# Approval channels of uploaded vet-diet prescriptions\n\n' + notes + markdown_table(frame) + '\n')
        frame.to_parquet(DATA/f'{name}.parquet', index=False)
    counts.reset_index().to_parquet(DATA/'channel-counts.parquet', index=False)
    tex = [
        r'Table~\ref{tab:upload-vet-diet-approval-channels} joins all distinct prescription IDs '
        r'in each upload source to \texttt{EDLDB.BT\_HCA\_HCDM.RXP\_PRESCRIPTIONS} '
        r'on \texttt{rx\_id}, then retains matched prescriptions with '
        r'\texttt{IS\_VET\_DIET\_FLAG = TRUE}. Approval channels are taken from the prescription table. '
        r'Each prescription counts once per source, even when it appears in multiple uploads. '
        r'No date, CMPU, approval-channel, status or upload-resource-type filters are applied.',
        r'\begin{longtable}{@{}lrrr@{}}',
        r'\caption{Approval channels of distinct vet-diet prescriptions found in the upload sources.}',
        r'\label{tab:upload-vet-diet-approval-channels}\\', r'\toprule',
        r'Approval channel & \shortstack{\texttt{EDLDB.BT\_HCA\_HCDM.}\\\texttt{rxp\_upload\_entity}\\Prescriptions (\%)} & '
        r'\shortstack{\texttt{rxp\_notification\_service.}\\\texttt{upload\_entity}\\Prescriptions (\%)} & '
        r'\shortstack{Difference\\Notification\\minus HCDM} \\',
        r'\midrule', r'\endfirsthead',
        r'\toprule Approval channel & HCDM prescriptions (\%) & Notification prescriptions (\%) & Difference \\',
        r'\midrule', r'\endhead',
    ]
    for row in table.itertuples(index=False, name=None):
        if row[0] == 'Total':
            tex.append(r'\midrule')
        tex.append('{' + latex_escape(row[0]) + '} & ' + ' & '.join(latex_escape(v) for v in row[1:]) + r' \\')
    first, second = [coverage.loc[name] for name in SOURCES]
    tex.extend([
        r'\bottomrule', r'\end{longtable}',
        r'\noindent\textit{Notes:} Prescription IDs are expanded from HCDM \texttt{RX\_ID} '
        r'and notification-service \texttt{ASSOCIATED\_RESOURCE\_IDS}; missing, blank and zero tokens '
        r'are excluded before joining. Vet-diet classification comes from the prescription registry, '
        r'not the upload resource type. Percentages use the matched vet-diet total in each source. '
        r'The difference is the notification-service count minus the HCDM count. '
        f'The sources contain {int(first["All source prescription IDs"]):,} and '
        f'{int(second["All source prescription IDs"]):,} distinct populated prescription IDs, respectively. '
        f'Excluded non-vet-diet matches: {int(first["Non-vet diet"]):,} and {int(second["Non-vet diet"]):,}; '
        f'unmatched IDs: {int(first["Unmatched RX_ID"]):,} and {int(second["Unmatched RX_ID"]):,}; '
        f'matched IDs with unknown vet-diet flag: {int(first["Unknown vet-diet flag"]):,} and '
        f'{int(second["Unknown vet-diet flag"]):,}. '
        r'Unmatched IDs cannot be assigned a vet-diet category or approval channel from this registry. '
        r'NULL approval channels remain in the distribution when present. '
        r'Both channel counts and join-coverage counts reconcile to independent Snowflake aggregates. '
        r'Percentages may not sum to 100\% because of rounding. Extraction: ' + latex_escape(timestamps[0]) + r' UTC.',
    ])
    generated = ROOT/'src/autogenerated'/NAME/'approval-channels.tex'
    generated.parent.mkdir(parents=True, exist_ok=True)
    write_text(generated, '\n'.join(tex) + '\n')
    print(coverage.to_string())
    print(table.to_string(index=False))


if __name__ == '__main__':
    main()

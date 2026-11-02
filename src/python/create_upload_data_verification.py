"""Compare all upload-source entries by associated_resource_type."""
import hashlib
import json
from pathlib import Path

import click
import pandas as pd

from src.python.create_opportunity_order_cancellation_summary import extract
from src.python.markdown_tables import markdown_table, write_text

ROOT = Path(__file__).resolve().parents[2]
NAME = 'upload-data-verification'
SOURCES = ['EDLDB.BT_HCA_HCDM.rxp_upload_entity',
           'EDLDB.rxp_notification_service.upload_entity']


def latex_escape(value):
    replacements = {'\\': r'\textbackslash{}', '&': r'\&', '%': r'\%',
                    '$': r'\$', '#': r'\#', '_': r'\_', '{': r'\{',
                    '}': r'\}', '~': r'\textasciitilde{}', '^': r'\textasciicircum{}'}
    return ''.join(replacements.get(c, c) for c in str(value))


def comparison(frame):
    """Reconcile separately queried source totals before rendering any output."""
    frame = frame.copy()
    frame.columns = frame.columns.str.lower()
    if set(frame.source_table) != set(SOURCES):
        raise ValueError('Expected exactly the two documented upload sources')
    totals = frame[frame.is_total]
    groups = frame[~frame.is_total]
    if len(totals) != 2 or totals.source_table.duplicated().any():
        raise ValueError('Expected one independent total per source')
    if groups.duplicated(['source_table', 'associated_resource_type']).any():
        raise ValueError('Duplicate resource-type groups')
    if (frame.entry_count < 0).any() or (frame.entry_count % 1 != 0).any():
        raise ValueError('Counts must be nonnegative integers')
    for source in SOURCES:
        actual = int(groups.loc[groups.source_table == source, 'entry_count'].sum())
        expected = int(totals.loc[totals.source_table == source, 'entry_count'].iloc[0])
        if actual != expected:
            raise ValueError(f'Grouped counts do not reconcile for {source}')
    def resource_type(value):
        return None if pd.isna(value) else str(value)

    types = sorted({resource_type(value) for value in groups.associated_resource_type},
                   key=lambda value: (value is None, value or ''))
    # Always expose SQL NULL, including when both sources have zero NULL entries.
    if None not in types:
        types.append(None)
    lookup = {(row.source_table, resource_type(row.associated_resource_type)): int(row.entry_count)
              for row in groups.itertuples()}
    rows = [(kind, *[lookup.get((source, kind), 0) for source in SOURCES]) for kind in types]
    total_counts = [int(totals.loc[totals.source_table == source, 'entry_count'].iloc[0])
                    for source in SOURCES]
    timestamps = frame.extracted_at_utc.unique()
    if len(timestamps) != 1:
        raise ValueError('Expected one extraction timestamp')
    return rows, total_counts, str(timestamps[0])


def render(frame):
    rows, totals, timestamp = comparison(frame)
    formatted = [[('[SQL NULL]' if kind is None else '[empty string]' if kind == '' else kind),
                  f'{first:,}', f'{second:,}'] for kind, first, second in rows]
    formatted.append(['Total', *[f'{value:,}' for value in totals]])
    md = (f'# Upload source verification\n\nExtracted: {timestamp} UTC. '
          'All available physical rows, without filters or deduplication. '
          'Grouped counts reconcile to independently queried source totals.\n\n' +
          markdown_table(pd.DataFrame(formatted, columns=['associated_resource_type', *SOURCES])) + '\n')
    lines = [r'\begin{longtable}{@{}p{0.30\linewidth}rr@{}}',
             r'\caption{Upload-source entries by associated resource type.}',
             r'\label{tab:upload-source-resource-types}\\', r'\toprule',
             r'\texttt{associated\_resource\_type} & '
             r'\shortstack{\texttt{EDLDB.BT\_HCA\_HCDM.}\\\texttt{rxp\_upload\_entity}} & '
             r'\shortstack{\texttt{rxp\_notification\_service.}\\\texttt{upload\_entity}} \\',
             r'\midrule', r'\endfirsthead',
             r'\toprule Resource type & HCDM entries & Notification-service entries \\',
             r'\midrule', r'\endhead']
    for row in formatted:
        if row[0] == 'Total' and row is formatted[-1]:
            lines.append(r'\midrule')
        # Braces prevent a leading '[' from becoming the previous row's
        # optional line-spacing argument (notably our SQL NULL label).
        cells = ['{' + latex_escape(row[0]) + '}', *[latex_escape(value) for value in row[1:]]]
        lines.append(' & '.join(cells) + r' \\')
    lines.extend([r'\bottomrule', r'\end{longtable}',
                  r'\noindent\textit{Extraction:} ' + latex_escape(timestamp) + r' UTC.'])
    return md, '\n'.join(lines) + '\n'


@click.command()
@click.option('--cached', is_flag=True, help='Reuse the fingerprint-verified extract without Snowflake access.')
def main(cached):
    sql_path = ROOT/'src/sql/upload_data_verification.sql'
    sql = sql_path.read_text()
    directory = ROOT/'data'/NAME
    directory.mkdir(parents=True, exist_ok=True)
    parquet, manifest = directory/'source.parquet', directory/'source.json'
    sql_hash = hashlib.sha256(sql.encode()).hexdigest()
    if cached:
        metadata = json.loads(manifest.read_text())
        if metadata['sql_sha256'] != sql_hash or metadata['parquet_sha256'] != hashlib.sha256(parquet.read_bytes()).hexdigest():
            raise click.ClickException('Cached SQL or source differs; rerun without CACHED=1')
    else:
        manifest.unlink(missing_ok=True)
        engine = extract(sql_path, parquet, directory)
        metadata = dict(sql_sha256=sql_hash,
                        parquet_sha256=hashlib.sha256(parquet.read_bytes()).hexdigest(), **engine)
    md, tex = render(pd.read_parquet(parquet))
    if not cached:
        write_text(manifest, json.dumps(metadata, indent=2) + '\n')
    table = ROOT/'outputs/tables'/NAME/'associated-resource-types.md'
    generated = ROOT/'src/autogenerated'/NAME/'associated-resource-types.tex'
    for path, content in [(table, md), (generated, tex)]:
        path.parent.mkdir(parents=True, exist_ok=True)
        write_text(path, content)
    click.echo(f'Verified comparison: {table.relative_to(ROOT)}')


if __name__ == '__main__':
    main()

"""Render the two frozen study-population tables from validated retained summaries."""
import json
from pathlib import Path

import duckdb
import pandas as pd

from src.python.create_opportunity_order_cancellation_summary import digest
from src.python.markdown_tables import markdown_table, write_text

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / 'data'
LABELS = ['All approval channels, matched to first-order lines',
          r'\texttt{CUSTOMER\_UPLOAD}, matched to first-order lines',
          r'\texttt{CUSTOMER\_UPLOAD} aged-cancellation subset']


def replace_rows(text, label, rows):
    """Keep the caption, layout and analyst notes; replace only computed rows."""
    start = text.index(r'\midrule', text.index(r'\label{' + label + '}')) + len(r'\midrule')
    end = text.index(r'\bottomrule', start)
    return text[:start] + '\n' + '\n'.join(rows) + '\n' + text[end:]


def main():
    decisions = DATA / 'cmpu-study-population-prescription-decisions'
    uploads = DATA / 'cmpu-study-population-uploaded-documents'
    # These summaries are regenerated and independently checked by the Make recipe.
    for directory in [decisions, uploads]:
        receipt = json.loads((directory / 'analysis.json').read_text())
        for name, sha in receipt['exports'].items():
            if digest(directory / name) != sha:
                raise ValueError(f'Validated study export fingerprint differs: {directory / name}')
    details = pd.read_parquet(decisions / 'prescriptions.parquet')
    documents = pd.read_parquet(uploads / 'summary.parquet')
    decision_counts = pd.read_parquet(decisions / 'summary.parquet')
    rows = []
    masks = [pd.Series(True, index=details.index), details.approval_channel.eq('CUSTOMER_UPLOAD'),
             details.aged_subset]
    for mask in masks:
        group = details.loc[mask]
        rows.append(dict(prescriptions=group.rx_id.nunique(), orders=group.order_id.nunique(),
                         order_lines=len(group[['order_id', 'order_line_id']].drop_duplicates()),
                         customers=group.customer_id.nunique()))
    counts = pd.DataFrame(rows)
    with duckdb.connect() as connection:
        connection.register('details', details)
        independent = connection.sql("""WITH populations AS (
          SELECT 0 AS population,* FROM details UNION ALL
          SELECT 1,* FROM details WHERE approval_channel='CUSTOMER_UPLOAD' UNION ALL
          SELECT 2,* FROM details WHERE aged_subset
        ) SELECT COUNT(DISTINCT rx_id) prescriptions,COUNT(DISTINCT order_id) orders,
          COUNT(DISTINCT (order_id,order_line_id)) order_lines,COUNT(DISTINCT customer_id) customers
          FROM populations GROUP BY population ORDER BY population""").df()
    pd.testing.assert_frame_equal(counts, independent, check_dtype=False)
    if documents.population.tolist() != decision_counts.population.tolist():
        raise ValueError('Study population row labels differ')
    if not counts.prescriptions.eq(decision_counts.prescriptions).all():
        raise ValueError('Study population denominators differ')
    counts['uploaded_documents'] = documents.uploaded_documents
    counts['accepted_documents'] = documents.accepted_documents
    tables = ROOT / 'outputs/tables/2026-08-15_2026-10-14'
    write_text(tables / 'study-population-counts.md', '# Study population counts\n\n' +
               markdown_table(counts.assign(population=documents.population)) + '\n')
    target = ROOT / 'src/latex/appendix/study_population_analysis.tex'
    text = target.read_text()
    for label, frame in [('tab:study-population-counts', counts),
                         ('tab:study-population-prescription-decisions', decision_counts.drop(columns='population'))]:
        rendered = [name + ' & ' + ' & '.join(f'{int(n):,}' for n in values) + r' \\'
                    for name, values in zip(LABELS, frame.itertuples(index=False, name=None))]
        text = replace_rows(text, label, rendered)
    write_text(target, text)
    print('Rendered both study-population tables from verified retained data.')


if __name__ == '__main__':
    main()

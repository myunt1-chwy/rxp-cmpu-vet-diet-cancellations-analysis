"""Reproduce the contact-window comparison from the verified frequency-study inputs."""
import hashlib
import json
import re

import duckdb
import pandas as pd

from src.python import create_opportunity_contact_frequency_reorders as frequency
from src.python import create_opportunity_aged_customer_contacts as contacts
from src.python import create_opportunity_order_cancellation_summary as base
from src.python.markdown_tables import markdown_table, write_text
from src.python.create_study_population_report_tables import replace_rows

ROOT = base.ROOT
START, END, AS_OF, DAYS = '2026-05-01', '2026-08-01', '2026-10-28', 14


def main():
    directory = ROOT / 'data/opportunity/contact-frequency-reorders' / f'{START}_{END}_{DAYS}d_as-of-{AS_OF}'
    metadata = json.loads((directory / 'source.json').read_text())
    for name, sql in frequency.queries(START, END, AS_OF, DAYS).items():
        if (metadata['identity']['sql_sha256'][name] != hashlib.sha256(sql.encode()).hexdigest()
                or metadata['source_sha256'][name] != base.digest(directory / f'{name}.parquet')):
            raise ValueError('Contact/reorder input fingerprint differs; regenerate the frequency study')
    raw = pd.read_parquet(directory / 'contacts.parquet')
    frames, audit, _ = frequency.analyze(raw, pd.read_parquet(directory / 'reorders.parquet'), START, END, AS_OF, DAYS)
    cf, _, _ = contacts.analyze(raw, START, END)
    detail = cf['contact_details']
    matched = detail.loc[detail.included & detail.relative_day.between(-7, 3), 'customer_id']
    customers = frames['customer_results'].copy()
    customers['contacted_in_window'] = customers.customer_id.isin(matched)
    rows = []
    for flag in [True, False]:
        group = customers.loc[customers.contacted_in_window.eq(flag)]
        n = int(group.reordered.sum())
        rows.append(dict(contacted_in_window=flag, customers=len(group), reordered_customers=n,
                         reorder_rate=100 * n / len(group) if len(group) else None))
    summary = pd.DataFrame(rows)
    # Independently assign the time-window group from timestamps, not Python's day flag.
    with duckdb.connect() as connection:
        connection.register('detail', detail)
        connection.register('customers', customers)
        expected = connection.sql("""WITH contacting AS (
          SELECT DISTINCT customer_id FROM detail WHERE direction='inbound'
          AND contact_customer_id=customer_id AND contact_at_utc IS NOT NULL
          AND contact_at_utc>=cancelled_at_utc-INTERVAL 7 DAY
          AND contact_at_utc<cancelled_at_utc+INTERVAL 4 DAY
        ) SELECT c.customer_id IS NOT NULL contacted_in_window,COUNT(*) customers,
          SUM(CASE WHEN reordered THEN 1 ELSE 0 END) reordered_customers
          FROM customers p LEFT JOIN contacting c USING(customer_id)
          GROUP BY 1 ORDER BY 1 DESC""").df()
    pd.testing.assert_frame_equal(summary.drop(columns='reorder_rate'), expected, check_dtype=False)
    output = ROOT / 'data/opportunity/contact-window-reorders' / f'{START}_{END}_{DAYS}d_as-of-{AS_OF}'
    output.mkdir(parents=True, exist_ok=True)
    customers.to_parquet(output / 'customer-results.parquet', index=False)
    summary.to_parquet(output / 'summary.parquet', index=False)
    write_text(output / 'analysis.json', json.dumps(dict(source_sha256=metadata['source_sha256'],
        audit=audit, independent_verification='DuckDB recomputes contact-window membership and both group counts'), indent=2) + '\n')
    write_text(ROOT / 'outputs/tables/opportunity/2026-05-01_2026-07-31/contact-window-reorders.md',
               '# Contact-window reorder comparison\n\nSame pet/part, 14-day successful reorder endpoint; '
               'contacts on elapsed cancellation days -7 through +3, all inbound handled states.\n\n' + markdown_table(summary) + '\n')
    labels = [r'Contacted on days $-7$ through $+3$', 'Rest of aged cohort']
    rendered = [label + f' & {r.customers:,} & {r.reordered_customers:,} & {r.reorder_rate:.2f}' + r'\% \\'
                for label, r in zip(labels, summary.itertuples())]
    target = ROOT / 'src/latex/appendix/contact_window_reorders.tex'
    text = replace_rows(target.read_text(), 'tab:contact-window-same-pet-part-reorders', rendered)
    # Keep the narrative difference tied to the recomputed percentages.
    difference = summary.reorder_rate.iloc[0] - summary.reorder_rate.iloc[1]
    direction = 'higher' if difference >= 0 else 'lower'
    text = re.sub(r'rate is [\d.]+ percentage points (?:higher|lower)',
                  f'rate is {abs(difference):.2f} percentage points {direction}', text)
    write_text(target, text)
    print(summary.to_string(index=False))


if __name__ == '__main__':
    main()

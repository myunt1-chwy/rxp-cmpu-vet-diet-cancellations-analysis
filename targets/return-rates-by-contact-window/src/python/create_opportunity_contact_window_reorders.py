"""
Reproduce the contact-window comparison from the verified frequency-study
inputs.
"""

import hashlib
import json
import re

import duckdb
import pandas as pd

from shared.python import contact_analysis as contacts
from shared.python import (
    create_opportunity_contact_frequency_reorders as frequency,
)
from shared.python import create_opportunity_order_cancellation_summary as base
from shared.python.latex_table_rows import replace_rows
from shared.python.markdown_tables import markdown_table, write_text
from shared.python.paths import artifact_path
from shared.python.sql_templates import module_sql

ROOT = base.ROOT
START, END, AS_OF, DAYS = "2026-05-01", "2026-08-01", "2026-10-28", 14


def main():
    directory = artifact_path(
        ROOT
        / "data/opportunity/contact-frequency-reorders"
        / f"{START}_{END}_{DAYS}d_as-of-{AS_OF}"
    )
    metadata = json.loads((directory / "source.json").read_text())
    for name, sql in frequency.queries(START, END, AS_OF, DAYS).items():
        if metadata["identity"]["sql_sha256"][name] != hashlib.sha256(
            sql.encode()
        ).hexdigest() or metadata["source_sha256"][name] != base.digest(
            directory / f"{name}.parquet"
        ):
            raise ValueError(
                "Contact/reorder input fingerprint differs; regenerate "
                "the frequency study"
            )
    raw = pd.read_parquet(directory / "contacts.parquet")
    frames, audit, _ = frequency.analyze(
        raw,
        pd.read_parquet(directory / "reorders.parquet"),
        START,
        END,
        AS_OF,
        DAYS,
    )
    cf, _, _ = contacts.analyze(raw, START, END)
    detail = cf["contact_details"]
    matched = detail.loc[
        detail.included & detail.relative_day.between(-7, 3), "customer_id"
    ]
    customers = frames["customer_results"].copy()
    customers["contacted_in_window"] = customers.customer_id.isin(matched)
    rows = []
    for flag in [True, False]:
        group = customers.loc[customers.contacted_in_window.eq(flag)]
        n = int(group.reordered.sum())
        rows.append(
            {
                "contacted_in_window": flag,
                "customers": len(group),
                "reordered_customers": n,
                "reorder_rate": 100 * n / len(group) if len(group) else None,
            }
        )
    summary = pd.DataFrame(rows)
    # Independently assign the time-window group from timestamps, not Python's
    # day flag.
    with duckdb.connect() as connection:
        connection.register("detail", detail)
        connection.register("customers", customers)
        expected = connection.sql(
            module_sql(
                __file__,
                "create_opportunity_contact_window_reorders-query-1.sql.j2",
            )
        ).df()
    pd.testing.assert_frame_equal(
        summary.drop(columns="reorder_rate"), expected, check_dtype=False
    )
    output = artifact_path(
        ROOT
        / "data/opportunity/contact-window-reorders"
        / f"{START}_{END}_{DAYS}d_as-of-{AS_OF}"
    )
    output.mkdir(parents=True, exist_ok=True)
    customers.to_parquet(output / "customer-results.parquet", index=False)
    summary.to_parquet(output / "summary.parquet", index=False)
    write_text(
        output / "analysis.json",
        json.dumps(
            {
                "source_sha256": metadata["source_sha256"],
                "audit": audit,
                "independent_verification": (
                    "DuckDB recomputes contact-window membership and both "
                    "group counts"
                ),
            },
            indent=2,
        )
        + "\n",
    )
    write_text(
        artifact_path(
            ROOT
            / (
                "outputs/tables/opportunity/2026-05-01_2026-07-31/"
                "contact-window-reorders.md"
            )
        ),
        "# Contact-window reorder comparison\n\nSame pet/part, 14-day "
        "successful reorder endpoint; "
        "contacts on elapsed cancellation days -7 through +3, all inbound "
        "handled states.\n\n" + markdown_table(summary) + "\n",
    )
    labels = [r"Contacted on days $-7$ through $+3$", "Rest of aged cohort"]
    rendered = [
        label
        + (
            f" & {r.customers:,} & {r.reordered_customers:,} & "
            f"{r.reorder_rate:.2f}"
        )
        + r"\% \\"
        for label, r in zip(labels, summary.itertuples())
    ]
    target = (
        ROOT
        / "targets/return-rates-by-contact-window/src/latex"
        / "contact_window_reorders.tex"
    )
    text = replace_rows(
        target.read_text(),
        "tab:contact-window-same-pet-part-reorders",
        rendered,
    )
    # Keep the narrative difference tied to the recomputed percentages.
    difference = summary.reorder_rate.iloc[0] - summary.reorder_rate.iloc[1]
    direction = "higher" if difference >= 0 else "lower"
    text = re.sub(
        r"rate is [\d.]+ percentage points (?:higher|lower)",
        f"rate is {abs(difference):.2f} percentage points {direction}",
        text,
    )
    write_text(target, text)
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()

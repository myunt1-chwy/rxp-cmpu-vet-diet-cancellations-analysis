"""Render frozen study-population tables from validated summaries."""

import json
import re

import duckdb
import pandas as pd

from shared.python.create_opportunity_order_cancellation_summary import digest
from shared.python.latex_table_rows import replace_rows
from shared.python.markdown_tables import markdown_table, write_text
from shared.python.paths import artifact_path, repository_root
from shared.python.sql_templates import module_sql

ROOT = repository_root()
# Keep the legacy root path unresolved until each dataset name is appended;
# resolving the directory first routes its children into report/retained.
DATA = ROOT / "data"
LABELS = [
    "All approval channels, matched to first-order lines",
    r"\texttt{CUSTOMER\_UPLOAD}, matched to first-order lines",
    r"\texttt{CUSTOMER\_UPLOAD} aged-cancellation subset",
]


def main():
    decisions = artifact_path(
        DATA / "cmpu-study-population-prescription-decisions"
    )
    uploads = artifact_path(DATA / "cmpu-study-population-uploaded-documents")
    receipts = []
    # These summaries are regenerated and independently checked by the Make
    # recipe.
    for directory in [decisions, uploads]:
        receipt = json.loads((directory / "analysis.json").read_text())
        receipts.append(receipt)
        for name, sha in receipt["exports"].items():
            if digest(directory / name) != sha:
                raise ValueError(
                    f"Validated study export fingerprint differs: "
                    f"{directory / name}"
                )
    line_period = (
        "2026-08-15_2026-10-15_uploads-from-2026-08-01_"
        "uploads-end-2026-10-26_accepted-state-change_order-placed_"
        "block-reasons"
    )
    line_directory = artifact_path(
        ROOT / "data/cmpu-first-order-line-status" / line_period
    )
    line_manifest = json.loads((line_directory / "source.json").read_text())
    financial_directory = artifact_path(
        ROOT / "data/opportunity/prescription-cohort-order-comparison/2026-"
        "08-15_2026-10-15_as-of-2026-10-27"
    )
    financial_manifest = json.loads(
        (financial_directory / "source.json").read_text()
    )
    run_ids = {
        receipts[0].get("refresh_run_id"),
        receipts[1].get("refresh_run_id"),
        line_manifest.get("refresh_run_id"),
        financial_manifest.get("refresh_run_id"),
    }
    if len(run_ids) != 1 or None in run_ids:
        raise ValueError("Study population inputs mix refresh runs")
    details = pd.read_parquet(decisions / "prescriptions.parquet")
    documents = pd.read_parquet(uploads / "summary.parquet")
    decision_counts = pd.read_parquet(decisions / "summary.parquet")
    rows = []
    masks = [
        pd.Series(True, index=details.index),
        details.approval_channel.eq("CUSTOMER_UPLOAD"),
        details.aged_subset,
    ]
    for mask in masks:
        group = details.loc[mask]
        rows.append(
            {
                "prescriptions": group.rx_id.nunique(),
                "orders": group.order_id.nunique(),
                "order_lines": len(
                    group[["order_id", "order_line_id"]].drop_duplicates()
                ),
                "customers": group.customer_id.nunique(),
            }
        )
    counts = pd.DataFrame(rows)
    with duckdb.connect() as connection:
        connection.register("details", details)
        independent = connection.sql(
            module_sql(
                __file__,
                "create_study_population_report_tables-query-1.sql.j2",
            )
        ).df()
    pd.testing.assert_frame_equal(counts, independent, check_dtype=False)
    if documents.population.tolist() != decision_counts.population.tolist():
        raise ValueError("Study population row labels differ")
    if not counts.prescriptions.eq(decision_counts.prescriptions).all():
        raise ValueError("Study population denominators differ")
    counts["uploaded_documents"] = documents.uploaded_documents
    counts["accepted_documents"] = documents.accepted_documents
    tables = artifact_path(ROOT / "outputs/tables/2026-08-15_2026-10-14")
    write_text(
        tables / "study-population-counts.md",
        "# Study population counts\n\n"
        + markdown_table(counts.assign(population=documents.population))
        + "\n",
    )
    target = (
        ROOT
        / "targets/study-population-counts/src/latex"
        / "study_population_analysis.tex"
    )
    text = target.read_text()
    extracted_date = pd.Timestamp(line_manifest["extracted_at_utc"]).strftime(
        "%B %d, %Y"
    )
    text = re.sub(
        r"Line associations and document counts were refreshed on [^\n]+\.",
        (
            "Line associations and document counts were refreshed on "
            f"{extracted_date}."
        ),
        text,
    )
    text = re.sub(
        r"Decisions use the current source snapshot refreshed [^;]+;",
        (
            "Decisions use the current source snapshot refreshed "
            f"{extracted_date};"
        ),
        text,
    )
    for label, frame in [
        ("tab:study-population-counts", counts),
        (
            "tab:study-population-prescription-decisions",
            decision_counts.drop(columns="population"),
        ),
    ]:
        rendered = [
            name + " & " + " & ".join(f"{int(n):,}" for n in values) + r" \\"
            for name, values in zip(
                LABELS, frame.itertuples(index=False, name=None)
            )
        ]
        text = replace_rows(text, label, rendered)
    write_text(target, text)
    print("Rendered both study-population tables from verified retained data.")


if __name__ == "__main__":
    main()

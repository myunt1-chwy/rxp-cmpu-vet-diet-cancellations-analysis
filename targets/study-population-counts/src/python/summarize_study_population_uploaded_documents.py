import sys
from pathlib import Path

from shared.paths import artifact_path
from shared.runtime import digest
from shared.sql_templates import module_sql

sys.path.insert(
    0,
    str(
        next(
            p
            for p in Path(__file__).resolve().parents
            if (p / "analysis.yaml").exists()
        )
    ),
)
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))
import duckdb
import pandas as pd

from shared import upload_entities as entity
from shared.python.markdown_tables import markdown_table, write_text

root = Path.cwd()
directory = artifact_path(
    root / "data/cmpu-study-population-uploaded-documents"
)
metadata = json.loads((directory / "source.json").read_text())
assert digest(directory / "source.parquet") == metadata["parquet_sha256"]
f = pd.read_parquet(directory / "source.parquet").rename(columns=str.lower)
params = entity.parameters(
    "2026-08-15", "2026-10-15", "2026-08-01", "2026-10-27"
)
a, e, audit = entity.validate(f, params)
assert (
    not a.groupby("matched_rx_id")
    .approval_channel.nunique(dropna=False)
    .gt(1)
    .any()
)
matched = a.matched_order_id.notna() & a.matched_order_line_id.notna()
rows = []
for label, mask in [
    ("All approval channels", matched),
    ("CUSTOMER_UPLOAD", matched & a.approval_channel.eq("CUSTOMER_UPLOAD")),
    (
        "CUSTOMER_UPLOAD aged-cancellation subset",
        matched
        & a.approval_channel.eq("CUSTOMER_UPLOAD")
        & a.aged_association,
    ),
]:
    g = a.loc[mask]
    rows.append(
        {
            "population": label,
            "uploaded_documents": g.upload_id.nunique(),
            "accepted_documents": g.loc[
                g.state_name.eq("ACCEPTED"), "upload_id"
            ].nunique(),
        }
    )
summary = pd.DataFrame(rows)
with duckdb.connect() as con:
    con.register("f", f)
    independent = con.sql(
        module_sql(
            __file__,
            "summarize_study_population_uploaded_documents-query-1.sql.j2",
        )
    ).df()
    assert (
        independent.to_numpy().tolist()
        == summary[["uploaded_documents", "accepted_documents"]]
        .to_numpy()
        .tolist()
    )
# Verify that the population rows being extended still match the report.
line_dir = artifact_path(
    root
    / (
        "data/cmpu-first-order-line-status/2026-08-15_2026-10-15_"
        "uploads-from-2026-08-01_uploads-end-2026-10-26_accepted-"
        "state-change_order-placed_block-reasons"
    )
)
line_meta = json.loads((line_dir / "source.json").read_text())
assert digest(line_dir / "source.parquet") == line_meta["parquet_sha256"]
l = pd.read_parquet(line_dir / "source.parquet").rename(columns=str.lower)
matched_lines = l.line_source_rows.gt(0)
assert l.loc[matched_lines, "rx_id"].nunique() == 103516
assert (
    l.loc[
        matched_lines & l.approval_channel.eq("CUSTOMER_UPLOAD"), "rx_id"
    ].nunique()
    == 95073
)
# A source entity can match several prescriptions: never sum upload_count per
# line.
valid_pairs = l.loc[
    matched_lines, ["rx_id", "first_order_id", "first_order_line_id"]
].drop_duplicates()
current = a.loc[
    matched, ["matched_rx_id", "first_order_id", "first_order_line_id"]
].rename(columns={"matched_rx_id": "rx_id"})
assert len(
    current.merge(
        valid_pairs,
        on=["rx_id", "first_order_id", "first_order_line_id"],
        how="inner",
    )
) == len(current)
print(summary.to_string(index=False))
print(
    "Validated entity source, matched first-order membership, baseline "
    "population counts and independent distinct aggregation."
)
# Store a durable execution/derivation receipt with complete records and
# bounded Markdown.
if "--export" in sys.argv:
    a.to_parquet(directory / "associations.parquet", index=False)
    summary.to_parquet(directory / "summary.parquet", index=False)
    audit.to_parquet(directory / "audit.parquet", index=False)
    note = (
        "Counts are distinct UPLOAD_IDs per report row, matched using "
        "expanded RX_ID and numeric customer ID. "
        "Require both matched first-order keys. Accepted documents have "
        "current STATE_NAME = ACCEPTED. "
        "Prescription creation [2026-08-15, 2026-10-15); upload creation "
        "[2026-08-01, 2026-10-26) UTC; "
        "null creation is retained as unknown-window. Aged cancellation <= "
        "2026-10-27 00:00 UTC. "
        "Multiple associations count once per population; entities can belong "
        "to multiple nested populations. "
        f"Query {metadata['query_id']}; extracted "
        f"{metadata['extracted_at_utc']}.\n\n"
    )
    tables = artifact_path(root / "outputs/tables/2026-08-15_2026-10-14")
    tables.mkdir(parents=True, exist_ok=True)
    write_text(
        tables / "study-population-uploaded-documents.md",
        "# Study population uploaded documents\n\n"
        + note
        + markdown_table(summary)
        + "\n",
    )
    write_text(
        directory / "analysis.json",
        json.dumps(
            dict(
                metadata,
                parameters=params,
                baseline_line_source=str(
                    (line_dir / "source.parquet").relative_to(root)
                ),
                baseline_sha256=line_meta["parquet_sha256"],
                exports={
                    name: digest(directory / name)
                    for name in [
                        "associations.parquet",
                        "summary.parquet",
                        "audit.parquet",
                    ]
                },
            ),
            indent=2,
        )
        + "\n",
    )

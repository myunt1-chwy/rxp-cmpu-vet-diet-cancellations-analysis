"""Compare all upload-source entries by associated_resource_type."""

import hashlib
import json

import click
import pandas as pd

from shared.paths import artifact_path, canonical_sql_path, repository_root
from shared.python.create_opportunity_order_cancellation_summary import extract
from shared.python.markdown_tables import markdown_table, write_text

ROOT = repository_root()
NAME = "upload-data-verification"
SOURCES = [
    "EDLDB.BT_HCA_HCDM.rxp_upload_entity",
    "EDLDB.rxp_notification_service.upload_entity",
]


def latex_escape(value):
    replacements = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
    }
    return "".join(replacements.get(c, c) for c in str(value))


def comparison(frame, count_column="entry_count"):
    """
    Reconcile separately queried source totals before rendering any output.
    """
    frame = frame.copy()
    frame.columns = frame.columns.str.lower()
    if set(frame.source_table) != set(SOURCES):
        raise ValueError("Expected exactly the two documented upload sources")
    totals = frame[frame.is_total]
    groups = frame[~frame.is_total]
    if len(totals) != 2 or totals.source_table.duplicated().any():
        raise ValueError("Expected one independent total per source")
    if groups.duplicated(["source_table", "associated_resource_type"]).any():
        raise ValueError("Duplicate resource-type groups")
    values = frame[count_column]
    if values.isna().any() or (values < 0).any() or (values % 1 != 0).any():
        raise ValueError("Counts must be nonnegative integers")
    if (
        "entries_with_nonzero_rx_id" in frame
        and (frame.entries_with_nonzero_rx_id > frame.entry_count).any()
    ):
        raise ValueError(
            "Prescription-linked entry counts exceed total entries"
        )
    for source in SOURCES:
        actual = int(
            groups.loc[groups.source_table == source, count_column].sum()
        )
        expected = int(
            totals.loc[totals.source_table == source, count_column].iloc[0]
        )
        if actual != expected:
            raise ValueError(f"Grouped counts do not reconcile for {source}")

    def resource_type(value):
        return None if pd.isna(value) else str(value)

    types = sorted(
        {resource_type(value) for value in groups.associated_resource_type},
        key=lambda value: (value is None, value or ""),
    )
    # Always expose SQL NULL, including when both sources have zero NULL
    # entries.
    if None not in types:
        types.append(None)
    lookup = {
        (row.source_table, resource_type(row.associated_resource_type)): int(
            getattr(row, count_column)
        )
        for row in groups.itertuples()
    }
    rows = [
        (kind, *[lookup.get((source, kind), 0) for source in SOURCES])
        for kind in types
    ]
    total_counts = [
        int(totals.loc[totals.source_table == source, count_column].iloc[0])
        for source in SOURCES
    ]
    timestamps = frame.extracted_at_utc.unique()
    if len(timestamps) != 1:
        raise ValueError("Expected one extraction timestamp")
    return rows, total_counts, str(timestamps[0])


def render(frame):
    rows, totals, timestamp = comparison(frame)
    rx_rows, rx_totals, _ = comparison(frame, "entries_with_nonzero_rx_id")
    rx_counts = {kind: (first, second) for kind, first, second in rx_rows}
    formatted = [
        [
            (
                "[SQL NULL]"
                if kind is None
                else "[empty string]"
                if kind == ""
                else kind
            ),
            f"{first:,}",
            f"{rx_counts[kind][0]:,}",
            f"{second:,}",
            f"{rx_counts[kind][1]:,}",
        ]
        for kind, first, second in rows
    ]
    formatted.append(
        [
            "Total",
            f"{totals[0]:,}",
            f"{rx_totals[0]:,}",
            f"{totals[1]:,}",
            f"{rx_totals[1]:,}",
        ]
    )
    md = (
        f"# Upload source verification\n\nExtracted: {timestamp} UTC. "
        "All available physical rows, without filters or deduplication. "
        "With Rx ID means at least one populated, non-zero ID in HCDM RX_ID "
        "or notification "
        "ASSOCIATED_RESOURCE_IDS; NULL, blank, empty-list and numeric-zero "
        "tokens are excluded. "
        "Each entry counts once regardless of ID count. Grouped counts "
        "reconcile to "
        "independently queried source totals for both metrics.\n\n"
        + markdown_table(
            pd.DataFrame(
                formatted,
                columns=[
                    "associated_resource_type",
                    f"{SOURCES[0]}: all entries",
                    f"{SOURCES[0]}: with Rx ID",
                    f"{SOURCES[1]}: all entries",
                    f"{SOURCES[1]}: with Rx ID",
                ],
            )
        )
        + "\n"
    )
    lines = [
        r"\begin{longtable}{@{}lrrrr@{}}",
        (
            "\\caption{Upload-source entries and entries with a non-"
            "zero prescription ID, by associated resource type.}"
        ),
        r"\label{tab:upload-source-resource-types}\\",
        r"\toprule",
        (
            " & \\multicolumn{2}{c}{\\shortstack{\\texttt{EDLDB."
            "BT\\_HCA\\_HCDM.}\\\\\\texttt{rxp\\_upload\\_"
            "entity}}} & \\multicolumn{2}{c}{\\shortstack{\\text"
            "tt{rxp\\_notification\\_service.}\\\\\\texttt{uploa"
            "d\\_entity}}} \\\\"
        ),
        r"\cmidrule(lr){2-3}\cmidrule(lr){4-5}",
        (
            r"\texttt{associated\_resource\_type} & All entries & With Rx ID "
            r"& All entries & With Rx ID \\"
        ),
        r"\midrule",
        r"\endfirsthead",
        (
            r"\toprule Resource type & HCDM total & With Rx ID & Notification "
            r"total & With Rx ID \\"
        ),
        r"\midrule",
        r"\endhead",
    ]
    for row in formatted:
        if row[0] == "Total" and row is formatted[-1]:
            lines.append(r"\midrule")
        # Braces prevent a leading '[' from becoming the previous row's
        # optional line-spacing argument (notably our SQL NULL label).
        cells = [
            "{" + latex_escape(row[0]) + "}",
            *[latex_escape(value) for value in row[1:]],
        ]
        lines.append(" & ".join(cells) + r" \\")
    lines.extend(
        [
            r"\bottomrule",
            r"\end{longtable}",
            r"\noindent\textit{Extraction:} "
            + latex_escape(timestamp)
            + r" UTC.",
        ]
    )
    return md, "\n".join(lines) + "\n"


@click.command()
@click.option(
    "--cached",
    is_flag=True,
    help="Reuse the fingerprint-verified extract without Snowflake access.",
)
def main(cached):
    sql_path = canonical_sql_path("upload_data_verification.sql")
    sql = sql_path.read_text()
    directory = artifact_path(ROOT / "data" / NAME)
    directory.mkdir(parents=True, exist_ok=True)
    parquet, manifest = directory / "source.parquet", directory / "source.json"
    sql_hash = hashlib.sha256(sql.encode()).hexdigest()
    if cached:
        metadata = json.loads(manifest.read_text())
        if (
            metadata["sql_sha256"] != sql_hash
            or metadata["parquet_sha256"]
            != hashlib.sha256(parquet.read_bytes()).hexdigest()
        ):
            raise click.ClickException(
                "Cached SQL or source differs; rerun without CACHED=1"
            )
    else:
        manifest.unlink(missing_ok=True)
        engine = extract(sql_path, parquet, directory)
        metadata = dict(
            sql_sha256=sql_hash,
            parquet_sha256=hashlib.sha256(parquet.read_bytes()).hexdigest(),
            **engine,
        )
    md, tex = render(pd.read_parquet(parquet))
    if not cached:
        write_text(manifest, json.dumps(metadata, indent=2) + "\n")
    table = artifact_path(
        ROOT / "outputs/tables" / NAME / "associated-resource-types.md"
    )
    generated = artifact_path(
        ROOT / "src/autogenerated" / NAME / "associated-resource-types.tex"
    )
    for path, content in [(table, md), (generated, tex)]:
        path.parent.mkdir(parents=True, exist_ok=True)
        write_text(path, content)
    click.echo(f"Verified comparison: {table.relative_to(ROOT)}")


if __name__ == "__main__":
    main()

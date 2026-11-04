"""Render UTC creation-time coverage from the retained source aggregates."""

import hashlib
import json

import pandas as pd
from shared.python.create_upload_data_verification import SOURCES, latex_escape

from shared.paths import artifact_path, canonical_sql_path, repository_root
from shared.python.markdown_tables import markdown_table, write_text

ROOT = repository_root()
NAME = "upload-source-time-coverage"
DATA = artifact_path(ROOT / "data" / NAME)


def main():
    frame = pd.read_parquet(artifact_path(DATA / "source.parquet"))
    frame.columns = frame.columns.str.lower()
    if set(frame.source_table) != set(SOURCES):
        raise ValueError("Expected both upload sources")
    frame["type_key"] = frame.associated_resource_type.map(
        lambda x: None if pd.isna(x) else str(x)
    )
    if frame.duplicated(
        ["source_table", "associated_resource_type", "is_overall"]
    ).any():
        raise ValueError("Duplicate source/resource groups")
    for field in ["min_created_utc_ts", "max_created_utc_ts"]:
        frame[field] = pd.to_datetime(frame[field])
    if (frame.timestamp_count > frame.entry_count).any():
        raise ValueError("Timestamp counts exceed source counts")
    for row in frame.itertuples():
        missing = pd.isna(row.min_created_utc_ts) or pd.isna(
            row.max_created_utc_ts
        )
        if row.timestamp_count == 0:
            if not (
                pd.isna(row.min_created_utc_ts)
                and pd.isna(row.max_created_utc_ts)
            ):
                raise ValueError(
                    "Empty timestamp population has non-null extrema"
                )
        elif missing or row.min_created_utc_ts > row.max_created_utc_ts:
            raise ValueError("Invalid timestamp range")
    groups = frame[~frame.is_overall]
    overall = frame[frame.is_overall].set_index("source_table")
    if len(overall) != 2:
        raise ValueError("Expected one overall row per source")
    for source in SOURCES:
        subset, total = (
            groups[groups.source_table == source],
            overall.loc[source],
        )
        if any(
            int(subset[field].sum()) != int(total[field])
            for field in ["entry_count", "timestamp_count"]
        ):
            raise ValueError(
                "Resource-group counts do not reconcile to overall counts"
            )
        for field, aggregate in [
            ("min_created_utc_ts", "min"),
            ("max_created_utc_ts", "max"),
        ]:
            calculated = getattr(subset[field], aggregate)()
            if (
                not (pd.isna(calculated) and pd.isna(total[field]))
                and calculated != total[field]
            ):
                raise ValueError(
                    "Resource-group extrema do not reconcile to overall "
                    "extrema"
                )
    timestamps = frame.extracted_at_utc.unique()
    if len(timestamps) != 1:
        raise ValueError("Expected one extraction timestamp")

    def stamp(value):
        if pd.isna(value):
            return "[No timestamp]"
        # Round half a second upward; retain the original nanosecond values in
        # source.parquet and use exact values for the coverage reconciliation.
        rounded = (value + pd.Timedelta(milliseconds=500)).floor("s")
        return rounded.strftime("%Y-%m-%d %H:%M:%S")

    def kind(value):
        return None if pd.isna(value) else str(value)

    lookup = {
        (row.source_table, kind(row.associated_resource_type)): row
        for row in groups.itertuples()
    }
    types = sorted(
        {kind(v) for v in groups.associated_resource_type},
        key=lambda v: (v is None, v or ""),
    )
    rows = []
    for resource in types:
        values = []
        for source in SOURCES:
            row = lookup.get((source, resource))
            values.extend(
                [stamp(row.min_created_utc_ts), stamp(row.max_created_utc_ts)]
                if row
                else ["[No entries]"] * 2
            )
        rows.append(["[SQL NULL]" if resource is None else resource, *values])
    rows.append(
        [
            "Overall",
            *[
                stamp(overall.loc[source, field])
                for source in SOURCES
                for field in ["min_created_utc_ts", "max_created_utc_ts"]
            ],
        ]
    )
    columns = [
        "associated_resource_type",
        *[
            f"{source}: {bound} created UTC"
            for source in SOURCES
            for bound in ["Minimum", "Maximum"]
        ],
    ]
    table = pd.DataFrame(rows, columns=columns)
    missing_counts = [
        int(
            overall.loc[source, "entry_count"]
            - overall.loc[source, "timestamp_count"]
        )
        for source in SOURCES
    ]
    notes = (
        "All current source entries, without date, order-ID or "
        "prescription-ID filters. "
        "HCDM uses CREATED_TS_UTC; notification-service CREATED_AT is "
        "converted to UTC. "
        "MIN/MAX ignore SQL NULL timestamps. Displayed extrema are rounded to "
        "the nearest "
        "second (half seconds round upward); the source extract retains full "
        "precision. "
        "Observed extrema describe available entries, "
        "not guaranteed continuous coverage or full system history. "
        f"Missing creation timestamps: HCDM {missing_counts[0]:,}; "
        f"notification service {missing_counts[1]:,}. "
        f"Extracted: {timestamps[0]} UTC.\n\n"
    )
    target = artifact_path(
        ROOT / "outputs/tables" / NAME / "created-time-coverage.md"
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    write_text(
        target,
        "# Upload creation-time coverage\n\n"
        + notes
        + markdown_table(table)
        + "\n",
    )
    table.to_parquet(
        artifact_path(DATA / "created-time-coverage.parquet"), index=False
    )
    metadata = {
        "extracted_at_utc": str(timestamps[0]),
        "source_sha256": hashlib.sha256(
            (artifact_path(DATA / "source.parquet")).read_bytes()
        ).hexdigest(),
        "sql_sha256": hashlib.sha256(
            (
                canonical_sql_path("upload_source_time_coverage.sql")
            ).read_bytes()
        ).hexdigest(),
    }
    write_text(
        artifact_path(DATA / "analysis.json"),
        json.dumps(metadata, indent=2) + "\n",
    )
    tex = [
        r"\Needspace{20\baselineskip}",
        (
            "Table~\\ref{tab:upload-source-time-coverage} shows "
            "the minimum and maximum creation timestamps of the "
            "entries currently available in each source, by "
            "resource type and overall. All timestamps are "
            "shown in UTC."
        ),
        r"\begin{longtable}{@{}lcccc@{}}",
        (
            "\\caption{Creation-time coverage of current upload-"
            "source entries (UTC).}"
        ),
        r"\label{tab:upload-source-time-coverage}\\",
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
            r"Resource type & Minimum created & Maximum created & Minimum "
            r"created & Maximum created \\"
        ),
        r"\midrule",
        r"\endfirsthead",
        (
            r"\toprule Resource type & HCDM min & HCDM max & Notification min "
            r"& Notification max \\"
        ),
        r"\midrule",
        r"\endhead",
    ]
    for row in rows:
        if row[0] == "Overall":
            tex.append(r"\midrule")
        cells = ["{" + latex_escape(row[0]) + "}"]
        for value in row[1:]:
            cells.append(
                r"\shortstack{"
                + latex_escape(value).replace(" ", r"\\", 1)
                + "}"
            )
        tex.append(" & ".join(cells) + r" \\")
    tex.extend(
        [
            r"\bottomrule",
            r"\end{longtable}",
            (
                "\\noindent\\textit{Notes:} No date, order-ID or pre"
                "scription-ID filters are applied. HCDM uses \\text"
                "tt{CREATED\\_TS\\_UTC}; notification-service \\textt"
                "t{CREATED\\_AT} is converted to UTC before aggrega"
                "tion. Minimum and maximum ignore missing timestam"
                "ps. Displayed values are rounded to the nearest s"
                "econd (half seconds round upward); the retained e"
                "xtract preserves full precision. Missing creation"
                " timestamps: "
                f"{missing_counts[0]:,}"
                " in HCDM and "
                f"{missing_counts[1]:,}"
                " in the notification-service source. The ranges d"
                "escribe available entries, without establishing c"
                "ontinuous coverage or the full history of either "
                "system. Extraction: "
            )
            + latex_escape(timestamps[0])
            + r" UTC.",
        ]
    )
    generated = artifact_path(
        ROOT / "src/autogenerated" / NAME / "created-time-coverage.tex"
    )
    generated.parent.mkdir(parents=True, exist_ok=True)
    write_text(generated, "\n".join(tex) + "\n")
    print(table.to_string(index=False))


if __name__ == "__main__":
    main()

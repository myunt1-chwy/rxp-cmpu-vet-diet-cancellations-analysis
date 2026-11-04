"""
First-order-line upload coverage by reason and status in the validated study.
"""

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import duckdb
import pandas as pd

from shared import upload_entities as entity
from shared.paths import artifact_path
from shared.python import create_opportunity_order_cancellation_summary as base
from shared.python import (
    summarize_study_population_prescription_decisions as decisions,
)
from shared.python.markdown_tables import markdown_table, write_text
from shared.sql_templates import module_sql

ROOT = base.ROOT
DATA = ROOT / "data"
NAME = "study-upload-coverage-by-cancel-reason"
PERIOD = "2026-08-15_2026-10-14"
BASELINE = artifact_path(
    DATA
    / (
        "cmpu-first-order-line-status/2026-08-15_2026-10-15_uploads-"
        "from-2026-08-01_uploads-end-2026-10-26_accepted-state-"
        "change_order-placed_block-reasons"
    )
)
KEYS = ["order_id", "order_line_id"]
MATCH = ["rx_id", "customer_id"] + KEYS
CUTOFF = pd.Timestamp("2026-10-27", tz="UTC")
PARAMS = entity.parameters(
    "2026-08-15", "2026-10-15", "2026-08-01", "2026-10-27"
)
VERIFY_SQL = module_sql(
    __file__, "create_study_upload_coverage_by_cancel_reason-query-1.sql.j2"
)


def load_source(directory):
    metadata = json.loads((directory / "source.json").read_text())
    source = directory / "source.parquet"
    if base.digest(source) != metadata["parquet_sha256"]:
        raise ValueError(f"Source fingerprint differs: {source}")
    if (
        hashlib.sha256(metadata["sql"].encode()).hexdigest()
        != metadata["sql_sha256"]
    ):
        raise ValueError(f"Source SQL fingerprint differs: {directory}")
    return pd.read_parquet(source).rename(columns=str.lower), metadata


def reason_key(series):
    return (
        series.astype("string")
        .str.strip()
        .str.casefold()
        .replace("", pd.NA)
        .fillna(base.MISSING_REASON)
    )


def analyze(baseline, decision_source, upload_source):
    matched = baseline.loc[baseline.line_source_rows.gt(0)].copy()
    if (
        not matched.rx_id.is_unique
        or not matched.cancel_reason_variants.eq(1).all()
    ):
        raise ValueError(
            "Conflicting validated prescription or cancellation membership"
        )
    if not matched.line_status_variants.eq(1).all():
        raise ValueError("Conflicting validated shipment-to-line statuses")
    if (
        matched.matched_order_id.ne(matched.first_order_id).any()
        or matched.matched_order_line_id.ne(matched.first_order_line_id).any()
    ):
        raise ValueError("Validated first-order keys disagree")
    # All consumers must use exactly the refreshed matched population.
    omitted = decision_source.loc[
        ~decision_source.rx_id.isin(matched.rx_id)
    ].copy()
    if not omitted.empty:
        raise ValueError("Decision membership exceeds the population")
    details, _ = decisions.summarize(decision_source.copy())
    check = details.merge(
        matched[
            [
                "rx_id",
                "customer_id",
                "first_order_id",
                "first_order_line_id",
                "approval_channel",
                "order_cancel_reason",
            ]
        ],
        on="rx_id",
        suffixes=("", "_baseline"),
        how="outer",
        validate="one_to_one",
        indicator=True,
    )
    if not check["_merge"].eq("both").all():
        raise ValueError("Decision source does not cover the validated study")
    for col in [
        "customer_id",
        "first_order_id",
        "first_order_line_id",
        "approval_channel",
    ]:
        if not check[col].eq(check[col + "_baseline"]).all():
            raise ValueError(
                f"Validated {col} differs from the decision source"
            )
    changed = ~reason_key(check.cancel_reason).eq(
        reason_key(check.order_cancel_reason)
    )
    if changed.any():
        raise ValueError("A populated validated cancellation reason changed")
    reason_differences = check.loc[
        changed & check.approval_channel.eq("CUSTOMER_UPLOAD"),
        [
            "rx_id",
            "customer_id",
            "first_order_id",
            "first_order_line_id",
            "order_cancel_reason",
            "cancel_reason",
            "cancel_time",
        ],
    ].copy()
    study = details.loc[
        details.approval_channel.eq("CUSTOMER_UPLOAD"),
        MATCH + ["cancel_reason", "cancel_time"],
    ].copy()
    study["reason_key"] = reason_key(study.cancel_reason)
    if study[MATCH].isna().any().any() or study.duplicated(KEYS).any():
        raise ValueError(
            "Missing or non-unique validated first-order-line identity"
        )
    associations, _, entity_audit = entity.validate(upload_source, PARAMS)
    uploads = associations.loc[
        associations.approval_channel.eq("CUSTOMER_UPLOAD")
        & associations.matched_order_id.notna()
        & associations.matched_order_line_id.notna(),
        [
            "matched_rx_id",
            "rx_customer_id",
            "matched_order_id",
            "matched_order_line_id",
            "upload_id",
            "state_name",
            "created_ts_utc",
            "state_changed_ts_utc",
            "order_cancel_reason",
            "order_cancel_time",
        ],
    ].rename(
        columns=dict(
            zip(
                [
                    "matched_rx_id",
                    "rx_customer_id",
                    "matched_order_id",
                    "matched_order_line_id",
                ],
                MATCH,
            )
        )
    )
    for frame in [study, uploads]:
        frame["rx_id"] = frame.rx_id.astype("string").str.strip()
        for col in MATCH[1:]:
            frame[col] = frame[col].map(base.identifier)
    linked = uploads.merge(
        study[MATCH + ["reason_key", "cancel_time"]],
        on=MATCH,
        how="left",
        validate="many_to_one",
        indicator=True,
    )
    if not linked["_merge"].eq("both").all():
        raise ValueError(
            "Upload association is outside the validated first-order study"
        )
    if (
        not reason_key(linked.order_cancel_reason).eq(linked.reason_key).all()
        or not (
            linked.order_cancel_time.eq(linked.cancel_time)
            | (linked.order_cancel_time.isna() & linked.cancel_time.isna())
        ).all()
    ):
        raise ValueError("Upload and validated cancellation evidence disagree")
    uploads = uploads.drop_duplicates(MATCH + ["upload_id"]).copy()
    study["cancellation_reason"] = study.reason_key
    outside = study.reason_key.eq("aged order") & (
        study.cancel_time.isna() | study.cancel_time.gt(CUTOFF)
    )
    study.loc[outside, "cancellation_reason"] = "[Aged order outside cutoff]"
    statuses = matched[
        [
            "rx_id",
            "customer_id",
            "first_order_id",
            "first_order_line_id",
            "order_line_status",
        ]
    ].rename(
        columns={
            "first_order_id": "order_id",
            "first_order_line_id": "order_line_id",
            "order_line_status": "line_item_status",
        }
    )
    statuses["rx_id"] = statuses.rx_id.astype("string").str.strip()
    for col in MATCH[1:]:
        statuses[col] = statuses[col].map(base.identifier)
    statuses["line_item_status"] = (
        statuses.line_item_status.astype("string")
        .str.strip()
        .str.upper()
        .replace("", pd.NA)
        .fillna("[Missing]")
    )
    study_with_status = study.merge(
        statuses, on=MATCH, how="left", validate="one_to_one", indicator=True
    )
    if not study_with_status["_merge"].eq("both").all():
        raise ValueError(
            "Validated line status does not cover every study identity"
        )
    study_with_status = study_with_status.drop(columns="_merge")
    joined = study_with_status.merge(
        uploads, on=MATCH, how="left", validate="one_to_many"
    )

    def counts(group, label, status, row_type):
        with_upload = group.upload_id.notna()
        n = len(group[KEYS].drop_duplicates())
        covered = len(group.loc[with_upload, KEYS].drop_duplicates())
        return {
            "row_type": row_type,
            "cancellation_reason": label,
            "line_item_status": status,
            "orders": group.order_id.nunique(),
            "prescriptions": group.rx_id.nunique(),
            "line_items": n,
            "lines_with_upload": covered,
            "uploads": group.upload_id.nunique(),
            "accepted_uploads": group.loc[
                group.state_name.eq("ACCEPTED"), "upload_id"
            ].nunique(),
            "rejected_uploads": group.loc[
                group.state_name.eq("REJECTED"), "upload_id"
            ].nunique(),
            "upload_coverage_pct": 100 * covered / n if n else float("nan"),
        }

    rows = [
        counts(group, label, status, "reason")
        for (label, status), group in joined.groupby(
            ["cancellation_reason", "line_item_status"]
        )
    ]
    rows.append(counts(joined, "TOTAL", "All", "total"))
    summary = (
        pd.DataFrame(rows)
        .sort_values(["row_type", "cancellation_reason", "line_item_status"])
        .reset_index(drop=True)
    )
    with duckdb.connect() as connection:
        connection.execute("SET TimeZone='UTC'")
        connection.register("study", study_with_status)
        connection.register("uploads", uploads)
        independent = connection.execute(VERIFY_SQL).df()
    pd.testing.assert_frame_equal(
        summary, independent, check_dtype=False, atol=1e-10, rtol=0
    )
    total = summary.iloc[-1]
    if (
        total.prescriptions != study.rx_id.nunique()
        or total.line_items != study[KEYS].drop_duplicates().shape[0]
        or total.orders != study.order_id.nunique()
    ):
        raise ValueError("Coverage totals do not match refreshed membership")
    if (
        not summary.loc[summary.line_items.gt(0), "upload_coverage_pct"]
        .between(0, 100)
        .all()
    ):
        raise ValueError("Upload coverage outside 0--100%")
    if (
        not summary.loc[
            summary.row_type.eq("reason"),
            ["prescriptions", "line_items", "lines_with_upload"],
        ]
        .sum()
        .eq(total[["prescriptions", "line_items", "lines_with_upload"]])
        .all()
    ):
        raise ValueError(
            "Reason/status line counts do not partition the study"
        )
    audit = {
        "excluded_newly_linked_decision_rows": len(omitted),
        "population_lines_with_newly_populated_reason": len(
            reason_differences
        ),
        "raw_upload_rows": len(upload_source),
        "eligible_upload_associations": len(uploads),
        "missing_upload_creation_dates": int(
            uploads.loc[uploads.created_ts_utc.isna(), "upload_id"].nunique()
        ),
        "uploads_in_multiple_reason_groups": int(
            joined.dropna(subset=["upload_id"])
            .groupby("upload_id")
            .cancellation_reason.nunique()
            .gt(1)
            .sum()
        ),
        "orders_in_multiple_reason_groups": int(
            study.groupby("order_id").cancellation_reason.nunique().gt(1).sum()
        ),
        "entity_audit": entity_audit.to_dict("records"),
        ("independent_verification"): (
            "All reason/status and TOTAL counts and coverage agree with DuckDB"
        ),
    }
    return {
        "study_lines": study,
        "upload_associations": uploads,
        "summary": summary,
        "study_status_lines": study_with_status,
        "excluded_decisions": omitted,
        "reason_snapshot_differences": reason_differences,
    }, audit


def latex_rows(summary):
    rows = []
    for r in summary.itertuples():
        label = (
            r.cancellation_reason
            if r.cancellation_reason.startswith("[") or r.row_type == "total"
            else r.cancellation_reason.capitalize()
        )
        label = (
            label.replace("&", r"\&").replace("_", r"\_").replace("%", r"\%")
        )
        if r.row_type == "total":
            rows.append(r"\midrule")
        if r.cancellation_reason == "aged order":
            rows.append(r"\rowcolor{yellow!35}")
        status = r.line_item_status.replace("_", r"\_")
        rows.append(
            "{"
            + label
            + "}"
            + (
                f" & {status} & {r.orders:,} & {r.prescriptions:,} & "
                f"{r.line_items:,} & {r.lines_with_upload:,} & "
                f"{r.upload_coverage_pct:.2f}"
            )
            + r"\%"
            + (
                f" & {r.uploads:,} & {r.accepted_uploads:,} & "
                f"{r.rejected_uploads:,}"
            )
            + r" \\"
        )
    return "\n".join(rows)


def latex_table(summary):
    return (
        (
            "% Generated by make study-upload-coverage-by-cancel-"
            "reason.\n\\clearpage\n\\begin{landscape}\n\\subsubsecti"
            "on{What is the percentage of prescription "
            "upload?}\\label{subsec:study-upload-"
            "coverage}\nTable~\\ref{tab:study-upload-coverage-by-"
            "cancellation-reason} reports upload coverage\nfor the "
            "study's first orders and first-order lines, by "
            "cancellation reason and line-item "
            "status.\n\\begin{table}[!htbp]\n\\centering\n\\caption{"
            "Prescription upload coverage by first-order "
            "cancellation reason and line-item status: CMPU vet-"
            "diet CUSTOMER\\_UPLOAD prescriptions created August 15-"
            "-October 14, 2026, inclusive, UTC.}\n\\label{tab:study-"
            "upload-coverage-by-cancellation-"
            "reason}\n\\small\n\\setlength{\\tabcolsep}{6pt}\n\\begi"
            "n{tabular}{@{}llrrrrrrrr@{}}\n\\toprule\nCancellation "
            "reason & \\shortstack{Line-item\\\\status} & "
            "\\shortstack{First\\\\orders} & Prescriptions & "
            "\\shortstack{First-order\\\\line items} & "
            "\\shortstack{Line items\\\\with upload} & "
            "\\shortstack{Upload\\\\coverage (\\%)} & "
            "\\shortstack{Total\\\\uploads} & "
            "\\shortstack{Accepted\\\\uploads} & "
            "\\shortstack{Rejected\\\\uploads} \\\\\n\\midrule\n"
        )
        + latex_rows(summary)
        + (
            "\n\\bottomrule\n\\end{tabular}\n\\begin{minipage}{\\lin"
            "ewidth}\n\\footnotesize\n\\textit{Notes:} Coverage = "
            "100 $\\times$ distinct first-order lines with at "
            "least\none matched upload $\\div$ all study first-"
            "order lines in that reason/status group, "
            "including\nlines without uploads. Prescriptions count "
            "distinct \\texttt{RX\\_ID}s and equal\nline-item "
            "counts in this validated one-prescription-per-first-order-"
            "line cohort.\nOrders and physical order/line pairs "
            "count distinctly;\nshipment rows cannot multiply "
            "counts. The validated population is the same "
            "as\nTable~\\ref{tab:study-population-counts}.\nUploads are "
            "distinct \\texttt{UPLOAD\\_ID}s from "
            "HCDM\n\\texttt{rxp\\_upload\\_entity}, restricted to "
            "\\texttt{DIET\\_PRESCRIPTION} entities.\nExpand "
            "prescription IDs and match both prescription and "
            "numeric customer IDs,\nthen both first-order keys. "
            "Upload discovery is August 1--October 25 "
            "inclusive,\nUTC; missing creation timestamps follow "
            "the existing study's unknown-window rule\nand are "
            "audited. No requirement that upload precede "
            "cancellation is imposed.\nAccepted and rejected refer "
            "to current entity \\texttt{STATE\\_NAME=ACCEPTED} "
            "and\n\\texttt{REJECTED}, not prescription approval or "
            "denial. Other entity states\nremain in Total uploads, "
            "so Accepted plus Rejected need not equal "
            "Total.\nReasons are trimmed and case-insensitive. Aged "
            "order uses the inclusive\nOctober 27, 2026, 00:00 UTC "
            "cancellation cutoff; later or undated aged "
            "reasons\nremain in the outside-cutoff row. Missing/"
            "blank reasons do not prove an uncancelled\norder. Line-"
            "item status is \\texttt{ORDER\\_ORDER\\_LINE\\_STATUS} "
            "from the coordinated first-order-line "
            "extract, with shipment-row consistency checked.\nCodes "
            "are shown as recorded; missing status is explicit. "
            "Table~\\ref{tab:study-no-cancellation-upload-"
            "details}\nuses a later status/reason extraction, so "
            "its counts can differ.\nAn entity may match multiple "
            "prescriptions/lines and reason/status groups;\nan "
            "order can also span groups. TOTAL independently "
            "deduplicates both and is not\nthe sum of overlapping "
            "rows. Cancellation reasons/times use the "
            "retained\nprescription-decision extract and agree with "
            "the upload extract; originally blank\nreasons "
            "populated since the earlier membership snapshot are "
            "audited separately.\nCounts describe the retained "
            "source snapshots.\n\\end{minipage}\n\\end{table}\n\\end"
            "{landscape}\n\\input{../autogenerated/study_no_"
            "cancellation_upload_details}\n\\clearpage\n"
        )
    )


def main():
    sources = {
        "baseline": BASELINE,
        "decisions": artifact_path(
            DATA / "cmpu-study-population-prescription-decisions"
        ),
        "uploads": artifact_path(
            DATA / "cmpu-study-population-uploaded-documents"
        ),
    }
    loaded = {
        name: load_source(directory) for name, directory in sources.items()
    }
    run_ids = {value[1].get("refresh_run_id") for value in loaded.values()}
    if len(run_ids) != 1 or None in run_ids:
        raise ValueError("Upload coverage inputs mix refresh runs")
    for name in ["decisions", "uploads"]:
        if (
            loaded[name][1].get("population_dependency_sha256")
            != (loaded["baseline"][1]["parquet_sha256"])
        ):
            raise ValueError("Coverage population dependency differs")
    frames, audit = analyze(
        *(loaded[name][0] for name in ["baseline", "decisions", "uploads"])
    )
    output = artifact_path(DATA / NAME / PERIOD)
    output.mkdir(parents=True, exist_ok=True)
    for name, frame in frames.items():
        frame.to_parquet(
            output / f"{name.replace('_', '-')}.parquet", index=False
        )
    write_text(output / "verification.sql", VERIFY_SQL + ";\n")
    write_text(output / "audit.json", json.dumps(audit, indent=2) + "\n")
    write_text(
        output / "analysis.json",
        json.dumps(
            {
                "generated_at_utc": datetime.now(UTC).isoformat(),
                "version": 3,
                "refresh_run_id": next(iter(run_ids)),
                "generator_sha256": base.digest(Path(__file__)),
                "parameters": PARAMS,
                "coverage_definition": (
                    "100 * distinct first-order lines with an upload / all "
                    "study first-order lines in the reason/status group"
                ),
                "sources": {
                    name: dict(
                        path=str(sources[name].relative_to(ROOT)),
                        **loaded[name][1],
                    )
                    for name in loaded
                },
                "exports": {
                    p.name: base.digest(p) for p in output.glob("*.parquet")
                },
            },
            indent=2,
        )
        + "\n",
    )
    write_text(
        artifact_path(ROOT / "outputs/tables" / PERIOD / f"{NAME}.md"),
        "# Prescription upload coverage by cancellation reason and line-item "
        "status\n\n"
        "Validated CUSTOMER_UPLOAD first-order study; percentage is line-item "
        "coverage, not uploads divided by lines. "
        "Upload discovery [2026-08-01,2026-10-26) UTC; aged cutoff 2026-10-27 "
        "00:00 UTC. "
        "Line-item status is from the coordinated first-order extraction. "
        "Prescriptions count distinct RX_IDs, equal to line counts in this "
        "validated cohort. "
        "TOTAL deduplicates entities/orders across reason/status groups. "
        "Accepted/rejected are current entity states.\n\n"
        + markdown_table(frames["summary"])
        + "\n",
    )
    write_text(
        artifact_path(
            ROOT
            / "targets/report/src/latex/retained/appendix"
            / "study_upload_coverage_by_cancel_reason.tex"
        ),
        latex_table(frames["summary"]),
    )
    print(frames["summary"].to_string(index=False))


if __name__ == "__main__":
    main()

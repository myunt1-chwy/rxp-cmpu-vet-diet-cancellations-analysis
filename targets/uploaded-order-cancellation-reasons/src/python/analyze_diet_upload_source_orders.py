"""
Compare ECOM cancellation reasons for diet-upload source order populations.
"""

import hashlib
import json

import pandas as pd
from shared.python.analyze_null_resource_uploads import numeric_id
from shared.python.create_upload_data_verification import SOURCES, latex_escape

from shared.paths import artifact_path, canonical_sql_path, repository_root
from shared.python.markdown_tables import markdown_table, write_text

ROOT = repository_root()
NAME = "diet-upload-source-cancellation-reasons"
DATA = artifact_path(ROOT / "data" / NAME)


def main():
    uploads = pd.read_parquet(artifact_path(DATA / "uploads.parquet"))
    orders = pd.read_parquet(artifact_path(DATA / "orders.parquet"))
    for frame in (uploads, orders):
        frame.columns = frame.columns.str.lower()
    if set(uploads.source_table) != set(SOURCES):
        raise ValueError("Expected both documented upload sources")
    if orders.order_id.isna().any() or orders.order_id.duplicated().any():
        raise ValueError(
            "ECOM order IDs must be populated and unique before joining"
        )
    orders["order_id"] = orders.order_id.map(int).astype(object)
    uploads["order_id"] = pd.Series(
        [numeric_id(v) for v in uploads.order_id_text], dtype=object
    )
    if (uploads.order_id_text.notna() & uploads.order_id.isna()).any():
        raise ValueError(
            "A populated order ID is blank or invalid; resolve before "
            "comparing sources"
        )
    if uploads.duplicated(["source_table", "upload_id"]).any():
        raise ValueError("Unexpected duplicate upload IDs within a source")
    eligible = uploads[uploads.order_id.notna()]
    source_orders = eligible[["source_table", "order_id"]].drop_duplicates()
    linked = source_orders.merge(
        orders,
        on="order_id",
        how="left",
        validate="many_to_one",
        indicator=True,
    )
    linked["reason"] = linked.order_cancel_reason.fillna("[SQL NULL]")
    linked.loc[linked._merge == "left_only", "reason"] = (
        "[No matching ECOM order]"
    )
    summary = []
    for source in SOURCES:
        raw = uploads[uploads.source_table == source]
        subset = linked[linked.source_table == source]
        summary.append(
            {
                "Source": source,
                "Diet upload entries": len(raw),
                "Entries with order ID": int(raw.order_id.notna().sum()),
                "Entries without order ID": int(raw.order_id.isna().sum()),
                "Distinct order IDs": len(subset),
                "Matched orders": int((subset._merge == "both").sum()),
                "Unmatched order IDs": int(
                    (subset._merge == "left_only").sum()
                ),
                "Canceled orders": int(
                    subset.order_status_description.eq("Canceled").sum()
                ),
                "Canceled orders with NULL reason": int(
                    (
                        subset.order_status_description.eq("Canceled")
                        & subset.order_cancel_reason.isna()
                    ).sum()
                ),
            }
        )
    coverage = pd.DataFrame(summary)
    denominators = dict(zip(coverage.Source, coverage["Distinct order IDs"]))
    counts = (
        linked.groupby(["reason", "source_table"])
        .size()
        .unstack(fill_value=0)
        .reindex(columns=SOURCES, fill_value=0)
    )
    counts = counts.loc[counts.sum(axis=1).sort_values(ascending=False).index]
    if any(
        int(counts[source].sum()) != denominators[source] for source in SOURCES
    ):
        raise ValueError(
            "Reason counts do not reconcile to distinct source order counts"
        )
    comparison = pd.DataFrame({"Order cancellation reason": counts.index})
    for source in SOURCES:
        comparison[source] = [
            f"{n:,} ({100 * n / denominators[source]:.2f}%)"
            for n in counts[source]
        ]
    differences = counts[SOURCES[1]] - counts[SOURCES[0]]
    total_difference = denominators[SOURCES[1]] - denominators[SOURCES[0]]
    if int(differences.sum()) != total_difference:
        raise ValueError(
            "Reason differences do not reconcile to the source-total "
            "difference"
        )
    comparison["Difference (notification minus HCDM orders)"] = [
        f"{n:+,}" if n else "0" for n in differences
    ]
    comparison.loc[len(comparison)] = [
        "Total",
        *[f"{denominators[s]:,} (100.00%)" for s in SOURCES],
        f"{total_difference:+,}" if total_difference else "0",
    ]
    sets = [
        set(
            source_orders.loc[source_orders.source_table == source, "order_id"]
        )
        for source in SOURCES
    ]
    metadata = {
        "scope": (
            "associated_resource_type = 'DIET_PRESCRIPTION', valid non-null "
            "associated order ID, all dates and order statuses; no "
            "order-item, upload-type, or replication filters"
        ),
        "order_id_fields": {
            SOURCES[0]: "ORDER_ID",
            SOURCES[1]: "context:orderId",
        },
        "grain": (
            "one distinct order ID per source; percentages include unmatched "
            "order IDs"
        ),
        "difference": (
            "notification-service distinct-order count minus HCDM "
            "distinct-order count"
        ),
        (
            "uploads_extracted_at"
        ): uploads.extracted_at_session_time.unique().tolist(),
        (
            "orders_extracted_at"
        ): orders.extracted_at_session_time.unique().tolist(),
        "shared_order_ids": len(sets[0] & sets[1]),
        "hcdm_only_order_ids": len(sets[0] - sets[1]),
        "notification_only_order_ids": len(sets[1] - sets[0]),
        "source_sha256": {
            name: hashlib.sha256(
                (artifact_path(DATA / name)).read_bytes()
            ).hexdigest()
            for name in ["uploads.parquet", "orders.parquet"]
        },
        "sql_sha256": {
            name: hashlib.sha256(
                (canonical_sql_path(name)).read_bytes()
            ).hexdigest()
            for name in [
                "diet_upload_source_orders.sql",
                "diet_upload_linked_orders.sql",
            ]
        },
    }
    notes = (
        "All available `DIET_PRESCRIPTION` source entries with an associated "
        "order ID. "
        "Order IDs come from HCDM `ORDER_ID` and notification-service "
        "`context:orderId`. "
        "Reasons come from `EDLDB.ECOM.ORDERS`. Each distinct order counts "
        "once per source; "
        "percentages use each source’s complete distinct-order population, "
        "including unmatched IDs. "
        "Difference is notification-service order count minus HCDM order "
        "count. "
        "SQL NULL means no recorded reason, which can include canceled "
        "orders. "
        f"Upload extraction: {metadata['uploads_extracted_at'][0]}; "
        f"order extraction: {metadata['orders_extracted_at'][0]}.\n\n"
    )
    table_dir = artifact_path(ROOT / "outputs/tables" / NAME)
    table_dir.mkdir(parents=True, exist_ok=True)
    for name, frame in [
        ("order-cancel-reasons", comparison),
        ("source-coverage", coverage),
    ]:
        write_text(
            table_dir / f"{name}.md",
            "# Diet-upload source comparison\n\n"
            + notes
            + markdown_table(frame)
            + "\n",
        )
        frame.to_parquet(artifact_path(DATA / f"{name}.parquet"), index=False)
    linked.to_parquet(
        artifact_path(DATA / "source-order-links.parquet"), index=False
    )
    counts.reset_index().to_parquet(
        artifact_path(DATA / "reason-counts.parquet"), index=False
    )
    write_text(
        artifact_path(DATA / "analysis.json"),
        json.dumps(metadata, indent=2) + "\n",
    )

    first, second = summary
    tex = [
        (
            "This comparison includes entries with "
            "\\texttt{associated\\_resource\\_type = DIET\\_"
            "PRESCRIPTION} and a non-null associated order ID "
            "in each source. HCDM uses \\texttt{ORDER\\_ID}; "
            "the notification-service source uses "
            "\\texttt{context:orderId}. Cancellation reasons "
            "are joined from \\texttt{EDLDB.ECOM.ORDERS}. No "
            "date, CMPU, study-cohort, order-item, upload-type, "
            "or replication filters are applied."
        ),
        (
            "In HCDM, "
            f"{first['Entries with order ID']:,}"
            " of "
            f"{first['Diet upload entries']:,}"
            " diet-upload entries have an order ID, representi"
            "ng "
            f"{first['Distinct order IDs']:,}"
            " distinct orders. In the notification-service sou"
            "rce, "
            f"{second['Entries with order ID']:,}"
            " of "
            f"{second['Diet upload entries']:,}"
            " entries have an order ID, representing "
            f"{second['Distinct order IDs']:,}"
            " distinct orders. Table~\\ref{tab:diet-upload-sour"
            "ce-cancel-reasons} compares the cancellation reas"
            "ons side by side. Each order counts once within e"
            "ach source regardless of the number of uploads."
        ),
        r"\begin{longtable}{@{}lrrr@{}}",
        (
            "\\caption{Order cancellation reasons for diet-"
            "prescription uploads with associated order IDs.}"
        ),
        r"\label{tab:diet-upload-source-cancel-reasons}\\",
        r"\toprule",
        (
            "Order cancellation reason & "
            "\\shortstack{\\texttt{EDLDB.BT\\_HCA\\_"
            "HCDM.}\\\\\\texttt{rxp\\_upload\\_"
            "entity}\\\\Orders (\\%)} & "
            "\\shortstack{\\texttt{rxp\\_notification\\_"
            "service.}\\\\\\texttt{upload\\_entity}\\\\Orders "
            "(\\%)} & \\shortstack{Difference\\\\Notification\\"
            "\\minus HCDM} \\\\"
        ),
        r"\midrule",
        r"\endfirsthead",
        (
            r"\toprule Order cancellation reason & HCDM orders (\%) & "
            r"Notification orders (\%) & Difference \\"
        ),
        r"\midrule",
        r"\endhead",
    ]
    labels = {
        "[SQL NULL]": "No recorded reason (SQL NULL)",
        "[No matching ECOM order]": "No matching ECOM order",
    }
    for row in comparison.itertuples(index=False, name=None):
        if row[0] == "Total":
            tex.append(r"\midrule")
        tex.append(
            "{"
            + latex_escape(labels.get(row[0], row[0]))
            + "} & "
            + " & ".join(latex_escape(cell) for cell in row[1:])
            + r" \\"
        )
    tex.extend(
        [
            r"\bottomrule",
            r"\end{longtable}",
            (
                "\\noindent\\textit{Notes:} Percentages use each sou"
                "rce\\textquotesingle s distinct-order total, and t"
                "he difference is the notification-service order c"
                "ount minus the HCDM order count. Totals include u"
                "nmatched IDs; the two source populations are not "
                "restricted to their intersection. "
                f"{metadata['shared_order_ids']:,}"
                " order IDs occur in both sources, "
                f"{metadata['hcdm_only_order_ids']:,}"
                " occur only in HCDM and "
                f"{metadata['notification_only_order_ids']:,}"
                " occur only in the notification-service source. U"
                "nmatched order IDs: "
                f"{first['Unmatched order IDs']:,}"
                " in HCDM and "
                f"{second['Unmatched order IDs']:,}"
                " in the notification-service source. A NULL reaso"
                "n does not imply that an order was not canceled. "
                "Of "
                f"{first['Canceled orders']:,}"
                " HCDM-linked orders and "
                f"{second['Canceled orders']:,}"
                " notification-linked orders with status \\texttt{C"
                "anceled}, "
                f"{first['Canceled orders with NULL reason']:,}"
                " and "
                f"{second['Canceled orders with NULL reason']:,}"
                ", respectively, have a NULL reason. Percentages m"
                "ay not sum to 100\\% because of rounding. Upload e"
                "xtraction: "
            )
            + latex_escape(metadata["uploads_extracted_at"][0])
            + r"; order extraction: "
            + latex_escape(metadata["orders_extracted_at"][0])
            + r" (UTC).",
        ]
    )
    tex_path = artifact_path(
        ROOT / "src/autogenerated" / NAME / "order-cancel-reasons.tex"
    )
    tex_path.parent.mkdir(parents=True, exist_ok=True)
    write_text(tex_path, "\n".join(tex) + "\n")
    print(coverage.to_string(index=False))
    print(comparison.to_string(index=False))


if __name__ == "__main__":
    main()

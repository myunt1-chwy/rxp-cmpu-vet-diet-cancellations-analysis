"""
Summarize retained NULL-resource upload extracts without live warehouse
access.
"""

import hashlib
import json
import re

import altair as alt
import pandas as pd

from shared.paths import (
    artifact_path,
    canonical_sql_path,
    output_path,
    repository_root,
)
from shared.python.create_upload_data_verification import latex_escape
from shared.python.markdown_tables import markdown_table, write_text

ROOT = repository_root()
DATA = artifact_path(ROOT / "data/null-resource-upload-analysis")
TABLES = artifact_path(ROOT / "outputs/tables/null-resource-upload-analysis")


def numeric_id(value):
    if pd.isna(value) or not re.fullmatch(r"[0-9]+", str(value).strip()):
        return None
    number = int(str(value).strip())
    return number if number < 10**38 else None


def main():
    uploads = pd.read_parquet(artifact_path(DATA / "uploads.parquet"))
    orders = pd.read_parquet(artifact_path(DATA / "orders.parquet"))
    for frame in (uploads, orders):
        frame.columns = frame.columns.str.lower()
    if orders.order_id.duplicated().any():
        raise ValueError(
            "ECOM.ORDERS is not unique by order_id; resolve before joining"
        )
    uploads["order_id"] = pd.Series(
        [numeric_id(v) for v in uploads.context_order_id], dtype=object
    )
    orders["order_id"] = orders.order_id.map(int).astype(object)
    linked = uploads[uploads.order_id.notna()].merge(
        orders,
        on="order_id",
        how="left",
        validate="many_to_one",
        indicator=True,
    )
    distinct = linked.drop_duplicates("order_id").copy()
    distinct["reason"] = distinct.order_cancel_reason.fillna("[SQL NULL]")
    distinct.loc[distinct._merge == "left_only", "reason"] = (
        "[No matching ECOM order]"
    )
    linked["reason"] = linked.order_cancel_reason.fillna("[SQL NULL]")
    linked.loc[linked._merge == "left_only", "reason"] = (
        "[No matching ECOM order]"
    )
    distribution = (
        distinct.groupby("reason", dropna=False)
        .size()
        .rename("Orders")
        .reset_index()
    )
    distribution["Upload entries"] = distribution.reason.map(
        linked.reason.value_counts()
    ).astype(int)
    distribution["Order share (%)"] = (
        100 * distribution.Orders / len(distinct)
    ).round(2)
    distribution = distribution.sort_values(
        ["Orders", "reason"], ascending=[False, True]
    )
    distribution = distribution[
        ["reason", "Orders", "Order share (%)", "Upload entries"]
    ]
    if distribution.Orders.sum() != len(distinct) or distribution[
        "Upload entries"
    ].sum() != len(linked):
        raise ValueError(
            "Cancellation distribution does not reconcile to input populations"
        )

    order_present = uploads.context_order_id.notna()
    item_present = uploads.context_order_item_id.notna()
    metrics = [
        ("All uploads with SQL NULL associated_resource_type", len(uploads)),
        ("Non-null orderId", int(order_present.sum())),
        ("Non-null orderItemId", int(item_present.sum())),
        ("Both IDs non-null", int((order_present & item_present).sum())),
        ("Order ID only", int((order_present & ~item_present).sum())),
        ("Order-item ID only", int((~order_present & item_present).sum())),
        ("Neither ID populated", int((~order_present & ~item_present).sum())),
    ]
    completeness = pd.DataFrame(
        metrics, columns=["Upload population", "Entries"]
    )
    completeness["Share of NULL-type uploads (%)"] = (
        100 * completeness.Entries / len(uploads)
    ).round(2)
    canceled = distinct[distinct.order_status_description == "Canceled"]
    canceled_reasons = (
        canceled.groupby("reason").size().rename("Orders").reset_index()
    )
    canceled_reasons["Share of canceled orders (%)"] = (
        100 * canceled_reasons.Orders / len(canceled)
    ).round(2)
    canceled_reasons = canceled_reasons.sort_values(
        ["Orders", "reason"], ascending=[False, True]
    )
    statuses = (
        distinct.groupby(["order_status_description", "reason"], dropna=False)
        .size()
        .rename("Orders")
        .reset_index()
    )
    coverage = pd.DataFrame(
        [
            (
                "Distinct context order IDs (non-null strings)",
                uploads.context_order_id.nunique(),
            ),
            ("Distinct numeric context order IDs", len(distinct)),
            (
                "Distinct context order-item IDs (non-null strings)",
                uploads.context_order_item_id.nunique(),
            ),
            (
                "Matched distinct ECOM orders",
                int((distinct._merge == "both").sum()),
            ),
            (
                "Unmatched distinct order IDs",
                int((distinct._merge == "left_only").sum()),
            ),
            ("Matched orders with status Canceled", len(canceled)),
            (
                "Other matched order statuses",
                int((distinct._merge == "both").sum()) - len(canceled),
            ),
            ("Repeated upload IDs", int(uploads.upload_id.duplicated().sum())),
            (
                "Non-null but invalid numeric order IDs",
                int((order_present & uploads.order_id.isna()).sum()),
            ),
            (
                "Non-null blank order IDs",
                int(
                    uploads.context_order_id.fillna("missing")
                    .str.strip()
                    .eq("")
                    .sum()
                ),
            ),
            (
                "Non-null blank order-item IDs",
                int(
                    uploads.context_order_item_id.fillna("missing")
                    .str.strip()
                    .eq("")
                    .sum()
                ),
            ),
            (
                "Non-null but invalid numeric order-item IDs",
                sum(
                    item_present
                    & pd.Series(
                        [
                            numeric_id(v) is None
                            for v in uploads.context_order_item_id
                        ]
                    )
                ),
            ),
            (
                "Uploads marked replication_deleted_flag true",
                int(uploads.replication_deleted_flag.eq(True).sum()),
            ),
        ],
        columns=["Check", "Count"],
    )
    metadata = {
        "population": (
            "EDLDB.RXP_NOTIFICATION_SERVICE.UPLOAD_ENTITY WHERE "
            "associated_resource_type IS NULL; all rows, no other filters"
        ),
        "context_keys": ["orderId", "orderItemId"],
        "nulls": (
            "SQL NULL, absent keys and JSON null are missing; blank and "
            "nonnumeric values counted separately"
        ),
        "distribution_grain": (
            "one distinct numeric context order ID; all order-ID uploads "
            "included regardless of item-ID presence"
        ),
        (
            "upload_extracted_at"
        ): uploads.extracted_at_session_time.unique().tolist(),
        (
            "order_extracted_at"
        ): orders.extracted_at_session_time.unique().tolist(),
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
                "null_resource_upload_context.sql",
                "null_resource_upload_orders.sql",
            ]
        },
    }
    TABLES.mkdir(parents=True, exist_ok=True)
    notes = (
        "Population: all entries in "
        "`EDLDB.RXP_NOTIFICATION_SERVICE.UPLOAD_ENTITY` "
        "where `associated_resource_type IS NULL`, without date or other "
        "filters. "
        f"Upload extraction: {metadata['upload_extracted_at'][0]}; "
        f"order extraction: {metadata['order_extracted_at'][0]}.\n\n"
        "JSON keys are `context:orderId` and `context:orderItemId`. Missing "
        "keys, SQL NULL and "
        "JSON null count as missing. Cancellation reasons come from "
        "`EDLDB.ECOM.ORDERS`; "
        "orders are counted once regardless of upload count. `[SQL NULL]` is "
        "a missing reason, "
        "not a statement that the order was not canceled. Unmatched order IDs "
        "remain explicit.\n\n"
    )
    for name, title, frame in [
        (
            "identifier-completeness",
            "Order identifiers in NULL-resource uploads",
            completeness,
        ),
        ("join-coverage", "Order-link coverage and data checks", coverage),
        (
            "order-cancel-reasons",
            "Cancellation reasons across all context order IDs",
            distribution,
        ),
        (
            "canceled-order-reasons",
            "Cancellation reasons among matched Canceled orders only",
            canceled_reasons,
        ),
        (
            "order-status-and-reason",
            "Order status and cancellation reason",
            statuses,
        ),
    ]:
        write_text(
            artifact_path(TABLES / f"{name}.md"),
            f"# {title}\n\n" + notes + markdown_table(frame) + "\n",
        )
        frame.to_parquet(artifact_path(DATA / f"{name}.parquet"), index=False)
    write_text(
        artifact_path(DATA / "analysis.json"),
        json.dumps(metadata, indent=2) + "\n",
    )
    linked.to_parquet(
        artifact_path(DATA / "upload-order-links.parquet"), index=False
    )
    distinct.to_parquet(
        artifact_path(DATA / "distinct-orders.parquet"), index=False
    )

    both = int((order_present & item_present).sum())
    matched = int((distinct._merge == "both").sum())
    missing_reason_canceled = int(canceled.order_cancel_reason.isna().sum())
    aged = int(canceled.order_cancel_reason.eq("Aged Order").sum())
    tex = [
        r"\Needspace{18\baselineskip}",
        (
            "\\noindent Of the "
            f"{len(uploads):,}"
            " notification-service upload entries with \\texttt"
            "{associated\\_resource\\_type IS NULL}, "
            f"{both:,}"
            " ("
            f"{100 * both / len(uploads):.2f}"
            "\\%) have both a non-null \\texttt{context:orderId}"
            " and \\texttt{context:orderItemId}; "
            f"{int((~order_present & ~item_present).sum()):,}"
            " have neither. These entries reference "
            f"{len(distinct):,}"
            " distinct orders, of which "
            f"{matched:,}"
            " match \\texttt{EDLDB.ECOM.ORDERS} and "
            f"{len(distinct) - matched:,}"
            " are unmatched. Table~\\ref{tab:null-resource-uplo"
            "ad-order-cancel-reasons} shows the cancellation-r"
            "eason distribution across these distinct order ID"
            "s."
        ),
        r"\begin{longtable}{@{}lrr@{}}",
        (
            "\\caption{Cancellation reasons for orders referenced "
            "by uploads with no associated resource type.}"
        ),
        r"\label{tab:null-resource-upload-order-cancel-reasons}\\",
        r"\toprule",
        r"Order cancellation reason & Distinct orders & Share (\%) \\",
        r"\midrule",
        r"\endfirsthead",
        r"\toprule",
        r"Order cancellation reason & Distinct orders & Share (\%) \\",
        r"\midrule",
        r"\endhead",
    ]
    labels = {
        "[SQL NULL]": "No recorded reason (SQL NULL)",
        "[No matching ECOM order]": "No matching ECOM order",
    }
    for row in distribution.to_dict("records"):
        reason = latex_escape(labels.get(row["reason"], row["reason"]))
        tex.append(
            f"{{{reason}}} & {row['Orders']:,} & {row['Order share (%)']:.2f}"
            + r" \\"
        )
    tex.extend(
        [
            r"\midrule",
            f"Total & {len(distinct):,} & 100.00" + r" \\",
            r"\bottomrule",
            r"\end{longtable}",
            (
                "\\noindent\\textit{Notes:} All available NULL-type "
                "uploads are included, without date or other filte"
                "rs. Missing JSON keys and JSON null count as miss"
                "ing identifiers. Each order counts once regardles"
                "s of upload count; percentages use all "
                f"{len(distinct):,}"
                " distinct order IDs, including unmatched IDs. A N"
                "ULL cancellation reason does not imply that the o"
                "rder was not canceled. Of "
                f"{len(canceled):,}"
                " matched orders with status \\texttt{Canceled}, "
                f"{missing_reason_canceled:,}"
                " have a NULL reason and "
                f"{aged:,}"
                " ("
                f"{100 * aged / len(canceled):.2f}"
                "\\%) have reason \\texttt{Aged Order}. Percentages "
                "may not sum to 100\\% because of rounding. Upload "
                "extraction: "
            )
            + latex_escape(metadata["upload_extracted_at"][0])
            + r"; order extraction: "
            + latex_escape(metadata["order_extracted_at"][0])
            + r" (UTC).",
        ]
    )
    tex_path = artifact_path(
        ROOT
        / (
            "src/autogenerated/null-resource-upload-analysis/order-"
            "cancel-reasons.tex"
        )
    )
    tex_path.parent.mkdir(parents=True, exist_ok=True)
    write_text(tex_path, "\n".join(tex) + "\n")

    chart_data = canceled_reasons.rename(columns={"reason": "Reason"})
    chart_data["Reason"] = chart_data.Reason.replace(
        {"[SQL NULL]": "No recorded reason (SQL NULL)"}
    )
    bars = (
        alt.Chart(chart_data)
        .mark_bar(color="#327cb0")
        .encode(
            x=alt.X(
                "Orders:Q",
                title="Distinct canceled orders",
                scale=alt.Scale(domain=[0, max(chart_data.Orders) * 1.15]),
            ),
            y=alt.Y(
                "Reason:N",
                sort="-x",
                title=None,
                axis=alt.Axis(labelLimit=320),
            ),
            tooltip=[
                "Reason:N",
                "Orders:Q",
                alt.Tooltip("Share of canceled orders (%):Q", format=".2f"),
            ],
        )
    )
    chart = (
        bars
        + bars.mark_text(align="left", dx=5, color="#767676").encode(
            text="Orders:Q"
        )
    ).properties(
        width=500,
        height=260,
        background="transparent",
        title=alt.TitleParams(
            text=(
                f"Cancellation reasons for {len(canceled):,} linked canceled "
                f"orders"
            ),
            subtitle=(
                f"NULL-resource uploads: {len(distinct):,} distinct order "
                f"IDs; {len(distinct) - len(orders):,} unmatched"
            ),
        ),
    )
    chart = chart.configure_axis(
        labelColor="#767676", titleColor="#767676"
    ).configure_title(color="#767676", subtitleColor="#767676")
    target = artifact_path(
        ROOT
        / (
            "outputs/charts/null-resource-upload-analysis/order-"
            "cancel-reasons.png"
        )
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    chart.save(output_path(target), scale_factor=2)
    print(completeness.to_string(index=False))
    print(coverage.to_string(index=False))
    print(distribution.to_string(index=False))
    print(canceled_reasons.to_string(index=False))


if __name__ == "__main__":
    main()

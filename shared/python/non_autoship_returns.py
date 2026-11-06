"""Orchestrate and validate same-pet/product reorder cohort panels."""

import hashlib
import json
import os
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import pandas as pd
from jinja2 import Environment, StrictUndefined

from shared.python import (
    create_opportunity_new_upload_customer_follow_up as first,
)
from shared.python import create_opportunity_order_cancellation_summary as base
from shared.python import reorder_analysis
from shared.python.analysis.reorder_panels import render_panel
from shared.python.markdown_tables import markdown_table, write_text

ROOT = Path(__file__).resolve().parents[2]
OWNER = "non-autoship-all-aged-returns"
TARGETS = dict(
    zip(
        ["all-aged", "first-upload", "first-vet-diet"],
        [
            OWNER,
            "non-autoship-first-upload-returns",
            "non-autoship-first-vet-diet-returns",
        ],
        strict=True,
    )
)
INITIATED_TARGETS = {
    cohort: "autoship-initiated-or-non-autoship-" + suffix
    for cohort, suffix in zip(
        TARGETS, ["all-aged", "first-upload", "first-vet-diet"], strict=True
    )
}
SHIPPED_TARGETS = dict(
    zip(
        TARGETS,
        [
            "same-pet-product-return-comparison",
            "same-pet-product-first-upload-returns",
            "same-pet-product-first-vet-diet-returns",
        ],
        strict=True,
    )
)
SHIPPED_LABELS = dict(
    zip(
        TARGETS,
        [
            "financial-opportunity-reorder-windows",
            "financial-opportunity-new-upload-follow-up",
            "financial-opportunity-new-vet-diet-follow-up",
        ],
        strict=True,
    )
)
PARAMS = {
    "start_date": "2026-05-01",
    "end_date": "2026-08-01",
    "as_of_date": "2026-10-28",
    "followup_days": 70,
}
HORIZONS = list(range(7, 71, 7))
REFRESH = "make non-autoship-same-pet-product-returns REFRESH=1"


def render_sql():
    path = ROOT / "targets" / OWNER / "src/sql/non_autoship_returns.sql.j2"
    return (
        Environment(undefined=StrictUndefined)
        .from_string(path.read_text())
        .render(**PARAMS)
    )


def records(raw):
    raw = raw.rename(columns=str.lower)
    result = {
        k: []
        for k in [
            "summary",
            "anchor",
            "line",
            "shipment",
            "matched",
            "first_shipped_summary",
            "shipped_summary",
            "subscription_history",
        ]
    }
    for row in raw.itertuples():
        result[row.record_type].append(
            {k.lower(): v for k, v in json.loads(row.payload).items()}
        )
    return result


def money(value):
    return Decimal(str(value)) if value is not None else Decimal(0)


def key(row, prefix="reorder_"):
    return tuple(str(row[prefix + k]) for k in ["order_id", "line_id"])


def anchor_set(rows):
    return {
        (
            str(r["original_order_id"]),
            str(r["original_line_id"]),
            str(r["original_customer_id"]),
            pd.Timestamp(r["original_cancel_utc"]).tz_localize(None),
        )
        for r in rows
    }


def dependencies():
    """Verify query identity and hashes before using frozen evidence."""
    references, hashes = {}, {}
    root = ROOT / "targets/same-pet-product-return-comparison/data"
    folders = [
        "aged-reorder-studies",
        "new-upload-customer-follow-up-studies",
        "new-vet-diet-customer-follow-up-studies",
    ]
    for cohort, folder in zip(TARGETS, folders, strict=True):
        candidates = []
        for path in (root / folder).glob(
            "*/source.json" if cohort == "all-aged" else "*/analysis.json"
        ):
            meta = json.loads(path.read_text())
            identity = meta["identity"]
            if identity.get("horizons") == HORIZONS and all(
                identity.get(k) == PARAMS[k]
                for k in ["start_date", "end_date", "as_of_date"]
            ):
                candidates.append((path, meta))
        if len(candidates) != 1:
            raise ValueError(
                "Missing compatible financial-return inputs; "
                "run make same-pet-product-returns REFRESH=1"
            )
        path, meta = candidates[0]
        args = [PARAMS[k] for k in ["start_date", "end_date", "as_of_date"]]
        sql = (
            reorder_analysis.render_sql(*args, 70, all_studies=True)
            if cohort == "all-aged"
            else first.render_sql(*args, all_studies=True, cohort_kind=cohort)
        )
        if (
            meta["identity"]["sql_sha256"]
            != hashlib.sha256(sql.encode()).hexdigest()
        ):
            raise ValueError(
                "Stale financial-return query; refresh existing "
                "same-pet-product-returns first"
            )
        source = path.parent / "source.parquet"
        if base.digest(source) != meta["source_sha256"]:
            raise ValueError("Financial-return source fingerprint differs")
        if cohort != "all-aged":
            _, _, fingerprints = first.load_cohort(
                PARAMS["start_date"], PARAMS["end_date"], True, cohort
            )
            if any(meta["identity"][k] != v for k, v in fingerprints.items()):
                raise ValueError("Financial-return cohort dependency differs")
        references[cohort] = pd.read_parquet(source).rename(columns=str.lower)
        hashes[str(path.relative_to(ROOT))] = base.digest(path)
        hashes[str(source.relative_to(ROOT))] = base.digest(source)
    return references, hashes


def validate(data, references=None):
    """Reconcile SQL summaries, physical lines and shipments."""
    for kind in ["anchor", "line", "shipment"]:
        for row in data[kind]:
            if any(
                v is not None and v > 1
                for k, v in row.items()
                if k.endswith("_variants")
            ):
                raise ValueError(
                    "Conflicting source or autoship flags: " + kind
                )
    for row in data["anchor"]:
        if any(
            row[k] is None
            for k in [
                "original_order_id",
                "original_line_id",
                "original_customer_id",
                "original_cancel_utc",
            ]
        ):
            raise ValueError("Missing anchor identity or cancellation")
    shipments = {}
    for row in data["shipment"]:
        k = (str(row["order_id"]), str(row["order_line_id"]))
        entry = shipments.setdefault(k, [Decimal(0), 0])
        entry[0] += money(row["net_sales"])
        entry[1] += row["net_sales"] is None
    for row in data["line"]:
        if shipments[key(row)] != [
            money(row["reorder_known_net_sales"]),
            row["missing_sales_records"],
        ]:
            raise ValueError(
                "Shipment/physical-line sales reconciliation failed"
            )
    # Independently reconcile pair minima against full-history physical lines.
    minima = {}
    history_lines = {}
    for row in data["subscription_history"]:
        pair = (row["subscription_key"], row["product_key"])
        timestamp = pd.Timestamp(row["history_line_shipped_utc"])
        physical = (*pair, row["order_line_id"])
        if physical in history_lines or row["order_line_id"] is None:
            raise ValueError("Missing or duplicated subscription history line")
        history_lines[physical] = timestamp
        minima[pair] = min(minima.get(pair, timestamp), timestamp)
    for row in data["line"]:
        pair = (row["subscription_key"], row["product_key"])
        expected = minima.get(pair)
        actual = row["product_first_shipped_utc"]
        if (pd.Timestamp(actual) if actual is not None else None) != expected:
            raise ValueError("Subscription/product shipment minimum differs")
        if pair in minima and row["transaction_shipped_utc"] is not None:
            physical = (*pair, row["reorder_line_id"])
            if history_lines.get(physical) != pd.Timestamp(
                row["transaction_shipped_utc"]
            ):
                raise ValueError("Transaction/history line shipment differs")
    earliest_counts = {}
    for physical, timestamp in history_lines.items():
        pair = physical[:2]
        if timestamp == minima[pair]:
            earliest_counts[pair] = earliest_counts.get(pair, 0) + 1
    audit = {
        "subscription_product_history": {
            "physical_lines": len(history_lines),
            "pairs": len(minima),
            "pairs_with_tied_earliest_lines": sum(
                count > 1 for count in earliest_counts.values()
            ),
        }
    }
    for cohort in TARGETS:
        anchors = [r for r in data["anchor"] if r["cohort"] == cohort]
        if references is not None:
            expected = references[cohort].to_dict("records")
            if anchor_set(anchors) != anchor_set(expected):
                raise ValueError(
                    "Existing cohort anchor agreement failed: " + cohort
                )
        denominator = len({r["original_customer_id"] for r in anchors})
        summary = sorted(
            [r for r in data["summary"] if r["cohort"] == cohort],
            key=lambda r: r["days"],
        )
        if [r["days"] for r in summary] != HORIZONS:
            raise ValueError("Missing or repeated follow-up horizons")
        prior = set()
        for row in summary:
            matches = [
                r
                for r in data["matched"]
                if r["cohort"] == cohort and r["days"] == row["days"]
            ]
            selected = [
                r
                for r in matches
                if r["line_auto_reorder_flag"] is False
                and r["reorder_shipped_utc"] is not None
            ]
            keys = {key(r) for r in selected}
            if len(keys) != len(selected) or not prior <= keys:
                raise ValueError(
                    "Duplicate physical lines or non-nested windows"
                )
            prior = keys
            for prefix, rows in [("", selected), ("unfiltered_", matches)]:
                expected = {
                    "customers": len({r["reorder_customer_id"] for r in rows}),
                    "orders": len({r["reorder_order_id"] for r in rows}),
                    "lines": len(rows),
                }
                if any(row[prefix + k] != v for k, v in expected.items()):
                    raise ValueError("Distinct-count reconciliation failed")
            null_rows = [
                r
                for r in matches
                if r["line_auto_reorder_flag"] is None
                and r["reorder_shipped_utc"] is not None
            ]
            null_counts = {
                "null_flag_lines": len(null_rows),
                "null_flag_orders": len(
                    {r["reorder_order_id"] for r in null_rows}
                ),
                "null_flag_customers": len(
                    {r["reorder_customer_id"] for r in null_rows}
                ),
            }
            if any(row[k] != v for k, v in null_counts.items()):
                raise ValueError("NULL flag diagnostics differ")
            expected_pct = (
                100 * row["customers"] / denominator if denominator else None
            )
            if (expected_pct is None and row["percentage"] is not None) or (
                expected_pct is not None
                and abs(float(row["percentage"]) - expected_pct) > 1e-5
            ):
                raise ValueError("Cohort percentage differs")
            if row["denominator"] != denominator:
                raise ValueError("Changed denominator")
            if money(row["known_net_sales"]) != sum(
                (money(r["reorder_known_net_sales"]) for r in selected),
                Decimal(0),
            ) or row["missing_sales_records"] != sum(
                r["missing_sales_records"] for r in selected
            ):
                raise ValueError("Summary sales reconciliation failed")
            if any(
                row[k] > row["unfiltered_" + k]
                for k in ["customers", "orders", "lines"]
            ):
                raise ValueError("Filtered count exceeds unfiltered count")
        audit[cohort] = summary[-1]
    audit["first_shipped_only"] = validate_first_shipped(data)
    audit["shipped_same_pet_product"] = validate_first_shipped(
        data, shipped=True
    )
    return audit


def validate_first_shipped(data, shipped=False):
    """Reconcile first-shipped eligibility with matching line evidence."""
    summaries = data["shipped_summary" if shipped else "first_shipped_summary"]
    expected_windows = {(c, d) for c in TARGETS for d in HORIZONS}
    if (
        len(summaries) != len(expected_windows)
        or {(r["cohort"], r["days"]) for r in summaries} != expected_windows
    ):
        raise ValueError(
            "Missing or duplicated first-shipped cohort summaries"
        )
    audit = {}
    for summary in summaries:
        cohort, days = summary["cohort"], summary["days"]
        baseline = next(
            r
            for r in data["summary"]
            if r["cohort"] == cohort and r["days"] == days
        )
        matches = [
            r
            for r in data["matched"]
            if r["cohort"] == cohort and r["days"] == days
        ]
        selected = []
        unknown = 0
        for row in matches:
            first_shipped = (
                None
                if row["transaction_shipped_utc"] is None
                or row["product_first_shipped_utc"] is None
                else pd.Timestamp(row["transaction_shipped_utc"])
                == pd.Timestamp(row["product_first_shipped_utc"])
            )
            line_auto = row["line_auto_reorder_flag"]
            initial = (
                False
                if first_shipped is False or line_auto is False
                else None
                if first_shipped is None or line_auto is None
                else True
            )
            eligible = (
                row["reorder_shipped_utc"] is not None if shipped else initial
            )
            if not shipped and row["first_shipped_eligible"] is not eligible:
                raise ValueError("First-shipped SQL/NULL behavior differs")
            unknown += eligible is None
            if eligible is True:
                selected.append(row)
        expected = {
            "days": days,
            "denominator": baseline["denominator"],
            "customers": len({r["reorder_customer_id"] for r in selected}),
            "orders": len({r["reorder_order_id"] for r in selected}),
            "lines": len(selected),
            "missing_sales_records": sum(
                r["missing_sales_records"] for r in selected
            ),
            "unknown_eligibility_lines": unknown,
        }
        if any(summary[k] != v for k, v in expected.items()):
            raise ValueError("First-shipped summary counts differ")
        if len({key(r) for r in selected}) != len(selected):
            raise ValueError("Duplicate first-shipped matching lines")
        if any(
            not 0 <= summary[k] <= baseline["unfiltered_" + k]
            for k in ["customers", "orders", "lines"]
        ):
            raise ValueError(
                "First-shipped counts exceed unfiltered populations"
            )
        if money(summary["known_net_sales"]) != sum(
            (money(r["reorder_known_net_sales"]) for r in selected), Decimal(0)
        ):
            raise ValueError("First-shipped sales reconciliation differs")
        pct = (
            100 * expected["customers"] / expected["denominator"]
            if expected["denominator"]
            else None
        )
        if (pct is None and summary["percentage"] is not None) or (
            pct is not None and abs(float(summary["percentage"]) - pct) > 1e-5
        ):
            raise ValueError("First-shipped cohort percentage differs")
        audit.setdefault(cohort, {})[days] = summary
    return audit


def present_first_shipped(data):
    """Export the 70-day table with authoritative Org cells."""
    labels = {
        "all-aged": "All aged customers",
        "first-upload": "First CUSTOMER_UPLOAD vet-diet order aged",
        "first-vet-diet": "First vet-diet order aged",
    }
    summaries = {
        r["cohort"]: r
        for r in data["first_shipped_summary"]
        if r["days"] == 70
    }
    columns = [
        "Cohort",
        "Denominator",
        "Customers who reordered",
        "Cohort (%)",
        "Distinct orders",
        "Matching lines",
        "Matching-line net sales (USD)",
    ]
    cells = []
    for cohort, label in labels.items():
        row = summaries[cohort]
        sales = f"{money(row['known_net_sales']):,.2f}"
        if row["missing_sales_records"]:
            sales += " (incomplete)"
        cells.append(
            [
                label,
                f"{row['denominator']:,}",
                f"{row['customers']:,}",
                f"{float(row['percentage']):.2f}"
                if row["denominator"]
                else "N/A",
                f"{row['orders']:,}",
                f"{row['lines']:,}",
                sales,
            ]
        )
    directory = ROOT / "targets" / OWNER / "outputs/tables"
    stem = "first-shipped-or-non-autoship-70d"
    note = (
        "Same customer, same pet and exact part number; successful later "
        "orders placed after cancellation through day 70 inclusive. "
        "Require a non-null shipment date on each matching physical line. "
        "Include later lines where "
        "the line autoreorder flag is TRUE and its shipment timestamp equals "
        "the earliest shipment for its subscription and product. Full history "
        "is used; all ties qualify. Missing keys/timestamps are excluded. "
        "Original aged lines are unrestricted by these flags. Cohorts "
        "overlap. Study cancellations: [2026-05-01, 2026-08-01) UTC; "
        "observation cutoff: 2026-10-28 00:00 UTC. Sales preserve signed "
        "amounts and deduplicate physical lines and shipment contributions."
    )
    org = directory / (stem + ".org")
    write_text(
        org,
        "#+TITLE: Autoship-initiating 70-day reorders\n"
        + "#+NOTE: "
        + note
        + "\n\n| "
        + " | ".join(columns)
        + " |\n|"
        + "+".join(["---"] * len(columns))
        + "|\n"
        + "\n".join("| " + " | ".join(row) + " |" for row in cells)
        + "\n",
    )
    values = [
        [c.strip() for c in line.strip("|").split("|")]
        for line in org.read_text().splitlines()
        if line.startswith("|")
    ]
    frame = pd.DataFrame(values[2:], columns=values[0])
    write_text(
        directory / (stem + ".md"),
        "# Autoship-initiating 70-day reorders\n\n"
        + note
        + "\n\n"
        + markdown_table(frame)
        + "\n",
    )
    write_text(
        directory / (stem + "-provenance.json"),
        json.dumps(
            {
                "parameters": PARAMS,
                "summary": summaries,
                "source_sha256": base.digest(
                    ROOT / "targets" / OWNER / "data/current/source.parquet"
                ),
                "org_sha256": base.digest(org),
            },
            indent=2,
        )
        + "\n",
    )
    print(frame.to_string(index=False))


def present(data, initiated=False, shipped=False):
    targets = (
        SHIPPED_TARGETS
        if shipped
        else INITIATED_TARGETS
        if initiated
        else TARGETS
    )
    summary = (
        "shipped_summary"
        if shipped
        else "first_shipped_summary"
        if initiated
        else "summary"
    )
    for cohort, target in targets.items():
        directory = ROOT / "targets" / target
        rows = sorted(
            [r for r in data[summary] if r["cohort"] == cohort],
            key=lambda r: r["days"],
        )
        cells = []
        for r in rows:
            pct = (
                "N/A"
                if not r["denominator"]
                else f"{float(r['percentage']):.2f}"
            )
            sales = f"{money(r['known_net_sales']):,.2f}"
            if r["missing_sales_records"]:
                sales += "*"
            cells.append(
                [
                    str(r["days"]),
                    f"{r['customers']:,}",
                    pct,
                    f"{r['orders']:,}",
                    f"{r['lines']:,}",
                    sales,
                ]
            )
        org = directory / "outputs/tables/table.org"
        write_text(
            org,
            "| Days | Customers | Cohort (%) | Orders | Line items | "
            "Net sales |\n"
            "|---+---+---+---+---+---|\n"
            + "\n".join("| " + " | ".join(row) + " |" for row in cells)
            + "\n",
        )
        # Org is authoritative: render the read-back values, not the dataframe.
        values = [
            line.strip("|").strip().split(" | ")
            for line in org.read_text().splitlines()[2:]
        ]
        first_row, last = rows[0], rows[-1]

        def percent(r):
            return (
                "N/A"
                if not r["denominator"]
                else f"{float(r['percentage']):.2f}\\%"
            )

        if initiated or shipped:
            qualifier = (
                "through initial autoship line items for that product. "
                if initiated
                else "through shipped matching line items. "
            )
            narrative = (
                f"Of {last['denominator']:,} customers, "
                f"{first_row['customers']:,} ({percent(first_row)}) reordered "
                "by day 7 and "
                f"{last['customers']:,} ({percent(last)}) by day 70 "
                + qualifier
                + "At 70 days these reorders included "
                f"{last['orders']:,} distinct orders and {last['lines']:,} "
                "matching lines. "
                f"There were {last['unknown_eligibility_lines']:,} lines "
                "with unknown eligibility and "
                f"{last['missing_sales_records']:,} missing shipment sales "
                "records among included lines.\n\n"
            )
        else:
            narrative = (
                f"Of {last['denominator']:,} customers, "
                f"{first_row['customers']:,} ({percent(first_row)}) "
                "reordered by day 7 "
                f"and {last['customers']:,} ({percent(last)}) by day 70. "
                f"At 70 days, {last['null_flag_lines']:,} otherwise "
                "qualifying lines "
                f"on {last['null_flag_orders']:,} orders for "
                f"{last['null_flag_customers']:,} customers had NULL "
                "line flags "
                "and were excluded. Lines absent from the transaction table "
                "are classified as non-autoship. "
                f"There were {last['missing_sales_records']:,} missing "
                "shipment sales records among included lines.\n\n"
            )
        eligibility_note = (
            "Autoship line items for the same pet and part number, "
            "on the earliest shipment of that product within the subscription."
            if initiated
            else "Line items for the same pet and the same part number."
            if shipped
            else "Non-autoship line items for the same pet and part number. "
            "Lines absent from the subscription transaction table "
            "are included."
        )
        title = (
            "Autoship-initiating reorders"
            if initiated
            else "Same-pet, same-product reorders"
            if shipped
            else "Non-autoship reorders"
        )
        label = "tab:" + (SHIPPED_LABELS[cohort] if shipped else target)
        write_text(
            directory / "outputs/latex/visual.tex",
            render_panel(
                values,
                f"{last['denominator']:,}",
                label,
                narrative,
                title,
                eligibility_note,
            ),
        )
        write_text(
            directory / "outputs/tables/provenance.json",
            json.dumps(
                {
                    "source_owner": OWNER,
                    "parameters": PARAMS,
                    "summary": rows,
                    "org_sha256": base.digest(org),
                },
                indent=2,
            )
            + "\n",
        )


def run(refresh=False):
    references, deps = dependencies()
    sql = render_sql()
    identity = {
        "parameters": PARAMS,
        "query_sha256": hashlib.sha256(sql.encode()).hexdigest(),
        "dependencies": deps,
        "version": 1,
    }
    materialized = (
        ROOT / "targets" / OWNER / "src/autogenerated/non_autoship_returns.sql"
    )
    write_text(materialized, sql.rstrip() + "\n")
    directory = ROOT / "targets" / OWNER / "data"
    current = directory / "current"
    if refresh:
        stage = directory / ("run-" + uuid4().hex)
        stage.mkdir(parents=True)
        write_text(stage / "query.sql", sql)
        # sqlparse counts indentation tokens toward its 10,000-token limit.
        # The runner formats this identical statement for execution/history.
        execution = stage / "execution.sql"
        write_text(
            execution, "\n".join(line.lstrip() for line in sql.splitlines())
        )
        engine = base.extract(execution, stage / "source.parquet", stage)
        data = records(pd.read_parquet(stage / "source.parquet"))
        audit = validate(data, references)
        manifest = dict(
            identity=identity,
            source_sha256=base.digest(stage / "source.parquet"),
            extracted_at_utc=datetime.now(UTC).isoformat(),
            sources=[
                "EDLDB.BT_HCA_HCDM.RXP_PRESCRIPTIONS",
                "EDLDB.BT_HCA_HCDM.ORDER_LINE_COST_MEASURES_RXP",
                "EDLDB.ECOM.ORDERS",
                "EDLDB.BT_SHARED_DW.FCT_SUBSCRIPTION_ORDER_LINE_TRANSACTION",
            ],
            **engine,
        )
        write_text(
            stage / "manifest.json", json.dumps(manifest, indent=2) + "\n"
        )
        write_text(
            stage / "reconciliation.json", json.dumps(audit, indent=2) + "\n"
        )
        # Atomic pointer swap only after extraction and validation succeed.
        link = directory / ("current-" + uuid4().hex)
        link.symlink_to(stage.name, target_is_directory=True)
        os.replace(link, current)
    else:
        try:
            meta = json.loads((current / "manifest.json").read_text())
            if meta["identity"] != identity or meta[
                "source_sha256"
            ] != base.digest(current / "source.parquet"):
                raise ValueError("fingerprint differs")
            data = records(pd.read_parquet(current / "source.parquet"))
        except (OSError, ValueError, KeyError) as error:
            raise ValueError(
                f"Missing or stale cache; run {REFRESH}"
            ) from error
        audit = validate(data, references)
    present(data)
    present_first_shipped(data)
    present(data, initiated=True)
    present(data, shipped=True)
    print(json.dumps(audit, indent=2))

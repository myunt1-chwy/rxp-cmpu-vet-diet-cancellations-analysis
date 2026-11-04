"""Reusable reorder analysis helpers; no analysis CLI."""

from datetime import date

import duckdb
import pandas as pd
import pyarrow as pa
from jinja2 import Environment, StrictUndefined

from shared.python import financial_values as base
from shared.python.paths import canonical_sql_path
from shared.python.sql_templates import render_sql as render_template

KEYS = ["original_order_id", "original_line_id"]


REORDER_KEYS = ["reorder_order_id", "reorder_line_id"]


STUDIES = ["same-part-pet", "same-pet-different-part", "any-vet-diet"]


def scope_mask(frame, study):
    if study == "any-chewy":
        return pd.Series(True, index=frame.index)
    if study == "any-vet-diet":
        return frame.reorder_is_vet_diet.eq(True).fillna(False)
    pet = (
        frame.original_pet_id.notna()
        & frame.reorder_pet_id.notna()
        & frame.original_pet_id.eq(frame.reorder_pet_id)
    )
    part = (
        frame.original_product_part_number.notna()
        & frame.reorder_product_part_number.notna()
        & frame.original_product_part_number.astype("string")
        .str.strip()
        .ne("")
        & frame.reorder_product_part_number.astype("string").str.strip().ne("")
    )
    if study == "same-part-pet":
        return (
            pet
            & part
            & frame.original_product_part_number.eq(
                frame.reorder_product_part_number
            )
        ).fillna(False)
    if study == "same-pet-different-part":
        return (
            pet
            & part
            & frame.original_product_part_number.ne(
                frame.reorder_product_part_number
            )
            & frame.reorder_is_vet_diet.eq(True)
        ).fillna(False)
    raise ValueError("unknown follow-up study")


def analyze(
    raw,
    frozen,
    days,
    as_of,
    source_days=None,
    study="same-part-pet",
    broad_source=False,
):
    f = raw.rename(columns=str.lower).copy()
    for col in (
        KEYS
        + REORDER_KEYS
        + [
            "original_customer_id",
            "original_pet_id",
            "reorder_customer_id",
            "reorder_pet_id",
        ]
    ):
        f[col] = f[col].map(base.identifier)
    for col in ["original_product_part_number", "reorder_product_part_number"]:
        f[col] = f[col].astype("string")
    f["original_cancel_utc"] = pd.to_datetime(
        f.original_cancel_utc, utc=True, format="mixed"
    )
    f["reorder_placed_utc"] = pd.to_datetime(
        f.reorder_placed_utc, utc=True, format="mixed"
    )
    f["reorder_shipped_utc"] = pd.to_datetime(
        f.reorder_shipped_utc, utc=True, format="mixed"
    )
    originals = f.drop_duplicates(KEYS).copy()
    if set(map(tuple, originals[KEYS].to_numpy())) != set(
        map(tuple, frozen[KEYS].to_numpy())
    ):
        raise ValueError("original keys differ from frozen aged membership")
    if "registry_variants" in f and f.registry_variants.gt(1).any():
        raise ValueError(
            "conflicting original prescription registry eligibility"
        )
    if (
        f[
            [
                "customer_variants",
                "pet_variants",
                "part_variants",
                "cancel_variants",
                "reason_variants",
            ]
        ]
        .gt(1)
        .any()
        .any()
    ):
        raise ValueError("conflicting original source values")
    evidence = originals.merge(
        frozen, on=KEYS, validate="one_to_one", suffixes=("", "_frozen")
    )
    if not (
        evidence.original_customer_id.eq(evidence.customer_id)
        & evidence.original_cancel_utc.eq(evidence.cancelled_at_utc)
        & evidence.original_reason.eq("aged order")
    ).all():
        raise ValueError(
            "aged source differs from frozen customer/cancellation evidence"
        )
    originals["usable_match_keys"] = (
        originals.original_customer_id.notna()
        & originals.original_pet_id.notna()
        & originals.original_product_part_number.notna()
        & originals.original_product_part_number.ne("")
    )
    if study in ["any-vet-diet", "any-chewy"]:
        originals["usable_match_keys"] = originals.original_customer_id.notna()
    originals["complete_followup"] = originals.original_cancel_utc.add(
        pd.Timedelta(days=days)
    ).le(pd.Timestamp(as_of, tz="UTC"))
    matches = f.loc[f.reorder_order_id.notna()].copy()
    if matches.source_variants.gt(1).any():
        raise ValueError("conflicting reorder source values")
    if not (
        matches.original_customer_id.eq(matches.reorder_customer_id)
        & matches.original_order_id.ne(matches.reorder_order_id)
        & matches.reorder_placed_utc.gt(matches.original_cancel_utc)
        & matches.reorder_placed_utc.le(
            matches.original_cancel_utc
            + pd.Timedelta(days=source_days or days)
        )
        & matches.reorder_placed_utc.le(pd.Timestamp(as_of, tz="UTC"))
    ).all():
        raise ValueError("reorder matching/window evidence differs")
    if not broad_source and not scope_mask(matches, study).all():
        raise ValueError("reorder matching/window evidence differs")
    matches = matches.loc[
        matches.reorder_placed_utc.le(
            matches.original_cancel_utc + pd.Timedelta(days=days)
        )
    ].copy()
    matches["qualifying_non_cancelled"] = (
        matches.reorder_order_has_cancellation.eq(0)
        & matches.reorder_order_has_unknown_status.eq(0)
    )
    eligible = originals.loc[
        originals.usable_match_keys & originals.complete_followup, KEYS
    ]
    matches = matches.merge(eligible, on=KEYS, validate="many_to_one")
    # Deduplicate later lines and money across original cancellations.
    matches["reorder_known_net_sales"] = matches.reorder_known_net_sales.map(
        base.money
    )
    candidates = matches.copy()
    matches = matches.loc[scope_mask(matches, study)].copy()
    selected = matches.loc[matches.qualifying_non_cancelled]
    if (
        selected.groupby(REORDER_KEYS)[
            ["reorder_known_net_sales", "missing_sales_records"]
        ]
        .nunique(dropna=False)
        .gt(1)
        .any()
        .any()
    ):
        raise ValueError("conflicting repeated reorder amounts")
    reorders = selected.drop_duplicates(REORDER_KEYS).copy()
    missing = int(reorders.missing_sales_records.sum())
    known = base.decimal_sum(reorders.reorder_known_net_sales)
    measures = {
        "aged_orders": originals.original_order_id.nunique(),
        "aged_lines": len(originals),
        "aged_customers": originals.original_customer_id.nunique(),
        "aged_lines_missing_match_keys": int(
            (~originals.usable_match_keys).sum()
        ),
        "aged_lines_incomplete_followup": int(
            (~originals.complete_followup).sum()
        ),
        "eligible_aged_orders": originals.loc[
            originals.usable_match_keys & originals.complete_followup
        ].original_order_id.nunique(),
        "eligible_aged_customers": originals.loc[
            originals.usable_match_keys & originals.complete_followup
        ].original_customer_id.nunique(),
        "matched_non_cancelled_orders": reorders.reorder_order_id.nunique(),
        "matched_non_cancelled_lines": len(reorders),
        "customers_with_non_cancelled_reorder": (
            reorders.original_customer_id.nunique()
        ),
        "aged_orders_with_non_cancelled_reorder": (
            selected.original_order_id.nunique()
        ),
        "candidate_orders_excluded_for_cancellation": matches.loc[
            matches.reorder_order_has_cancellation.eq(1)
        ].reorder_order_id.nunique(),
        "candidate_orders_excluded_for_unknown_status": matches.loc[
            matches.reorder_order_has_unknown_status.eq(1)
        ].reorder_order_id.nunique(),
        "missing_sales_records": missing,
    }
    with duckdb.connect() as c:
        # Explicit precision avoids DuckDB's sampled pandas Decimal inference
        # choosing a type too small for later rows in a larger horizon.
        table = pa.Table.from_pandas(
            candidates.drop(columns=["reorder_known_net_sales"]),
            preserve_index=False,
        )
        table = table.append_column(
            "reorder_known_net_sales",
            pa.array(
                candidates.reorder_known_net_sales.tolist(),
                type=pa.decimal128(38, 5),
            ),
        )
        c.register("matches", table)
        counts = c.execute(
            render_template(
                canonical_sql_path(
                    "create_opportunity_aged_reorders-query-3.sql.j2"
                ),
                study=study,
            )
        ).fetchone()
        amount = c.execute(
            render_template(
                canonical_sql_path(
                    "create_opportunity_aged_reorders-query-4.sql.j2"
                ),
                study=study,
            )
        ).fetchone()[0]
    if (
        counts
        != (
            measures["matched_non_cancelled_orders"],
            len(reorders),
            measures["customers_with_non_cancelled_reorder"],
            measures["aged_orders_with_non_cancelled_reorder"],
        )
        or amount != known
    ):
        raise ValueError("independent reorder counts/sales do not reconcile")
    summary = pd.DataFrame(measures.items(), columns=["measure", "count"])
    sales = {
        "known_matching_line_net_sales": str(known),
        "matching_line_net_sales": None if missing else str(known),
    }
    return {
        "originals": originals,
        "matches": matches,
        "reorders": reorders,
        "summary": summary,
    }, sales


def render_sql(
    start_date, end_date, as_of_date, days, all_studies=False, all_chewy=False
):
    params = base.parameters(start_date, end_date)
    date.fromisoformat(as_of_date)
    if days < 1:
        raise ValueError("follow-up must be positive")
    template = (
        "opportunity_chewy_follow_up.sql"
        if all_chewy
        else "opportunity_aged_reorders.sql"
    )
    return (
        Environment(undefined=StrictUndefined)
        .from_string((canonical_sql_path(template)).read_text())
        .render(
            **params,
            followup_days=days,
            as_of_date=as_of_date,
            all_studies=all_studies,
        )
    )

"""Validate study-linked uploads and prescription associations."""

import json
from datetime import date, timedelta

import pandas as pd

ENTITY_COLUMNS = [
    "upload_id",
    "upload_customer_id",
    "state_name",
    "created_ts_utc",
    "state_changed_ts_utc",
]


def parameters(start, end, upload_start, as_of):
    start, end, upload_start, as_of = map(
        date.fromisoformat, [start, end, upload_start, as_of]
    )
    if start >= end or upload_start > start or as_of < end:
        raise ValueError(
            "require upload start <= study start < exclusive study end <= "
            "as-of date"
        )
    return {
        "start_date": str(start),
        "end_date": str(end),
        "upload_start_date": str(upload_start),
        "upload_end_date": str(end + timedelta(days=11)),
        "as_of_date": str(as_of),
    }


def validate(frame, params):
    """Validate source versions before reducing joins to one row per entity."""
    f = frame.rename(columns=str.lower).copy()
    for col in [
        "created_ts_utc",
        "state_changed_ts_utc",
        "rx_creation_datetime",
        "order_cancel_time",
    ]:
        f[col] = pd.to_datetime(
            f[col], utc=True, format="mixed", errors="raise"
        )
    if f.upload_id.isna().any():
        raise ValueError("missing UPLOAD_ID")
    if (
        f.groupby("upload_id")[ENTITY_COLUMNS[1:]]
        .nunique(dropna=False)
        .gt(1)
        .any()
        .any()
    ):
        raise ValueError("conflicting entity states, timestamps or customers")
    matched = f.matched_rx_id.notna()
    rx = f.loc[matched]
    if (
        rx.groupby("matched_rx_id")[
            [
                "rx_customer_id",
                "rx_creation_datetime",
                "first_order_id",
                "first_orderitem_id",
                "first_order_line_id",
            ]
        ]
        .nunique(dropna=False)
        .gt(1)
        .any()
        .any()
    ):
        raise ValueError("conflicting prescription source values")
    if (
        rx.upload_rx_id.ne(rx.matched_rx_id).any()
        or rx.upload_customer_id.ne(rx.rx_customer_id).any()
        or not rx.upload_rx_id.str.fullmatch(r"[A-Za-z0-9_-]+").all()
    ):
        raise ValueError("invalid RX/customer match")
    if not rx.rx_creation_datetime.between(
        pd.Timestamp(params["start_date"], tz="UTC"),
        pd.Timestamp(params["end_date"], tz="UTC"),
        inclusive="left",
    ).all():
        raise ValueError("prescription outside study window")
    created = f.created_ts_utc.dropna()
    if not created.between(
        pd.Timestamp(params["upload_start_date"], tz="UTC"),
        pd.Timestamp(params["upload_end_date"], tz="UTC"),
        inclusive="left",
    ).all():
        raise ValueError("entity creation outside discovery window")
    line = f.matched_order_id.notna() | f.matched_order_line_id.notna()
    if (
        not f.loc[line, ["matched_order_id", "matched_order_line_id"]]
        .notna()
        .all()
        .all()
        or f.loc[line, "matched_order_id"]
        .ne(f.loc[line, "first_order_id"])
        .any()
        or f.loc[line, "matched_order_line_id"]
        .ne(f.loc[line, "first_order_line_id"])
        .any()
    ):
        raise ValueError("first-order join keys disagree")
    if (
        not f.loc[line, "reason_variants"].eq(1).all()
        or f.loc[line, "cancel_variants"].gt(1).any()
    ):
        raise ValueError("conflicting first-order cancellation source values")
    if (
        f.loc[line]
        .groupby(["matched_order_id", "matched_order_line_id"])[
            ["order_cancel_reason", "order_cancel_time"]
        ]
        .nunique(dropna=False)
        .gt(1)
        .any()
        .any()
    ):
        raise ValueError("conflicting first-order cancellation associations")
    expected = (
        matched
        & line
        & f.order_cancel_reason.astype("string")
        .str.strip()
        .str.lower()
        .eq("aged order")
        & f.order_cancel_time.le(pd.Timestamp(params["as_of_date"], tz="UTC"))
    ).fillna(False)
    if not f.aged_association.eq(expected).all():
        raise ValueError("aged cutoff evidence disagrees")
    f["aged_association"] = expected
    # Full source keeps expansions outside the study; associations contain only
    # matching prescriptions, collapsing identical entity/Rx/line rows.
    associations = (
        f.loc[matched]
        .drop_duplicates(
            [
                "upload_id",
                "matched_rx_id",
                "first_order_id",
                "first_order_line_id",
            ]
        )
        .copy()
    )
    counts = associations.groupby("upload_id").agg(
        matched_prescriptions=("matched_rx_id", "nunique"),
        aged_entity=("aged_association", "any"),
    )
    entities = (
        f[ENTITY_COLUMNS]
        .drop_duplicates("upload_id")
        .merge(counts, on="upload_id", how="left")
    )
    if entities.matched_prescriptions.isna().any():
        raise ValueError(
            "discovered entity has no matching study prescription"
        )
    entities["missing_creation"] = entities.created_ts_utc.isna()
    entities["missing_state_change"] = entities.state_changed_ts_utc.isna()
    entities["unknown_discovery_window"] = entities.missing_creation
    entities["elapsed_hours"] = (
        entities.state_changed_ts_utc - entities.created_ts_utc
    ).dt.total_seconds() / 3600
    entities["usable_duration"] = entities.elapsed_hours.notna()
    entities["negative_duration"] = entities.elapsed_hours.lt(0)
    # JSON labels distinguish literal states from missing states.
    entities["state_label"] = entities.state_name.map(
        lambda s: "[NULL state]" if pd.isna(s) else json.dumps(s)
    )
    audit = pd.DataFrame(
        [
            ("source association rows", len(f)),
            ("distinct source association rows", len(f.drop_duplicates())),
            (
                "identical source/expansion rows collapsed",
                len(f) - len(f.drop_duplicates()),
            ),
            ("matched prescription associations", len(associations)),
            (
                "unmatched RX expansions retained in source",
                int((~matched).sum()),
            ),
            ("all entities", len(entities)),
            ("aged entities", int(entities.aged_entity.sum())),
            (
                "entities with multiple matched prescriptions",
                int(entities.matched_prescriptions.gt(1).sum()),
            ),
        ],
        columns=["measure", "count"],
    )
    return associations, entities, audit

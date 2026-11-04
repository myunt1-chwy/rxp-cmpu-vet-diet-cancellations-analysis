"""Validate and normalize prescription/upload evidence used across analyses."""

from datetime import date

import pandas as pd

AUDIT_COLUMNS = [
    "window_upload_rows",
    "invalid_upload_source_rows",
    "uploads_missing_customer",
    "uploads_invalid_customer",
    "upload_rows_missing_rx",
    "upload_rows_malformed_rx",
]
TIMING_VARIANT = "accepted-state-change_order-placed"


def date_parameters(start, end, upload_start=None):
    start, end = date.fromisoformat(start), date.fromisoformat(end)
    upload_start = date.fromisoformat(upload_start) if upload_start else start
    if start >= end:
        raise ValueError("start date must precede exclusive end date")
    if upload_start > start:
        raise ValueError(
            "upload start date must be on or before prescription start date"
        )
    return {
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "upload_start_date": upload_start.isoformat(),
    }


def period_name(start, end, upload_start=None):
    period = f"{start}_{end}"
    return (
        f"{period}_uploads-from-{upload_start}"
        if upload_start and upload_start != start
        else period
    )


def validate_accepted_uploads(frame):
    """Entity presence and usable state-change time are separate evidence."""
    present = frame.upload_count.gt(0)
    if (
        present
        & (
            frame.selected_upload_id.isna()
            | frame.selected_upload_state.ne("ACCEPTED").fillna(True)
        )
    ).any():
        raise ValueError("invalid selected accepted upload entity")
    if (
        ~present
        & (
            frame.selected_upload_id.notna()
            | frame.selected_upload_state.notna()
        )
    ).any():
        raise ValueError("selected upload without accepted entity evidence")
    for column in ["first_upload_at_utc", "upload_state_changed_at_utc"]:
        frame[column] = pd.to_datetime(frame[column], utc=True, errors="raise")
    if (~present & frame.upload_state_changed_at_utc.notna()).any():
        raise ValueError("state-change time without accepted entity")
    frame["missing_accepted_state_change"] = (
        present & frame.upload_state_changed_at_utc.isna()
    )
    frame["state_change_before_entity_creation"] = (
        frame.upload_state_changed_at_utc.lt(frame.first_upload_at_utc)
    )
    return frame


def prepare_prescription_uploads(frame):
    frame = frame.rename(columns=str.lower).copy()
    if (
        frame.rx_id.isna().any()
        or frame.rx_id.duplicated().any()
        or not frame.rx_source_rows.eq(1).all()
    ):
        raise ValueError("missing or duplicate prescription source IDs")
    if not frame.order_source_rows.isin([0, 1]).all():
        raise ValueError("duplicate order source records")
    if (
        frame.upload_count.isna().any()
        or frame.upload_count.lt(0).any()
        or frame.upload_count.mod(1).ne(0).any()
    ):
        raise ValueError("invalid upload counts")
    if frame.upload_count.gt(0).ne(frame.first_upload_at_utc.notna()).any():
        raise ValueError("upload count/timestamp evidence disagrees")
    if (
        frame.cohort_window_upload_count.isna().any()
        or frame.cohort_window_upload_count.lt(0).any()
        or frame.cohort_window_upload_count.mod(1).ne(0).any()
        or frame.cohort_window_upload_count.gt(frame.upload_count).any()
    ):
        raise ValueError("invalid prescription-window upload counts")
    if (frame.first_order_id.isna() & frame.order_source_rows.ne(0)).any():
        raise ValueError("order match without a first order ID")
    audits = {}
    for column in AUDIT_COLUMNS:
        if (
            frame[column].nunique(dropna=False) > 1
            or frame[column].isna().any()
        ):
            raise ValueError("inconsistent upload audits")
        audits[column] = int(frame[column].iloc[0]) if len(frame) else None
    if audits["invalid_upload_source_rows"]:
        raise ValueError("missing or duplicate upload source IDs")
    frame["channel"] = (
        frame.approval_channel.astype("string")
        .str.strip()
        .replace("", pd.NA)
        .fillna("[Unknown approval channel]")
    )
    audits.update(
        cohort_prescriptions=len(frame),
        prescriptions_with_upload=int(frame.upload_count.gt(0).sum()),
        prescriptions_matched_only_by_earlier_uploads=int(
            (
                frame.upload_count.gt(0)
                & frame.cohort_window_upload_count.eq(0)
            ).sum()
        ),
        prescriptions_missing_customer=int(frame.customer_id.isna().sum()),
    )
    return frame, audits

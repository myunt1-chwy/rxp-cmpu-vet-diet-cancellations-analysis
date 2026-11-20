import importlib.util
from pathlib import Path

import pandas as pd
import pytest

PATH = (
    Path(__file__).parents[1] / "targets/study-population-counts/src/python/"
    "refresh_study_population_inputs.py"
)
SPEC = importlib.util.spec_from_file_location("study_population_refresh", PATH)
refresh = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(refresh)


def sources():
    line = pd.DataFrame(
        [
            {
                "rx_id": "RX-A",
                "customer_id": 7,
                "first_order_id": 101,
                "first_order_line_id": 11,
                "approval_channel": "CUSTOMER_UPLOAD",
                "line_source_rows": 1,
                "line_status_variants": 1,
                "cancel_reason_variants": 1,
                "order_cancel_reason": "Aged Order",
            }
        ]
    )
    decisions = pd.DataFrame(
        [
            {
                "rx_id": "RX-A",
                "customer_id": 7,
                "first_order_id": 101,
                "first_order_line_id": 11,
                "order_id": 101,
                "order_line_id": 11,
                "approval_channel": "CUSTOMER_UPLOAD",
                "cancel_reason": "aged order",
            }
        ]
    )
    uploads = pd.DataFrame(
        [
            {
                "matched_rx_id": "RX-A",
                "rx_customer_id": 7,
                "upload_customer_id": 7,
                "first_order_id": 101,
                "first_order_line_id": 11,
                "matched_order_id": 101,
                "matched_order_line_id": 11,
            }
        ]
    )
    return line, decisions, uploads


def test_refresh_inputs_accept_reconciled_keys_and_normalized_reasons():
    refresh.validate_sources(*sources())


@pytest.mark.parametrize(
    "source_index,field,value,message",
    [
        (1, "customer_id", 9, "Decision customer_id"),
        (1, "first_order_line_id", 12, "Decision first_order_line_id"),
        (1, "order_line_id", 12, "both first-order keys"),
        (1, "cancel_reason", "Other", "Cancellation reasons"),
        (2, "upload_customer_id", 9, "Upload customer"),
        (2, "matched_order_line_id", 12, "both first-order keys"),
    ],
)
def test_refresh_inputs_reject_inconsistent_cross_source_evidence(
    source_index, field, value, message
):
    values = list(sources())
    values[source_index].loc[0, field] = value
    with pytest.raises(ValueError, match=message):
        refresh.validate_sources(*values)

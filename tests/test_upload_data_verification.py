"""Source reconciliation and report rendering for the upload comparison."""

import pandas as pd
import pytest

from src.python.create_upload_data_verification import (
    SOURCES,
    comparison,
    render,
)


def source_frame():
    return pd.DataFrame(
        [
            (SOURCES[0], "RX_&TYPE", 2, 1, False, "2026-11-02 16:00:00"),
            (SOURCES[0], None, 1, 0, False, "2026-11-02 16:00:00"),
            (SOURCES[0], None, 3, 1, True, "2026-11-02 16:00:00"),
            (SOURCES[1], "ORDER", 4, 2, False, "2026-11-02 16:00:00"),
            (SOURCES[1], None, 4, 2, True, "2026-11-02 16:00:00"),
        ],
        columns=[
            "source_table",
            "associated_resource_type",
            "entry_count",
            "entries_with_nonzero_rx_id",
            "is_total",
            "extracted_at_utc",
        ],
    )


def test_types_from_either_source_and_null_are_retained():
    rows, totals, timestamp = comparison(source_frame())
    assert rows == [("ORDER", 0, 4), ("RX_&TYPE", 2, 0), (None, 1, 0)]
    assert totals == [3, 4]
    assert timestamp == "2026-11-02 16:00:00"
    md, tex = render(source_frame())
    assert "| [SQL NULL] | 1 | 0 | 0 | 0 |" in md
    assert r"{RX\_\&TYPE} & 2 & 1 & 0 & 0" in tex
    assert "{[SQL NULL]} & 1 & 0 & 0 & 0" in tex
    assert "{Total} & 3 & 1 & 4 & 2" in tex


def test_mismatched_independent_total_prevents_publication():
    frame = source_frame()
    frame.loc[2, "entry_count"] = 5
    with pytest.raises(ValueError, match="do not reconcile"):
        render(frame)


def test_empty_sources_still_render_totals_and_null():
    frame = source_frame().loc[lambda value: value.is_total].copy()
    frame["entry_count"] = 0
    frame["entries_with_nonzero_rx_id"] = 0
    assert comparison(frame)[:2] == ([(None, 0, 0)], [0, 0])


def test_duplicate_groups_are_rejected():
    frame = source_frame()
    with pytest.raises(ValueError, match="Duplicate resource-type"):
        comparison(pd.concat([frame, frame.iloc[:1]], ignore_index=True))

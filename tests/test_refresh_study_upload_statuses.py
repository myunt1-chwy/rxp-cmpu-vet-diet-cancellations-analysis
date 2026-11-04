import importlib.util
from pathlib import Path

import pandas as pd
import pytest

PATH = (
    Path(__file__).parents[1]
    / "targets"
    / "no-recorded-cancellation-upload-statuses/src/python"
    / "refresh_study_upload_statuses.py"
)
SPEC = importlib.util.spec_from_file_location("coverage_refresh", PATH)
refresh = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(refresh)


def inputs():
    source = pd.DataFrame(
        [
            {
                "rx_id": "rx-a",
                "customer_id": 7,
                "order_id": 101,
                "order_line_id": 11,
                "line_customer_id": 7,
                "source_rows": 1,
                "shipment_rows": 2,
                "duplicate_shipment_rows": 0,
                "customer_variants": 1,
                "order_status_variants": 1,
                "line_status_variants": 1,
                "reason_variants": 1,
                "order_cancellation_reason": "aged order",
                "line_item_status": "X",
                "order_status": "X",
                "rx_status": "PENDING",
                "extracted_at_utc": "2026-11-04T13:00:00Z",
            }
        ]
    )
    study = source[refresh.details.MATCH + ["line_item_status"]].copy()
    study["reason_key"] = "aged order"
    return (
        source,
        study,
        source[["rx_id", "order_status"]],
        source[["rx_id", "rx_status"]],
    )


def test_accepts_multiple_distinct_shipments_and_changed_cohort_size():
    source, study, baseline, decisions = inputs()
    result = refresh.validate_statuses(source, study, baseline, decisions)
    assert len(result) == 1
    assert result.shipment_rows.iloc[0] == 2


@pytest.mark.parametrize(
    "column,value",
    [
        ("order_id", 999),
        ("line_customer_id", 8),
        ("duplicate_shipment_rows", 1),
        ("reason_variants", 2),
        ("order_cancellation_reason", "customer request"),
        ("line_item_status", "D"),
        ("order_status", "S"),
        ("rx_status", "APPROVED"),
    ],
)
def test_rejects_inconsistent_status_inputs(column, value):
    source, study, baseline, decisions = inputs()
    source.loc[0, column] = value
    with pytest.raises(ValueError):
        refresh.validate_statuses(source, study, baseline, decisions)


def test_rejects_missing_status_match():
    source, study, baseline, decisions = inputs()
    with pytest.raises(ValueError, match="membership"):
        refresh.validate_statuses(source.iloc[:0], study, baseline, decisions)


def test_empty_detail_subgroup_has_zero_counts():
    source, study, _, _ = inputs()
    source = source.iloc[:0]
    cohort = study.iloc[:0]
    uploads = pd.DataFrame(columns=refresh.details.MATCH + ["upload_id"])
    _, _, summary, audit = refresh.details.analyze(
        source,
        cohort,
        uploads,
        "aged order",
        extracted_at_utc="2026-11-04T13:00:00Z",
    )
    assert summary.empty
    assert audit["retained_lines"] == 0


def test_failed_install_restores_previous_inputs(tmp_path, monkeypatch):
    staged = []
    originals = {}
    for index in range(2):
        part = tmp_path / f"stage-{index}"
        target = tmp_path / f"target-{index}"
        part.mkdir()
        target.mkdir()
        for name in ["source.parquet", "source.sql", "source.json"]:
            (part / name).write_text("new")
            (target / name).write_text("old")
            originals[target / name] = "old"
        staged.append((part, target))
    replace = Path.replace

    def fail_second_subset(path, target):
        if path == staged[1][0] / "source.sql":
            raise OSError("simulated installation failure")
        return replace(path, target)

    monkeypatch.setattr(Path, "replace", fail_second_subset)
    with pytest.raises(OSError, match="simulated"):
        refresh.install_sources(staged)
    assert all(path.read_text() == value for path, value in originals.items())


@pytest.mark.parametrize("ids", [("a", "a", "b"), ("a", "a", None)])
def test_coverage_rejects_mixed_or_missing_runs(monkeypatch, ids):
    manifests = iter({"refresh_run_id": value} for value in ids)
    monkeypatch.setattr(
        refresh.coverage,
        "load_source",
        lambda _: (pd.DataFrame(), next(manifests)),
    )
    with pytest.raises(ValueError, match="mix refresh runs"):
        refresh.coverage.main()

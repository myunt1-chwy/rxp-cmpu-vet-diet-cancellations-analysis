import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from click.testing import CliRunner
import numpy as np
import pandas as pd

from src.python import create_aged_upload_lifecycle_distribution as lifecycle
from src.python.create_vdam_upload_distribution import histogram, render_sql


START, END = "2026-07-30", "2026-10-21"


def cohort():
    return pd.DataFrame({
        "rx_id": ["RX1", "RX2", "RX3"], "elapsed_hours": [-1.0, 0.0, 49.0],
    })


def write_upload_cache(directory):
    directory.mkdir(parents=True, exist_ok=True)
    frame = pd.DataFrame([
        ("a", "RX1", 1, "2026-08-01", None, "matched", -1.0),
        ("b", "RX1", 2, "2026-08-02", "Aged Order", "matched", 5.0),
        ("c", "RX2", 3, "2026-08-01", "Aged Order", "matched", 0.0),
        ("d", "RX3", 4, "2026-08-01", None, "matched", 49.0),
    ], columns=["upload_id", "rx_id", "order_id", "uploaded_at_utc", "order_cancel_reason", "row_status", "elapsed_hours"])
    frame.to_parquet(directory / "uploads.parquet", index=False)
    (directory / "source.json").write_text(json.dumps({
        "sql": render_sql(START, END), "start_date": START, "end_date_exclusive": END,
        "extracted_at_utc": "2026-10-21T00:00:00+00:00",
    }))
    return frame


class AgedLifecycleTests(unittest.TestCase):
    def test_left_join_preserves_missing_and_unmatched_separately(self):
        states = pd.DataFrame({"RX_ID": ["RX1", "RX2"], "RX_LIFECYCLE_STATE": ["VET_REVIEW", None]})
        merged = lifecycle.attach_states(cohort(), states)
        self.assertEqual(merged.lifecycle_state.tolist(), ["VET_REVIEW", lifecycle.MISSING, lifecycle.UNMATCHED])
        self.assertEqual(len(merged), 3)

    def test_duplicate_null_and_unexpected_state_ids_fail(self):
        for identifiers in [["RX1", "RX1"], [None], ["RX4"]]:
            with self.subTest(identifiers=identifiers), self.assertRaises(ValueError):
                lifecycle.attach_states(cohort(), pd.DataFrame({"rx_id": identifiers, "rx_lifecycle_state": ["VET_REVIEW"] * len(identifiers)}))

    def test_stacks_preserve_bin_boundaries_and_counts(self):
        aged = cohort()
        states = pd.DataFrame({"rx_id": aged.rx_id, "rx_lifecycle_state": ["A", "B", "A"]})
        merged = lifecycle.attach_states(aged, states)
        bins = histogram(aged.elapsed_hours)
        stacked = lifecycle.state_histograms(merged, bins)
        self.assertEqual(len(stacked), 100)
        np.testing.assert_array_equal(
            stacked.groupby(["lower_hours", "upper_hours"]).prescriptions.sum().to_numpy(),
            bins.prescriptions.to_numpy(),
        )
        self.assertEqual(stacked.prescriptions.sum(), 3)
        self.assertEqual(stacked.loc[stacked.upper_hours.eq(49), "prescriptions"].sum(), 1)
        self.assertEqual(stacked.loc[stacked.lower_hours.eq(-1), "prescriptions"].sum(), 1)

    def test_reject_duration_outside_shared_bin_range(self):
        bins = histogram(pd.Series([0.0, 1.0]))
        merged = cohort().assign(lifecycle_state="A")
        with self.assertRaisesRegex(ValueError, "reconcile"):
            lifecycle.state_histograms(merged, bins)

    def test_cohort_selection_precedes_aged_filter_and_fingerprint_detects_change(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            frame = write_upload_cache(path)
            aged, bins, fingerprint, _ = lifecycle.load_cohort(path, START, END)
            self.assertEqual(aged.rx_id.tolist(), ["RX2"])
            self.assertEqual(bins.lower_hours.iloc[0], -1)
            self.assertEqual(bins.upper_hours.iloc[-1], 49)
            frame.iloc[::-1].to_parquet(path / "uploads.parquet", index=False)
            self.assertEqual(lifecycle.load_cohort(path, START, END)[2], fingerprint)
            frame.loc[frame.rx_id.eq("RX2"), "elapsed_hours"] = 2.0
            frame.to_parquet(path / "uploads.parquet", index=False)
            self.assertNotEqual(lifecycle.load_cohort(path, START, END)[2], fingerprint)

    def test_upload_cache_missing_or_stale_provenance(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            with self.assertRaisesRegex(ValueError, "first run: make"):
                lifecycle.load_cohort(path, START, END)
            write_upload_cache(path)
            (path / "source.json").write_text('{}')
            with self.assertRaisesRegex(ValueError, "provenance"):
                lifecycle.load_cohort(path, START, END)

    def test_state_cache_checks_fingerprint_query_and_timestamp(self):
        valid = {"cohort_fingerprint": "one", "sql": "query", "extracted_at_utc": "now"}
        lifecycle.validate_state_cache(valid, "one", "query")
        for key in valid:
            broken = {**valid, key: None}
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, "cache"):
                lifecycle.validate_state_cache(broken, "one", "query")

    def test_sql_ids_are_deduplicated_sorted_and_validated(self):
        sql = lifecycle.state_sql(pd.Series(["RX2", "RX1", "RX2"]))
        self.assertIn("'RX1', 'RX2'", sql)
        self.assertIn("RX_LIFECYCLE_STATE", sql)
        with self.assertRaises(ValueError):
            lifecycle.state_sql(pd.Series(["RX1' OR 1=1"]))
        self.assertIn("WHERE FALSE", lifecycle.state_sql(pd.Series([], dtype=str)))

    def test_cached_and_print_sql_modes_do_not_query(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            base = root / "data/vdam-upload-distribution" / f"{START}_{END}"
            write_upload_cache(base)
            aged, _, fingerprint, _ = lifecycle.load_cohort(base, START, END)
            state_dir = base / "aged-lifecycle"
            state_dir.mkdir()
            pd.DataFrame({"rx_id": aged.rx_id, "rx_lifecycle_state": ["VET_REVIEW"]}).to_parquet(state_dir / "states.parquet", index=False)
            metadata = {"cohort_fingerprint": fingerprint, "sql": lifecycle.state_sql(aged.rx_id), "extracted_at_utc": "now"}
            (state_dir / "source.json").write_text(json.dumps(metadata))
            args = ["--start-date", START, "--end-date", END]
            with patch.object(lifecycle, "ROOT", root), patch.object(lifecycle.subprocess, "run") as query, patch.object(lifecycle, "write_outputs") as output:
                cached = CliRunner().invoke(lifecycle.main, [*args, "--cached"])
                self.assertEqual(cached.exit_code, 0, cached.output)
                self.assertEqual(output.call_count, 1)
                printed = CliRunner().invoke(lifecycle.main, [*args, "--print-sql"])
                self.assertEqual(printed.exit_code, 0, printed.output)
                self.assertIn("RX_LIFECYCLE_STATE", printed.output)
                query.assert_not_called()
                self.assertEqual(output.call_count, 1)

    def test_empty_result_writes_table_and_removes_stale_png(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            (path / f"{lifecycle.STEM}.png").write_bytes(b"stale")
            merged = cohort().iloc[:0].assign(lifecycle_state=pd.Series(dtype=str))
            metadata = {"start_date": START, "end_date_exclusive": END, "upload_extracted_at_utc": "before",
                        "extracted_at_utc": "now", "cohort_fingerprint": "hash"}
            lifecycle.write_outputs(merged, histogram(pd.Series([], dtype=float)), metadata, path, path)
            self.assertFalse((path / f"{lifecycle.STEM}.png").exists())
            self.assertIn("No aged-order prescriptions", (path / f"{lifecycle.STEM}.md").read_text())

    def test_empty_cohort_skips_snowflake_and_creates_reusable_empty_cache(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            base = root / "data/vdam-upload-distribution" / f"{START}_{END}"
            frame = write_upload_cache(base)
            frame["order_cancel_reason"] = None
            frame.to_parquet(base / "uploads.parquet", index=False)
            args = ["--start-date", START, "--end-date", END]
            with patch.object(lifecycle, "ROOT", root), patch.object(lifecycle.subprocess, "run") as query:
                for flags in [[], ["--cached"]]:
                    result = CliRunner().invoke(lifecycle.main, [*args, *flags])
                    self.assertEqual(result.exit_code, 0, result.output)
                query.assert_not_called()
            self.assertTrue(pd.read_parquet(base / "aged-lifecycle/states.parquet").empty)


if __name__ == "__main__":
    unittest.main()

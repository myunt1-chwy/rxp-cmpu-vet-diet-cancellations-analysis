from pathlib import Path
import tempfile
import unittest

import duckdb
import numpy as np
import pandas as pd
from click.testing import CliRunner

from src.python.create_vdam_upload_distribution import (
    CANCEL_GROUPS, cancellation_groups, cancellation_histograms,
    histogram, main, render_sql, summarize, write_outputs,
)


def query_fixture():
    """Execute the actual query against fixtures, adapting only Snowflake syntax."""
    connection = duckdb.connect()
    connection.execute("CREATE MACRO TRY_TO_NUMBER(v) AS TRY_CAST(v AS DECIMAL(38,0))")
    connection.execute("CREATE TABLE uploads_source(upload_id VARCHAR, order_id VARCHAR, created_ts_utc TIMESTAMP, upload_type VARCHAR)")
    connection.execute("CREATE TABLE orders_source(order_id BIGINT, order_placed_dttm TIMESTAMP)")
    connection.executemany("INSERT INTO uploads_source VALUES (?, ?, ?, ?)", [
        ("a", "001", "2026-07-30 00:00:00", "DIET_PRESCRIPTION"),
        ("b", "1", "2026-07-30 01:00:00", "DIET_PRESCRIPTION"),
        ("c", "2", "2026-10-20 23:59:59", "DIET_PRESCRIPTION"),
        ("d", "3", "2026-10-21 00:00:00", "DIET_PRESCRIPTION"),
        ("e", "4", "2026-07-29 23:59:59", "DIET_PRESCRIPTION"),
        ("f", None, "2026-08-01", "DIET_PRESCRIPTION"),
        ("g", "bad", "2026-08-01", "DIET_PRESCRIPTION"),
        ("h", "5", "2026-08-01", "DIET_PRESCRIPTION"),
        ("i", "6", "2026-08-01", "DIET_PRESCRIPTION"),
        ("j", "7", "2026-08-01", "SNAIL_MAIL"),
        ("k", "8", None, "DIET_PRESCRIPTION"),
        ("l", "9", "2026-08-01", "DIET_PRESCRIPTION"),
    ])
    connection.executemany("INSERT INTO orders_source VALUES (?, ?)", [
        (1, "2026-07-30 00:30:00"), (2, "2026-10-20 23:00:00"),
        (6, None), (9, "2026-07-31"), (9, "2026-07-31"),
    ])
    connection.execute("ALTER TABLE orders_source ADD COLUMN order_cancel_reason VARCHAR")
    connection.execute("UPDATE orders_source SET order_cancel_reason = 'Aged Order' WHERE order_id = 2")
    connection.execute("ALTER TABLE uploads_source ADD COLUMN rx_id VARCHAR DEFAULT '{RX1}'")
    connection.execute("ALTER TABLE uploads_source ADD COLUMN associated_resource_type VARCHAR DEFAULT 'DIET_PRESCRIPTION'")
    connection.execute("ALTER TABLE uploads_source ADD COLUMN has_associated_rx BOOLEAN DEFAULT TRUE")
    connection.execute("ALTER TABLE uploads_source ADD COLUMN has_uploaded_file BOOLEAN DEFAULT TRUE")
    connection.execute("UPDATE uploads_source SET rx_id = '{RX2,RX3,RX3}' WHERE upload_id = 'c'")
    connection.executemany("INSERT INTO uploads_source VALUES (?, ?, ?, ?, ?, ?, ?, ?)", [
        ("m", "2", "2026-10-20 23:59:00", "DIET_PRESCRIPTION", "{RX1}", "DIET_PRESCRIPTION", True, True),
        ("n", "1", "2026-08-01", "DIET_PRESCRIPTION", "{RX4}", "DIET_PRESCRIPTION", False, True),
        ("o", "1", "2026-08-01", "DIET_PRESCRIPTION", "{RX5}", "DIET_PRESCRIPTION", True, False),
        ("p", "1", "2026-08-01", "DIET_PRESCRIPTION", "{RX6}", "OTHER", True, True),
        ("q", "1", "2026-08-01", "DIET_PRESCRIPTION", "{RX7}", "DIET_PRESCRIPTION", None, True),
        ("r", "1", "2026-08-01", "DIET_PRESCRIPTION", "{RX8}", "DIET_PRESCRIPTION", True, None),
    ])
    sql = render_sql("2026-07-30", "2026-10-21").replace(
        "EDLDB.BT_HCA_HCDM.RXP_UPLOAD_ENTITY", "uploads_source"
    ).replace("EDLDB.ECOM.ORDERS", "orders_source").replace("TIMESTAMP_NTZ", "TIMESTAMP").replace(
        "LATERAL FLATTEN(INPUT => SPLIT(TRIM(COALESCE(u.RX_IDS, ''), '{}'), ','), OUTER => TRUE) p",
        "LATERAL UNNEST(STRING_SPLIT(TRIM(COALESCE(u.RX_IDS, ''), '{}'), ',')) p(VALUE)",
    )
    result = connection.execute(sql).df()
    connection.close()
    return result.rename(columns=str.lower)


class UploadDistributionTests(unittest.TestCase):
    def test_cohort_join_first_upload_and_exclusion_reconciliation(self):
        frame = query_fixture()
        self.assertEqual(set(frame.upload_id), set("abcfghilm"))
        self.assertEqual(frame.loc[frame.upload_id.eq("l"), "row_status"].item(), "duplicate_order_rows")
        selected, counts = summarize(frame[frame.upload_id.ne("l")])
        self.assertEqual(set(selected.upload_id), {"a", "c"})
        self.assertEqual(set(selected.rx_id), {"RX1", "RX2", "RX3"})
        self.assertEqual(frame.upload_id.eq("c").sum(), 2)
        self.assertEqual(selected.loc[selected.upload_id.eq("a"), "elapsed_hours"].item(), -0.5)
        self.assertAlmostEqual(selected.loc[selected.rx_id.eq("RX2"), "elapsed_hours"].item(), 3599 / 3600)
        self.assertEqual(counts["qualifying_uploads"], 8)
        self.assertEqual(counts["prescription_upload_rows"], 9)
        self.assertEqual(counts["eligible_prescriptions"], 3)
        self.assertEqual(counts["negative_prescriptions"], 1)
        self.assertEqual(counts["repeat_matched_prescription_uploads"], 2)
        self.assertEqual(counts["prescriptions_linked_to_multiple_orders"], 1)
        self.assertEqual(selected.loc[selected.rx_id.eq("RX1"), "cancel_group"].item(), "Not cancelled")
        self.assertEqual(selected.loc[selected.rx_id.eq("RX2"), "cancel_group"].item(), "Aged orders")
        self.assertEqual(sum(counts[s] for s in ("missing_prescription_id", "missing_order_id", "invalid_order_id", "unmatched_order", "missing_order_timestamp", "matched")), 9)

    def test_duplicate_orders_fail_instead_of_silently_choosing_timestamp(self):
        with self.assertRaisesRegex(ValueError, "duplicate order"):
            summarize(query_fixture())

    def test_duplicate_uploads_fail(self):
        frame = query_fixture()
        with self.assertRaisesRegex(ValueError, "upload/prescription pairs"):
            summarize(pd.concat([frame, frame.iloc[:1]]))

    def test_missing_and_malformed_prescription_ids(self):
        frame = query_fixture().query("upload_id == 'a'").copy()
        frame["rx_id"] = None
        frame["row_status"] = "missing_prescription_id"
        selected, counts = summarize(frame)
        self.assertTrue(selected.empty)
        self.assertEqual(counts["missing_prescription_id"], 1)
        frame["rx_id"] = "{RX1,RX2}"
        frame["row_status"] = "matched"
        with self.assertRaisesRegex(ValueError, "prescription ID format"):
            summarize(frame)

    def test_first_matched_upload_is_stable_when_rows_are_reordered(self):
        frame = query_fixture().query("upload_id != 'l'")
        first, counts = summarize(frame)
        reordered, other_counts = summarize(frame.iloc[::-1])
        self.assertEqual(first.set_index("rx_id").upload_id.to_dict(),
                         reordered.set_index("rx_id").upload_id.to_dict())
        self.assertEqual(counts, other_counts)

    def test_exact_bins_boundaries_and_maximum(self):
        bins = histogram(pd.Series(np.arange(-25, 26)))
        self.assertEqual(len(bins), 50)
        self.assertEqual(bins.prescriptions.sum(), 51)
        self.assertEqual(bins.prescriptions.iloc[-1], 2)
        self.assertTrue((bins.prescriptions.iloc[:-1] == 1).all())
        self.assertAlmostEqual(bins.percent.sum(), 100)
        self.assertTrue(np.allclose(bins.upper_hours - bins.lower_hours, 1))

    def test_constant_range_and_empty_bins(self):
        bins = histogram(pd.Series([2.0, 2.0]))
        self.assertEqual(len(bins), 50)
        self.assertEqual(bins.lower_hours.iloc[0], 1.5)
        self.assertEqual(bins.upper_hours.iloc[-1], 2.5)
        self.assertEqual((bins.prescriptions == 0).sum(), 49)
        self.assertEqual(bins.prescriptions.sum(), 2)

    def test_cancellation_reason_buckets(self):
        reasons = pd.Series([None, pd.NA, "Aged Order", "Customer Initiated Cancellation",
                             "Customer Request", "Pharmacy Rejection", "Other", "",
                             " aged order ", "CUSTOMER REQUEST", "Unknown new reason"])
        self.assertEqual(cancellation_groups(reasons).tolist(), [
            "Not cancelled", "Not cancelled", "Aged orders", "Customer initiated",
            "Customer requested", "Other", "Other", "Other", "Aged orders",
            "Customer requested", "Other",
        ])

    def test_cancellation_bins_share_edges_and_reconcile_to_overall(self):
        selected, _ = summarize(query_fixture().query("upload_id != 'l'"))
        overall = histogram(selected.elapsed_hours)
        grouped = cancellation_histograms(selected, overall)
        self.assertEqual(len(grouped), 250)
        self.assertEqual(grouped.cancel_group.drop_duplicates().tolist(), list(CANCEL_GROUPS))
        combined = grouped.groupby(["lower_hours", "upper_hours"]).prescriptions.sum()
        np.testing.assert_array_equal(combined.to_numpy(), overall.prescriptions.to_numpy())
        for group in CANCEL_GROUPS:
            frame = grouped[grouped.cancel_group.eq(group)]
            np.testing.assert_array_equal(frame.lower_hours.to_numpy(), overall.lower_hours.to_numpy())
            count = int(selected.cancel_group.eq(group).sum())
            self.assertEqual(frame.prescriptions.sum(), count)
            self.assertAlmostEqual(frame.percent.sum(), 100 if count else 0)

    def test_empty_result_removes_stale_chart_and_writes_explanation(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            (path / "distribution.png").write_bytes(b"stale")
            (path / "distribution-by-cancel-reason.png").write_bytes(b"stale")
            counts = write_outputs(query_fixture().iloc[:0], "2026-07-30", "2026-10-21", path, path)
            self.assertEqual(counts["eligible_prescriptions"], 0)
            self.assertFalse((path / "distribution.png").exists())
            self.assertFalse((path / "distribution-by-cancel-reason.png").exists())
            self.assertIn("No eligible observations", (path / "distribution.md").read_text())

    def test_invalid_dates_and_sql_only(self):
        for start, end in [("bad", "2026-10-21"), ("2026-10-21", "2026-07-30"), ("2026-07-30", "2026-07-30")]:
            with self.assertRaises(ValueError):
                render_sql(start, end)
        result = CliRunner().invoke(main, ["--start-date", "2026-07-30", "--end-date", "2026-10-21", "--print-sql"])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("'2026-10-21'::TIMESTAMP_NTZ", result.output)
        self.assertNotIn("{{", result.output)


if __name__ == "__main__":
    unittest.main()

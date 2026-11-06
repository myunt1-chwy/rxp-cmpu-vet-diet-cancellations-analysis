"""Execute the delivered SQL against edge-case warehouse fixtures."""

import re
from decimal import Decimal

import duckdb
import pandas as pd
import pytest

from shared.python import non_autoship_returns as a


def fixture():
    original = {
        "order_id": 1,
        "order_line_id": 11,
        "customer_id": 7,
        "pet_id": 8,
        "product_part_number": "P",
        "rx_id": "rx",
        "is_vet_diet_flag": True,
        "order_placed_dttm": pd.Timestamp("2026-05-01"),
        "order_cancel_dttm": pd.Timestamp("2026-06-01"),
        "order_cancel_reason": "aged order",
        "order_order_line_status": "X",
        "shipment_key": None,
        "order_line_shipped_dttm": None,
        "order_line_net_sales": Decimal(5),
        "order_auto_reorder_flag": True,
        "order_auto_reorder_subscription_first_shipped_flag": False,
        "order_line_auto_reorder_flag": True,
    }
    later = dict(
        original,
        order_id=2,
        order_line_id=21,
        order_placed_dttm=pd.Timestamp("2026-06-08"),
        order_cancel_dttm=None,
        order_cancel_reason=None,
        order_order_line_status="D",
        shipment_key="s1",
        order_line_auto_reorder_flag=False,
        order_line_shipped_dttm=pd.Timestamp("2026-06-09"),
        order_line_net_sales=Decimal(10),
    )
    return [original, later]


def execute(rows, transactions=None):
    sql = a.render_sql()
    sql = sql.replace("edldb.bt_hca_hcdm.rxp_prescriptions", "prescriptions")
    sql = sql.replace(
        "edldb.bt_hca_hcdm.order_line_cost_measures_rxp", "lines"
    )
    sql = sql.replace("edldb.ecom.orders", "orders")
    sql = sql.replace(
        "edldb.bt_shared_dw.fct_subscription_order_line_transaction",
        "transactions",
    )
    if transactions is None:
        transactions = pd.DataFrame(rows)[
            [
                "order_line_id",
                "order_line_auto_reorder_flag",
                "order_line_shipped_dttm",
            ]
        ].copy()
        for key in [
            "subscription_group_key",
            "subscription_key",
            "order_key",
            "product_key",
        ]:
            transactions[key] = 1
        for flag in [
            "one_time_shipped_flag",
            "auto_added_flag",
            "order_line_pbfresh_subscription_flag",
        ]:
            transactions[flag] = False
    transactions = transactions.copy()
    transactions["order_line_shipped_dttm"] = pd.to_datetime(
        transactions["order_line_shipped_dttm"], utc=True
    )
    sql = sql.replace("TIMESTAMP_NTZ", "TIMESTAMP").replace(
        "NUMBER(38, 5)", "DECIMAL(38, 5)"
    )
    sql = re.sub(r"OBJECT_CONSTRUCT_KEEP_NULL\((\w+)\.\*\)", r"\1", sql)
    sql = re.sub(
        r"DATEADD\(DAY, ([\w.]+), ([\w.]+)\)",
        r"(\2 + \1 * INTERVAL 1 DAY)",
        sql,
    )
    sql = sql.replace("column1", "col0")
    sql = re.sub(
        r"FROM\s+VALUES\s+(.*?)\n\)",
        r"FROM (VALUES \1)\n)",
        sql,
        flags=re.DOTALL,
    )
    lines = pd.DataFrame(rows)
    for column in [
        "order_cancel_dttm",
        "order_placed_dttm",
        "order_line_shipped_dttm",
    ]:
        lines[column] = pd.to_datetime(lines[column])
    prescriptions = pd.DataFrame(
        [
            {
                "rx_id": "rx",
                "customer_id": 7,
                "is_vet_diet_flag": True,
                "approval_channel": "CUSTOMER_UPLOAD",
                "prescription_source": "CMPU",
            }
        ]
    )
    orders = lines[
        ["order_id", "customer_id", "order_placed_dttm"]
    ].drop_duplicates()
    orders["order_first_order_placed_flag"] = orders.order_id.eq(1)
    with duckdb.connect() as con:
        con.register("lines", lines)
        con.register("prescriptions", prescriptions)
        con.register("orders", orders)
        con.execute("CREATE MACRO IFF(x,a,b) AS CASE WHEN x THEN a ELSE b END")
        con.execute(
            "CREATE MACRO CONVERT_TIMEZONE(tz, ts) AS timezone(tz, ts)"
        )
        con.register("transactions", transactions)
        return a.records(con.execute(sql).df())


def summary(data, days=70):
    return next(
        r
        for r in data["summary"]
        if r["cohort"] == "all-aged" and r["days"] == days
    )


def test_flags_mixed_order_duplicate_shipments_signed_sales_repeated_anchors():
    original, later = fixture()
    rows = [
        original,
        dict(original, order_id=3, order_line_id=31),
        later,
        later,
        dict(later, shipment_key="s2", order_line_net_sales=Decimal(-12)),
        dict(later, order_line_id=22, order_line_auto_reorder_flag=True),
        dict(later, order_line_id=23, order_line_auto_reorder_flag=None),
    ]
    data = execute(rows)
    a.validate(data)
    r = summary(data, 7)
    assert (r["denominator"], r["customers"], r["orders"], r["lines"]) == (
        1,
        1,
        1,
        1,
    )
    assert Decimal(r["known_net_sales"]) == -2
    assert r["null_flag_lines"] == 1 and r["unfiltered_lines"] == 3


@pytest.mark.parametrize("flag", [True, False, None])
def test_flags(flag):
    rows = fixture()
    rows[1]["order_line_auto_reorder_flag"] = flag
    data = execute(rows)
    a.validate(data)
    assert summary(data)["customers"] == int(flag is False)


@pytest.mark.parametrize("flag", [True, None])
def test_conflicting_flags_across_shipments_fail(flag):
    rows = fixture()
    rows.append(
        dict(rows[1], shipment_key="other", order_line_auto_reorder_flag=flag)
    )
    with pytest.raises(ValueError, match="Conflicting"):
        a.validate(execute(rows))


@pytest.mark.parametrize(
    "offset,expected7,expected70",
    [(0, 0, 0), (7, 1, 1), (8, 0, 1), (70, 0, 1), (71, 0, 0)],
)
def test_boundaries(offset, expected7, expected70):
    rows = fixture()
    rows[1]["order_placed_dttm"] = pd.Timestamp("2026-06-01") + pd.Timedelta(
        days=offset
    )
    data = execute(rows)
    a.validate(data)
    assert summary(data, 7)["customers"] == expected7
    assert summary(data)["customers"] == expected70


def test_missing_keys_empty_cohort_and_incomplete_sales():
    rows = fixture()
    rows[0]["pet_id"] = None
    data = execute(rows)
    a.validate(data)
    assert (
        summary(data)["denominator"] == 1 and summary(data)["customers"] == 0
    )
    rows = fixture()
    rows[0]["order_cancel_reason"] = "other"
    data = execute(rows)
    a.validate(data)
    assert (
        summary(data)["denominator"] == 0
        and summary(data)["percentage"] is None
    )
    rows = fixture()
    rows[1]["order_line_net_sales"] = None
    data = execute(rows)
    a.validate(data)
    assert summary(data)["missing_sales_records"] == 1


def test_failed_refresh_preserves_cache_and_pdf(tmp_path, monkeypatch):
    monkeypatch.setattr(a, "ROOT", tmp_path)
    monkeypatch.setattr(a, "dependencies", lambda: ({}, {}))
    monkeypatch.setattr(a, "render_sql", lambda: "query")
    current = tmp_path / "targets" / a.OWNER / "data/current"
    current.mkdir(parents=True)
    marker = current / "source.parquet"
    marker.write_bytes(b"usable")
    pdf = tmp_path / "outputs/reports/pdf/report.pdf"
    pdf.parent.mkdir(parents=True)
    pdf.write_bytes(b"published")

    def fail(*args):
        raise ValueError("extraction failed")

    monkeypatch.setattr(a.base, "extract", fail)
    with pytest.raises(ValueError, match="extraction failed"):
        a.run(True)
    assert (
        marker.read_bytes() == b"usable" and pdf.read_bytes() == b"published"
    )


def test_missing_cache_actionable(tmp_path, monkeypatch):
    monkeypatch.setattr(a, "ROOT", tmp_path)
    monkeypatch.setattr(a, "dependencies", lambda: ({}, {}))
    monkeypatch.setattr(a, "render_sql", lambda: "query")
    with pytest.raises(ValueError, match="REFRESH=1"):
        a.run()


def test_cached_reproduction_no_warehouse_and_stale_rejection(
    tmp_path, monkeypatch
):
    import hashlib
    import json

    data = execute(fixture())
    refs = {
        cohort: pd.DataFrame(
            [r for r in data["anchor"] if r["cohort"] == cohort]
        )
        for cohort in a.TARGETS
    }
    raw = pd.DataFrame(
        [
            {"record_type": kind, "payload": json.dumps(row)}
            for kind, rows in data.items()
            for row in rows
        ]
    )
    monkeypatch.setattr(a, "ROOT", tmp_path)
    monkeypatch.setattr(a, "dependencies", lambda: (refs, {}))
    monkeypatch.setattr(a, "render_sql", lambda: "query")

    def forbidden(*args):
        pytest.fail("Cached reproduction accessed warehouse")

    monkeypatch.setattr(a.base, "extract", forbidden)
    current = tmp_path / "targets" / a.OWNER / "data/current"
    current.mkdir(parents=True)
    raw.to_parquet(current / "source.parquet")
    manifest = {
        "identity": {
            "parameters": a.PARAMS,
            "query_sha256": hashlib.sha256(b"query").hexdigest(),
            "dependencies": {},
            "version": 1,
        },
        "source_sha256": a.base.digest(current / "source.parquet"),
    }
    (current / "manifest.json").write_text(json.dumps(manifest))
    a.run()
    for target in a.TARGETS.values():
        assert (
            tmp_path / "targets" / target / "outputs/tables/table.org"
        ).exists()
    manifest["identity"]["parameters"] = {}
    (current / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="REFRESH=1"):
        a.run()


def test_first_cohorts_and_successful_order_scope():
    original, later = fixture()
    earlier = dict(
        later,
        order_id=0,
        order_line_id=1,
        order_placed_dttm=pd.Timestamp("2026-04-01"),
    )
    data = execute([original, later, earlier])
    a.validate(data)
    assert summary(data)["denominator"] == 1
    assert all(
        r["denominator"] == 0
        for r in data["summary"]
        if r["cohort"] != "all-aged"
    )
    cancelled_other_product = dict(
        later,
        order_line_id=22,
        product_part_number="OTHER",
        order_order_line_status="X",
    )
    data = execute([original, later, cancelled_other_product])
    a.validate(data)
    assert summary(data)["customers"] == 0


def test_incomplete_followup_keeps_denominator(monkeypatch):
    monkeypatch.setitem(a.PARAMS, "as_of_date", "2026-06-09")
    data = execute(fixture())
    assert summary(data)["denominator"] == 1
    assert summary(data)["customers"] == 0
    assert summary(data, 7)["customers"] == 1
    # This case deliberately has incomplete follow-up, so nested windows
    # are not assumed by the production fixed study dates.


@pytest.mark.parametrize(
    "field,value",
    [
        ("pet_id", None),
        ("product_part_number", ""),
        ("product_part_number", None),
    ],
)
def test_unusable_matching_keys_stay_in_denominator(field, value):
    rows = fixture()
    rows[0][field] = value
    data = execute(rows)
    a.validate(data)
    assert summary(data)["denominator"] == 1
    assert summary(data)["customers"] == 0


def test_zero_sales_and_unknown_other_line_status():
    rows = fixture()
    rows[1]["order_line_net_sales"] = Decimal(0)
    data = execute(rows)
    a.validate(data)
    assert summary(data)["customers"] == 1
    assert Decimal(summary(data)["known_net_sales"]) == 0
    rows.append(
        dict(
            rows[1],
            order_line_id=22,
            product_part_number="OTHER",
            order_order_line_status=None,
        )
    )
    data = execute(rows)
    a.validate(data)
    assert summary(data)["customers"] == 0


@pytest.mark.parametrize("first_shipped", [True, False, None])
@pytest.mark.parametrize("auto_reorder", [True, False, None])
def test_initial_shipment_requires_autoship_line(first_shipped, auto_reorder):
    rows = fixture()
    rows[1]["order_line_auto_reorder_flag"] = auto_reorder
    txn = transaction_fixture(auto_reorder)
    if first_shipped is False:
        earlier = txn.copy()
        earlier["order_line_id"] = 999
        earlier["order_line_shipped_dttm"] = "2025-01-01T00:00:00Z"
        txn = pd.concat([txn, earlier])
    elif first_shipped is None:
        txn["order_line_shipped_dttm"] = None
    data = execute(rows, txn)
    a.validate(data)
    result = next(
        r for r in data["first_shipped_summary"] if r["cohort"] == "all-aged"
    )
    expected = first_shipped is True and auto_reorder is True
    assert result["customers"] == int(expected)
    assert result["lines"] == int(expected)


@pytest.mark.parametrize("other_flag", [False, None])
def test_legacy_first_shipped_flag_is_ignored(other_flag):
    rows = fixture()
    rows[1]["order_auto_reorder_subscription_first_shipped_flag"] = True
    rows.append(
        dict(
            rows[1],
            shipment_key="second",
            order_auto_reorder_subscription_first_shipped_flag=other_flag,
        )
    )
    a.validate(execute(rows))


def test_first_shipped_deduplicates_lines_and_keeps_signed_sales():
    original, later = fixture()
    # Original flags never qualify a later line; order auto flag is diagnostic.
    original["order_auto_reorder_subscription_first_shipped_flag"] = True
    later["order_auto_reorder_subscription_first_shipped_flag"] = True
    included_auto = dict(
        later,
        order_line_id=22,
        order_line_auto_reorder_flag=True,
        order_line_net_sales=Decimal(-100),
    )
    excluded_auto = dict(
        included_auto,
        order_line_id=23,
        order_line_shipped_dttm=pd.Timestamp("2026-06-10"),
    )
    rows = [
        original,
        dict(original, order_id=3, order_line_id=31),
        later,
        later,
        included_auto,
        excluded_auto,
    ]
    data = execute(rows)
    a.validate(data)
    result = next(
        r for r in data["first_shipped_summary"] if r["cohort"] == "all-aged"
    )
    assert (result["customers"], result["orders"], result["lines"]) == (
        1,
        1,
        1,
    )
    assert Decimal(result["known_net_sales"]) == -100
    assert summary(data)["known_net_sales"] == "10.00000"


@pytest.mark.parametrize("boundary", a.HORIZONS)
def test_autoship_initiating_cumulative_window_boundaries(boundary):
    original, later = fixture()
    later["order_auto_reorder_subscription_first_shipped_flag"] = True
    later["order_line_auto_reorder_flag"] = True
    later["order_placed_dttm"] = pd.Timestamp("2026-06-01") + pd.Timedelta(
        days=boundary
    )
    after = dict(
        later,
        order_id=4,
        order_line_id=41,
        order_placed_dttm=later["order_placed_dttm"] + pd.Timedelta(seconds=1),
    )
    data = execute([original, later, after])
    a.validate(data)
    for row in data["first_shipped_summary"]:
        days = row["days"]
        assert row["customers"] == int(days >= boundary)
        assert row["orders"] == int(days >= boundary) + int(days > boundary)
        assert row["denominator"] == 1
    assert summary(data)["customers"] == 0


@pytest.mark.parametrize("line_flag", [True, False, None])
def test_shipment_required_for_all_reorder_panels(line_flag):
    original, later = fixture()
    later["order_auto_reorder_subscription_first_shipped_flag"] = True
    later["order_line_auto_reorder_flag"] = line_flag
    later["order_line_shipped_dttm"] = None
    # Another shipped line on the order cannot qualify this matching line.
    other = dict(
        later,
        order_line_id=22,
        product_part_number="OTHER",
        order_line_shipped_dttm=pd.Timestamp("2026-06-09"),
    )
    data = execute([original, later, other])
    a.validate(data)
    for kind in ["summary", "shipped_summary"]:
        assert all(r["customers"] == 0 for r in data[kind])
        assert all(r["denominator"] == 1 for r in data[kind])
    assert all(r["customers"] == 0 for r in data["first_shipped_summary"])


def test_shipped_line_uses_minimum_timestamp_and_placement_window():
    original, later = fixture()
    # Placement on day 7 qualifies even though shipment is after day 70.
    later["order_line_shipped_dttm"] = pd.Timestamp("2026-09-01")
    second = dict(
        later,
        shipment_key="s2",
        order_line_shipped_dttm=None,
        order_line_net_sales=Decimal(-2),
    )
    data = execute([original, later, later, second])
    a.validate(data)
    for kind in ["summary", "shipped_summary"]:
        for row in data[kind]:
            assert row["customers"] == row["orders"] == row["lines"] == 1
            assert Decimal(row["known_net_sales"]) == 8


def transaction_fixture(flag=False):
    return pd.DataFrame(
        [
            {
                "order_line_id": 21,
                "order_line_shipped_dttm": "2026-06-09T00:00:00Z",
                "subscription_group_key": 1,
                "subscription_key": 2,
                "order_key": 3,
                "product_key": 4,
                "one_time_shipped_flag": False,
                "auto_added_flag": False,
                "order_line_auto_reorder_flag": flag,
                "order_line_pbfresh_subscription_flag": False,
            }
        ]
    )


def test_transaction_flag_overrides_old_source_without_multiplying_sales():
    rows = fixture()
    rows[1]["order_line_auto_reorder_flag"] = True
    txn = transaction_fixture(False)
    data = execute(rows, pd.concat([txn, txn]))
    a.validate(data)
    assert summary(data)["customers"] == 1
    assert summary(data)["lines"] == 1
    assert Decimal(summary(data)["known_net_sales"]) == 10
    assert data["line"][0]["transaction_records"] == 2


def test_missing_transaction_is_non_autoship():
    data = execute(fixture(), transaction_fixture().iloc[:0])
    a.validate(data)
    assert summary(data)["customers"] == 1
    assert summary(data)["null_flag_lines"] == 0
    assert data["anchor"][0]["original_order_line_auto_reorder_flag"] is False


def test_conflicting_transaction_keys_are_rejected():
    txn = transaction_fixture()
    conflict = txn.copy()
    conflict["product_key"] = 999
    with pytest.raises(ValueError, match="Conflicting"):
        a.validate(execute(fixture(), pd.concat([txn, conflict])))


@pytest.mark.parametrize("order_flag", [True, False, None])
def test_order_autoreorder_flag_is_ignored_even_when_conflicting(order_flag):
    rows = fixture()
    rows.append(dict(rows[1], order_auto_reorder_flag=order_flag))
    data = execute(rows)
    a.validate(data)
    assert summary(data)["customers"] == 1
    assert summary(data)["lines"] == 1


def test_present_null_transaction_flag_stays_unknown():
    data = execute(fixture(), transaction_fixture(None))
    a.validate(data)
    assert summary(data)["customers"] == 0
    assert summary(data)["null_flag_lines"] == 1


@pytest.mark.parametrize("changed_key", ["subscription_key", "product_key"])
def test_initial_shipment_partition_uses_both_keys(changed_key):
    txn = transaction_fixture(True)
    earlier = txn.copy()
    earlier["order_line_id"] = 999
    earlier["order_line_shipped_dttm"] = "2025-01-01T00:00:00Z"
    earlier[changed_key] = 999
    data = execute(fixture(), pd.concat([txn, earlier]))
    a.validate(data)
    assert data["first_shipped_summary"][0]["customers"] == 1


@pytest.mark.parametrize("key", ["subscription_key", "product_key"])
def test_initial_shipment_requires_pair_keys(key):
    txn = transaction_fixture(True)
    txn[key] = None
    data = execute(fixture(), txn)
    a.validate(data)
    assert all(r["customers"] == 0 for r in data["first_shipped_summary"])


def test_full_history_includes_earlier_non_autoship_line():
    txn = transaction_fixture(True)
    earlier = transaction_fixture(False)
    earlier["order_line_id"] = 999
    earlier["order_line_shipped_dttm"] = "2025-01-01T00:00:00Z"
    data = execute(fixture(), pd.concat([txn, earlier, earlier]))
    a.validate(data)
    assert all(r["customers"] == 0 for r in data["first_shipped_summary"])
    assert len(data["subscription_history"]) == 2


def test_eastern_daylight_saving_ties_use_instants():
    txn = transaction_fixture(True)
    txn["order_line_shipped_dttm"] = "2026-11-01T01:30:00-04:00"
    tie = txn.copy()
    tie["order_line_id"] = 999
    tie["order_line_shipped_dttm"] = "2026-11-01T05:30:00Z"
    later = txn.copy()
    later["order_line_id"] = 998
    later["order_line_shipped_dttm"] = "2026-11-01T01:00:00-05:00"
    data = execute(fixture(), pd.concat([txn, tie, later]))
    a.validate(data)
    assert data["first_shipped_summary"][0]["customers"] == 1
    assert pd.Timestamp(data["line"][0]["product_first_shipped_utc"]) == (
        pd.Timestamp("2026-11-01T05:30:00")
    )

"""
Original-order handled WISMO, strict nanosecond bounds and frozen
intervals.
"""

import json
from pathlib import Path
from unittest.mock import patch

import duckdb
import pandas as pd
import pytest
from click.testing import CliRunner
from sql_fixtures import (
    contact_fixture_sql,
    fixture_sql,
    isolate_cte,
    sql_contains,
)

from shared.python import create_aged_order_reorder_wismo as analysis


def fixtures():
    cancel = pd.Timestamp("2026-09-01", tz="UTC")
    rows = []
    for days in [7, 14, 21]:
        for customer in [1, 2]:
            rows.append(
                {
                    "followup_days": days,
                    "original_customer_id": customer,
                    "original_order_id": 99 + customer,
                    "original_line_id": customer,
                    "reorder_order_id": 199 + customer,
                    "reorder_line_id": customer,
                    "order_cancel_time": cancel,
                    "reorder_placed_at_utc": cancel + pd.Timedelta(days=1),
                    "prescription_comparison": "Different prescription"
                    if customer == 1
                    else "Same prescription",
                }
            )
    selected, intervals = analysis.requests_for(pd.DataFrame(rows))
    events = []
    for name, order, ns, wismo, handled, session, channel in [
        ("BEFORE", 100, -1, True, True, "s0", "Voice"),
        ("ATCANCEL", 100, 0, True, True, "s0", "Voice"),
        ("GOOD1", 100, 1, True, True, "s1", "Voice"),
        ("GOOD2", 100, 2, True, True, "s1", "Chat"),
        ("GOOD3", 100, 86_400_000_000_000 - 1, True, True, "s2", None),
        ("ATREORDER", 100, 86_400_000_000_000, True, True, "s3", "Voice"),
        ("AFTER", 100, 86_400_000_000_001, True, True, "s3", "Voice"),
        ("UNHANDLED", 100, 3, True, False, "s4", "Voice"),
        ("NONWISMO", 100, 3, False, True, "s5", "Voice"),
        ("NEWORDER", 200, 3, True, True, "s6", "Voice"),
        ("UNDATED", 100, None, True, True, "s7", "Email"),
    ]:
        events.append(
            {
                "order_id": order,
                "leg_id": name,
                "session_id": session,
                "session_channel": channel,
                "session_start_dttm": cancel.tz_localize(None)
                + pd.Timedelta(nanoseconds=ns)
                if ns is not None
                else pd.NaT,
                "category_wismo_flag": wismo,
                "handled_flag": handled,
            }
        )
    contacts = pd.DataFrame(events)
    contacts["session_start_dttm"] = contacts.session_start_dttm.astype(
        "datetime64[ns]"
    )
    return selected, intervals, contacts


def execute_sql(
    intervals, contacts, all_contacts=False, all_order_history=False
):
    sql = fixture_sql(
        analysis.render_sql("UTC", all_contacts, all_order_history)
    )
    sql = isolate_cte(sql, "requested", "contact_interval_fixture.sql")
    sql = (
        contact_fixture_sql(sql)
        .replace("EDLDB.BT_CUSTOMER_CARE.FCT_CONTACTS_BRD", "contacts_source")
        .replace("CURRENT_WAREHOUSE()", "'test'")
    )
    typed_intervals = intervals.copy()
    for field in ["order_cancel_time", "reorder_placed_at_utc"]:
        typed_intervals[field] = pd.to_datetime(
            typed_intervals[field], utc=True
        ).dt.tz_localize(None)
    with duckdb.connect() as con:
        con.register("interval_fixture", typed_intervals)
        con.register("contacts_source", contacts)
        con.execute(
            (
                Path(__file__).parent / "sql" / "contact_fixture_functions.sql"
            ).read_text()
        )
        return con.execute(sql).df()


def test_actual_sql_strict_bounds_original_order_flags_and_zero_matches():
    selected, intervals, contacts = fixtures()
    assert (
        len(intervals) == 2
    )  # horizon repeats do not multiply the contact lookup
    raw = execute_sql(intervals, contacts)
    outputs = analysis.summarize(selected, intervals, raw, "UTC")
    assert set(outputs["contact-interval-associations"].leg_id) == {
        "GOOD1",
        "GOOD2",
        "GOOD3",
    }
    yes = outputs["selected-customers"].loc[
        outputs["selected-customers"].original_customer_id.eq(1)
    ]
    no = outputs["selected-customers"].loc[
        outputs["selected-customers"].original_customer_id.eq(2)
    ]
    assert (
        yes.wismo_contact_count.eq(3).all()
        and yes.distinct_wismo_sessions.eq(2).all()
    )
    assert yes.wismo_channels.eq("Chat, Voice").all()
    assert yes.missing_session_time_rows.eq(1).all()
    assert (
        no.wismo_contact_count.eq(0).all() and no.first_wismo_dttm.isna().all()
    )
    summary = outputs["summary"].loc[
        outputs["summary"].prescription_comparison.eq(
            "All reordered customers"
        )
    ]
    assert (
        summary.customers_with_wismo.eq(1).all()
        and summary.reordered_customers.eq(2).all()
    )
    assert summary.matching_contact_legs.eq(3).all()


def test_leg_count_retains_multiple_legs_and_duplicate_source_rows():
    selected, intervals, contacts = fixtures()
    duplicate = pd.concat(
        [contacts, contacts.loc[contacts.leg_id.eq("GOOD1")]]
    )
    result = analysis.summarize(
        selected, intervals, execute_sql(intervals, duplicate), "UTC"
    )
    assert (
        result["selected-customers"]
        .loc[lambda d: d.original_customer_id.eq(1), "wismo_contact_count"]
        .eq(4)
        .all()
    )
    assert (
        result["audit"]
        .loc[
            result["audit"].measure.str.startswith("Repeated non-null"),
            "count",
        ]
        .iloc[0]
        == 1
    )


def test_same_order_different_selected_reorder_windows_are_not_collapsed():
    selected, _, contacts = fixtures()
    selected = selected.drop(columns="request_id")
    mask = selected.followup_days.eq(14) & selected.original_customer_id.eq(1)
    selected.loc[mask, "reorder_placed_at_utc"] = pd.Timestamp(
        "2026-09-01 12:00", tz="UTC"
    )
    selected, intervals = analysis.requests_for(selected)
    assert len(intervals) == 3
    result = analysis.summarize(
        selected, intervals, execute_sql(intervals, contacts), "UTC"
    )["selected-customers"]
    assert result.loc[result.original_customer_id.eq(1)].set_index(
        "followup_days"
    ).wismo_contact_count.to_dict() == {7: 3, 14: 2, 21: 3}


def test_timezone_must_be_explicit_and_conversion_is_verified():
    selected, intervals, contacts = fixtures()
    with pytest.raises(ValueError, match="explicitly"):
        analysis.render_sql(None)
    assert sql_contains(
        analysis.render_sql("America/New_York"),
        "CONVERT_TIMEZONE('America/New_York', 'UTC', c.SESSION_START_DTTM)",
    )
    raw = execute_sql(intervals, contacts)
    for index, row in raw.iterrows():
        records = json.loads(row.matched_contacts_json)
        for record in records:
            utc = pd.Timestamp(record["contact_at_utc"], tz="UTC")
            record["session_start_dttm_raw"] = (
                utc.tz_convert("America/New_York")
                .tz_localize(None)
                .isoformat(sep=" ", timespec="nanoseconds")
            )
        raw.loc[index, "matched_contacts_json"] = json.dumps(records)
    result = analysis.summarize(selected, intervals, raw, "America/New_York")
    assert len(result["contact-interval-associations"]) == 3
    with pytest.raises(ValueError, match="timezone"):
        analysis.summarize(selected, intervals, raw, "UTC")


@pytest.mark.parametrize(
    "case",
    [
        "missing-key",
        "duplicate-key",
        "wrong-order",
        "count",
        "first-time",
        "channel",
        "session-count",
        "at-cancel",
        "at-reorder",
        "wrong-contact-order",
        "flag",
        "negative-audit",
    ],
)
def test_mismatched_aggregates_and_contacts_rejected(case):
    selected, intervals, contacts = fixtures()
    raw = execute_sql(intervals, contacts)
    if case == "missing-key":
        raw = raw.iloc[1:]
    if case == "duplicate-key":
        raw = pd.concat([raw, raw.iloc[[0]]])
    if case == "wrong-order":
        raw.loc[0, "original_order_id"] = 999
    if case == "count":
        raw.loc[0, "wismo_contact_count"] = 99
    if case == "first-time":
        raw.loc[0, "first_wismo_dttm"] = "2026-09-01"
    if case == "channel":
        raw.loc[0, "wismo_channels"] = "Email"
    if case == "session-count":
        raw.loc[0, "distinct_wismo_sessions"] = 3
    if case == "negative-audit":
        raw.loc[0, "missing_session_time_rows"] = -1
    if case in ["at-cancel", "at-reorder", "wrong-contact-order", "flag"]:
        records = json.loads(raw.loc[0, "matched_contacts_json"])
        if case == "at-cancel":
            records[0]["contact_at_utc"] = "2026-09-01"
        if case == "at-reorder":
            records[0]["contact_at_utc"] = "2026-09-02"
        if case == "wrong-contact-order":
            records[0]["order_id"] = 200
        if case == "flag":
            records[0]["handled_flag"] = False
        raw.loc[0, "matched_contacts_json"] = json.dumps(records)
    with pytest.raises(ValueError):
        analysis.summarize(selected, intervals, raw, "UTC")


def test_fresh_cached_sql_only_and_fingerprint_modes(tmp_path):
    selected, intervals, contacts = fixtures()
    raw = execute_sql(intervals, contacts)
    frozen = selected.drop(columns="request_id")
    period = (
        "2026-08-15_2026-10-15_customer_upload_same-pet_reorders-7d-"
        "14d-21d_as-of-2026-10-27"
    )

    def extract(args, **kwargs):
        raw.assign(extraction_warehouse="test").to_parquet(
            tmp_path / args[args.index("--output-parquet") + 1], index=False
        )

    with (
        patch.object(analysis, "ROOT", tmp_path),
        patch.object(
            analysis.sankeys.windows,
            "load_source",
            return_value=(
                pd.DataFrame(),
                {"parquet_sha256": "baseline"},
                period,
            ),
        ),
        patch.object(
            analysis.sankeys.windows,
            "summarize",
            return_value={"associations": pd.DataFrame()},
        ),
        patch.object(
            analysis.sankeys, "select_customers", return_value=pd.DataFrame()
        ),
        patch.object(
            analysis.sankeys,
            "load_source",
            return_value=(pd.DataFrame(), {"parquet_sha256": "rx"}, None),
        ),
        patch.object(
            analysis.sankeys, "summarize", return_value=(frozen, None)
        ),
        patch.object(analysis.subprocess, "run", side_effect=extract) as run,
    ):
        runner = CliRunner()
        missing = runner.invoke(analysis.main, [])
        assert (
            missing.exit_code != 0 and "--contact-timezone" in missing.output
        )
        result = runner.invoke(
            analysis.main, ["--contact-timezone", "UTC", "--print-sql"]
        )
        assert result.exit_code == 0, result.output
        run.assert_not_called()
        assert not list(tmp_path.iterdir())
        result = runner.invoke(analysis.main, ["--contact-timezone", "UTC"])
        assert result.exit_code == 0, result.output
        run.assert_called_once()
        run.reset_mock()
        result = runner.invoke(
            analysis.main, ["--contact-timezone", "UTC", "--cached"]
        )
        assert result.exit_code == 0, result.output
        run.assert_not_called()
        manifest = next((tmp_path / "data").rglob("source.json"))
        saved = json.loads(manifest.read_text())
        for field in [
            "dependencies",
            "sql_sha256",
            "parquet_sha256",
            "contact_timezone",
        ]:
            manifest.write_text(json.dumps({**saved, field: "tampered"}))
            result = runner.invoke(
                analysis.main, ["--contact-timezone", "UTC", "--cached"]
            )
            assert (
                result.exit_code != 0
                and "fingerprint differs" in result.output
            )
        exports = json.loads(
            next((tmp_path / "data").rglob("exports.json")).read_text()
        )
        for file, sha in exports["files"].items():
            assert analysis.digest(tmp_path / file) == sha


def test_snowflake_decimal_interval_keys_are_validated_before_normalizing():
    from decimal import Decimal

    selected, intervals, contacts = fixtures()
    raw = execute_sql(intervals, contacts)
    raw["request_id"] = raw.request_id.map(lambda x: Decimal(int(x)))
    outputs = analysis.summarize(selected, intervals, raw, "UTC")
    assert len(outputs["selected-customers"]) == 6
    raw.loc[0, "request_id"] = Decimal("1.5")
    with pytest.raises(ValueError, match="invalid WISMO interval key"):
        analysis.summarize(selected, intervals, raw, "UTC")


def test_all_categories_keeps_false_null_flags_but_needs_handled_strict_time():
    selected, intervals, contacts = fixtures()
    contacts["category_wismo_flag"] = contacts.category_wismo_flag.astype(
        "boolean"
    )
    extra = contacts.loc[contacts.leg_id.eq("NONWISMO")].assign(
        leg_id="NULLCAT", session_id="s8", category_wismo_flag=pd.NA
    )
    contacts = pd.concat([contacts, extra], ignore_index=True)
    sql = analysis.render_sql("UTC", True)
    assert sql_contains(sql, "WHERE c.HANDLED_FLAG=TRUE") and not sql_contains(
        sql, "CATEGORY_WISMO_FLAG=TRUE"
    )
    raw = execute_sql(intervals, contacts, True)
    result = analysis.summarize(selected, intervals, raw, "UTC", True)
    assert set(result["contact-interval-associations"].leg_id) == {
        "GOOD1",
        "GOOD2",
        "GOOD3",
        "NONWISMO",
        "NULLCAT",
    }
    yes = result["selected-customers"].loc[
        lambda d: d.original_customer_id.eq(1)
    ]
    assert (
        yes.wismo_contact_count.eq(5).all()
        and yes.distinct_wismo_sessions.eq(4).all()
    )
    with pytest.raises(ValueError, match="flags disagree"):
        analysis.summarize(selected, intervals, raw, "UTC")
    exported = analysis.contact_columns(result["selected-customers"])
    assert (
        "contact_count" in exported
        and "has_handled_contact" in exported
        and "wismo_contact_count" not in exported
    )
    assert "category_wismo_flag" in analysis.contact_columns(
        result["contact-interval-associations"]
    )


def test_all_category_cache_is_separate_and_rejects_wrong_scope(tmp_path):
    _selected, intervals, contacts = fixtures()
    raw = execute_sql(intervals, contacts, True)
    period = (
        "2026-08-15_2026-10-15_customer_upload_same-pet_reorders-7d-"
        "14d-21d_as-of-2026-10-27"
    )
    deps = {
        "baseline": "b",
        "prescription_channels": "rx",
        "customer_selection": "shortest",
    }

    def extract(args, **kwargs):
        raw.assign(extraction_warehouse="test").to_parquet(
            tmp_path / args[args.index("--output-parquet") + 1], index=False
        )

    with (
        patch.object(analysis, "ROOT", tmp_path),
        patch.object(analysis.subprocess, "run", side_effect=extract) as run,
    ):
        _, meta, manifest = analysis.load_source(
            intervals, period, deps, "UTC", False, True
        )
        assert (
            "_all-handled-contacts" in str(manifest)
            and meta["contact_scope"] == "all-handled"
        )
        manifest.write_text(json.dumps(meta))
        run.reset_mock()
        cached, _, _ = analysis.load_source(
            intervals, period, deps, "UTC", True, True
        )
        assert len(cached) == len(raw)
        run.assert_not_called()
        manifest.write_text(json.dumps({**meta, "contact_scope": "wismo"}))
        with pytest.raises(ValueError, match="fingerprint differs"):
            analysis.load_source(intervals, period, deps, "UTC", True, True)
        assert not (
            tmp_path / "data" / analysis.NAME / period / "UTC/source.parquet"
        ).exists()


def test_all_order_history_includes_before_after_boundaries_undated_contacts():
    selected, intervals, contacts = fixtures()
    sql = analysis.render_sql("UTC", all_order_history=True)
    assert not sql_contains(
        sql, "c.contact_at_utc > d.order_cancel_time"
    ) and not sql_contains(sql, "c.contact_at_utc < d.reorder_placed_at_utc")
    assert sql_contains(sql, "WHERE c.HANDLED_FLAG=TRUE") and not sql_contains(
        sql, "CATEGORY_WISMO_FLAG=TRUE"
    )
    raw = execute_sql(intervals, contacts, all_order_history=True)
    result = analysis.summarize(
        selected, intervals, raw, "UTC", all_order_history=True
    )
    assert set(result["contact-interval-associations"].leg_id) == {
        "BEFORE",
        "ATCANCEL",
        "GOOD1",
        "GOOD2",
        "GOOD3",
        "ATREORDER",
        "AFTER",
        "NONWISMO",
        "UNDATED",
    }
    yes = result["selected-customers"].loc[
        lambda d: d.original_customer_id.eq(1)
    ]
    assert (
        yes.wismo_contact_count.eq(9).all()
        and yes.distinct_wismo_sessions.eq(6).all()
    )
    assert (
        yes.has_wismo_contact.all()
        and yes.missing_session_time_rows.eq(1).all()
    )
    assert yes.first_wismo_dttm.lt(yes.order_cancel_time).all()
    assert yes.last_wismo_dttm.gt(yes.reorder_placed_at_utc).all()
    assert (
        not result["selected-customers"]
        .loc[lambda d: d.original_customer_id.eq(2), "has_wismo_contact"]
        .any()
    )


def test_all_undated_order_contacts_still_count_as_present():
    selected, intervals, contacts = fixtures()
    contacts["session_start_dttm"] = pd.Series(
        pd.NaT, index=contacts.index, dtype="datetime64[ns]"
    )
    raw = execute_sql(intervals, contacts, all_order_history=True)
    result = analysis.summarize(
        selected, intervals, raw, "UTC", all_order_history=True
    )
    yes = result["selected-customers"].loc[
        lambda d: d.original_customer_id.eq(1)
    ]
    assert yes.wismo_contact_count.eq(9).all() and yes.has_wismo_contact.all()
    assert (
        yes.first_wismo_dttm.isna().all() and yes.last_wismo_dttm.isna().all()
    )
    exported = analysis.contact_columns(result["summary"], True)
    assert (
        "customers_without_contact" in exported
        and "customers_without_dated_contact" not in exported
    )


def test_all_history_cache_records_and_checks_time_scope(tmp_path):
    _selected, intervals, contacts = fixtures()
    raw = execute_sql(intervals, contacts, all_order_history=True)
    period = (
        "2026-08-15_2026-10-15_customer_upload_same-pet_reorders-7d-"
        "14d-21d_as-of-2026-10-27"
    )

    def extract(args, **kwargs):
        raw.assign(extraction_warehouse="test").to_parquet(
            tmp_path / args[args.index("--output-parquet") + 1], index=False
        )

    with (
        patch.object(analysis, "ROOT", tmp_path),
        patch.object(analysis.subprocess, "run", side_effect=extract),
    ):
        _, meta, manifest = analysis.load_source(
            intervals, period, {}, "UTC", False, all_order_history=True
        )
        assert "all-handled-contacts_all-order-history" in str(manifest)
        assert (
            meta["contact_scope"] == "all-handled"
            and meta["contact_time_scope"] == "all-order-history"
        )
        manifest.write_text(json.dumps(meta))
        analysis.load_source(
            intervals, period, {}, "UTC", True, all_order_history=True
        )
        manifest.write_text(
            json.dumps(
                {
                    **meta,
                    "contact_time_scope": "strict-cancellation-to-reorder",
                }
            )
        )
        with pytest.raises(ValueError, match="fingerprint differs"):
            analysis.load_source(
                intervals, period, {}, "UTC", True, all_order_history=True
            )

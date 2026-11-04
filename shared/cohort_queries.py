"""
Render database-derived cohorts and explicitly validate retained snapshots.
"""

import hashlib
import re
import warnings
from datetime import date
from pathlib import Path

import yaml

from shared.paths import repository_root
from shared.sql_templates import render_sql


def render_cohort_query(
    template, period=None, as_of=None, contact_timezone=None
):
    financial = Path(template).name == "opportunity_auto_reorder_flags.sql"
    start, end, cutoff = (
        ("2026-05-01", "2026-08-01", "2026-10-28")
        if financial
        else ("2026-08-15", "2026-10-15", "2026-10-27")
    )
    if period is not None:
        match = re.match(r"(\d{4}-\d{2}-\d{2})_(\d{4}-\d{2}-\d{2})", period)
        if not match:
            raise ValueError(
                "The cohort period must begin with start and exclusive "
                "end dates"
            )
        start, end = match.groups()
        match = re.search(r"as-?of-(\d{4}-\d{2}-\d{2})", period)
        if match:
            cutoff = match[1]
    if as_of is not None:
        cutoff = date.fromisoformat(as_of).isoformat()
    if (
        not date.fromisoformat(start)
        < date.fromisoformat(end)
        <= date.fromisoformat(cutoff)
    ):
        raise ValueError("Require start < exclusive end <= observation cutoff")
    parameters = {"start_date": start, "end_date": end, "as_of_date": cutoff}
    if contact_timezone is not None:
        if contact_timezone not in {"UTC", "America/New_York"}:
            raise ValueError("Unsupported contact timezone")
        parameters["contact_timezone"] = contact_timezone
    return render_sql(template, **parameters).strip() + "\n"


def query_matches(metadata, sql):
    """Accept current SQL or an explicitly recorded historical query/data pair.

    Historical replay is not validation of the new database-derived query.
    Callers must still verify actual Parquet bytes and cohort dependencies.
    """
    current = hashlib.sha256(sql.encode()).hexdigest()
    recorded = metadata.get("sql_sha256")
    if recorded == current:
        return metadata.get("sql", sql) == sql
    fingerprint = metadata.get("parquet_sha256") or metadata.get(
        "source_sha256"
    )
    registry = yaml.safe_load(
        (
            repository_root() / "shared/retained-query-snapshots.yaml"
        ).read_text()
    )
    allowed = {
        (row["query_sha256"], row["parquet_sha256"])
        for row in registry["snapshots"]
    }
    if (recorded, fingerprint) not in allowed:
        return False
    if (
        "sql" in metadata
        and hashlib.sha256(metadata["sql"].encode()).hexdigest() != recorded
    ):
        return False
    warnings.warn(
        (
            "Replaying a fingerprint-verified historical snapshot. "
            "The new database-derived SQL has not been executed or "
            "numerically reconciled with this snapshot."
        ),
        stacklevel=2,
    )
    return True


def cached_expectations(metadata, expected):
    """
    Preserve strict dependency checks while allowing named historical
    snapshots.
    """
    sql = expected.get("sql")
    if sql is None:
        if expected["sql_sha256"] == metadata.get("sql_sha256"):
            return expected
        # A hash-only manifest is allowed only through the recorded pair
        # registry.
        sql = ""
    if not query_matches(metadata, sql):
        return expected
    return {
        key: metadata[key] if key in {"sql", "sql_sha256"} else value
        for key, value in expected.items()
    }

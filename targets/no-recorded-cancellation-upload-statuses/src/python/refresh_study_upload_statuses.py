"""Extract and reconcile status evidence for both upload detail tables."""

import hashlib
import json
import shutil
import sys
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))

import pandas as pd

from shared.cohort_queries import render_cohort_query
from shared.paths import artifact_path
from shared.python import (
    create_study_no_cancellation_upload_details as details,
)
from shared.python.markdown_tables import write_text

coverage = details.coverage


def validate_statuses(source, study, baseline, decisions):
    """Reject changed membership, customers, reasons, or status evidence."""
    study = study.copy()
    for column in details.MATCH[1:]:
        study[column] = study[column].map(coverage.base.identifier)
    source = source.rename(columns=str.lower).copy()
    source.rx_id = source.rx_id.astype("string").str.strip()
    for column in details.MATCH[1:] + ["line_customer_id"]:
        source[column] = source[column].map(coverage.base.identifier)
    if (
        not source.rx_id.is_unique
        or source.duplicated(details.KEYS).any()
        or source[details.MATCH + ["line_customer_id"]].isna().any().any()
        or not source.source_rows.eq(1).all()
        or not source.shipment_rows.gt(0).all()
        or not source.duplicate_shipment_rows.eq(0).all()
        or not source.customer_id.eq(source.line_customer_id).all()
    ):
        raise ValueError("Invalid status identities or shipment evidence")
    for column in [
        "customer_variants",
        "order_status_variants",
        "line_status_variants",
        "reason_variants",
    ]:
        if not source[column].eq(1).all():
            raise ValueError(f"Conflicting shipment evidence: {column}")
    check = study[details.MATCH + ["reason_key", "line_item_status"]].merge(
        source,
        on=details.MATCH,
        how="outer",
        validate="one_to_one",
        indicator=True,
        suffixes=("_population", ""),
    )
    if not check._merge.eq("both").all():
        raise ValueError("Status membership differs from coverage population")
    if (
        not coverage.reason_key(check.order_cancellation_reason)
        .eq(check.reason_key)
        .all()
    ):
        raise ValueError("Status cancellation reasons differ from population")

    def normalized(series):
        return (
            series.astype("string")
            .str.strip()
            .str.upper()
            .replace("", pd.NA)
            .fillna("[Missing]")
        )

    if (
        not normalized(check.line_item_status)
        .eq(normalized(check.line_item_status_population))
        .all()
    ):
        raise ValueError("Line statuses differ from population")
    for frame, column in [
        (baseline, "order_status"),
        (decisions, "rx_status"),
    ]:
        compare = source[["rx_id", column]].merge(
            frame[["rx_id", column]],
            on="rx_id",
            how="left",
            validate="one_to_one",
            suffixes=("", "_population"),
            indicator=True,
        )
        if (
            not compare._merge.eq("both").all()
            or not normalized(compare[column])
            .eq(normalized(compare[column + "_population"]))
            .all()
        ):
            raise ValueError(f"{column} differs from population")
    return source


def install_sources(staged):
    """Restore the previous inputs if installation of either subset fails."""
    backup = staged[0][0].parent / "backups"
    backup.mkdir()
    originals = {}
    installed = []
    try:
        for part, destination in staged:
            destination.mkdir(parents=True, exist_ok=True)
            for name in ["source.parquet", "source.sql", "source.json"]:
                target = destination / name
                if target.exists():
                    saved = backup / str(len(originals))
                    shutil.copy2(target, saved)
                    originals[target] = saved
                (part / name).replace(target)
                installed.append(target)
    except Exception:
        for target in installed:
            target.unlink(missing_ok=True)
        for target, saved in originals.items():
            shutil.copy2(saved, target)
        raise


def main():
    parent = json.loads((details.PARENT / "analysis.json").read_text())
    run_id = parent.get("refresh_run_id")
    if not run_id:
        raise ValueError("Coverage requires a coordinated population run")
    for name, expected in parent["exports"].items():
        if details.digest(details.PARENT / name) != expected:
            raise ValueError("Coverage export fingerprint differs")
    study = pd.read_parquet(details.PARENT / "study-status-lines.parquet")
    inputs = {}
    for name in ["baseline", "decisions"]:
        provenance = parent["sources"][name]
        directory = ROOT / provenance["path"]
        frame, manifest = coverage.load_source(directory)
        if manifest != {k: v for k, v in provenance.items() if k != "path"}:
            raise ValueError("Coverage population changed after analysis")
        inputs[name] = frame
    sql = render_cohort_query(details.SQL)
    details.DATA.mkdir(parents=True, exist_ok=True)
    # Keep SQL history and extraction logs outside the temporary data stage.
    query_dir = (
        ROOT
        / "targets/no-recorded-cancellation-upload-statuses"
        / "src/autogenerated/status-refresh"
    )
    query_dir.mkdir(parents=True, exist_ok=True)
    query = query_dir / "extract.sql"
    write_text(query, sql)
    with TemporaryDirectory(prefix=".refresh-", dir=details.DATA) as temporary:
        stage = Path(temporary)
        full_path = stage / "all-statuses.parquet"
        engine = coverage.base.extract(query, full_path, query_dir)
        source = validate_statuses(
            pd.read_parquet(full_path),
            study,
            inputs["baseline"],
            inputs["decisions"],
        )
        timestamps = source.extracted_at_utc.drop_duplicates()
        if len(source) and (len(timestamps) != 1 or timestamps.isna().any()):
            raise ValueError("Status query has inconsistent extraction times")
        extracted_at = (
            pd.to_datetime(timestamps.iloc[0], utc=True).isoformat()
            if len(timestamps)
            else datetime.now(UTC).isoformat()
        )
        staged = []
        for reason, destination in [
            (coverage.base.MISSING_REASON, details.DATA),
            (
                "aged order",
                artifact_path(
                    ROOT
                    / "data/study-aged-order-upload-coverage"
                    / coverage.PERIOD
                ),
            ),
        ]:
            cohort, uploads, hashes = details.frozen_inputs(reason)
            subset = source.merge(
                cohort[details.MATCH], on=details.MATCH, validate="one_to_one"
            )
            details.analyze(
                subset, cohort, uploads, reason, extracted_at_utc=extracted_at
            )
            part = stage / str(len(staged))
            part.mkdir()
            subset.to_parquet(part / "source.parquet", index=False)
            write_text(part / "source.sql", sql)
            metadata = {
                "version": 2,
                "refresh_run_id": run_id,
                "frozen_inputs": hashes,
                "sql_sha256": hashlib.sha256(sql.encode()).hexdigest(),
                "parquet_sha256": details.digest(part / "source.parquet"),
                "extracted_at_utc": extracted_at,
                "full_extract_sha256": details.digest(full_path),
                "generator_sha256": details.digest(Path(__file__)),
                "engine": engine,
                "parameters": coverage.PARAMS,
            }
            write_text(
                part / "source.json", json.dumps(metadata, indent=2) + "\n"
            )
            staged.append((part, destination))
        # Both subsets have passed before any usable input is replaced.
        install_sources(staged)
    print(f"Validated {len(source):,} coverage status rows for run {run_id}.")


if __name__ == "__main__":
    main()

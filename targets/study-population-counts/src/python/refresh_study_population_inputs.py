"""Refresh report population prescription and upload evidence together."""

import hashlib
import json
import os
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

from jinja2 import Environment, StrictUndefined

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))

import pandas as pd

from shared.python import prescription_uploads
from shared.python.create_opportunity_order_cancellation_summary import extract
from shared.python.financial_values import identifier
from shared.python.markdown_tables import write_text
from shared.python.paths import artifact_path
from shared.python.runtime import digest

START_DATE = "2026-08-15"
END_DATE = "2026-10-15"
UPLOAD_START_DATE = "2026-08-01"
UPLOAD_END_DATE = "2026-10-26"
AS_OF_DATE = "2026-10-27"
RUN_ID = os.environ.get("RXP_REFRESH_RUN_ID") or uuid4().hex
LINE_DATASET = "cmpu-first-order-line-status"
UPLOAD_DATASET = "cmpu-study-population-uploaded-documents"
DECISION_DATASET = "cmpu-study-population-prescription-decisions"


def line_source_directory():
    period = (
        prescription_uploads.period_name(
            START_DATE, END_DATE, UPLOAD_START_DATE
        )
        + f"_uploads-end-{UPLOAD_END_DATE}"
        + "_"
        + prescription_uploads.TIMING_VARIANT
        + "_block-reasons"
    )
    return artifact_path(ROOT / "data" / LINE_DATASET / period)


def render(name, **parameters):
    source = ROOT / "targets" / name
    return (
        Environment(undefined=StrictUndefined)
        .from_string(source.read_text())
        .render(**parameters)
        .strip()
        + "\n"
    )


def normalized(frame, columns):
    result = frame.copy()
    for column in columns:
        if column in {"rx_id", "matched_rx_id", "approval_channel"}:
            result[column] = result[column].astype("string").str.strip()
        else:
            result[column] = result[column].map(identifier)
    return result


def keys(frame, columns):
    return set(map(tuple, frame[columns].to_numpy()))


def equal_values(left, right):
    return (left.eq(right) | (left.isna() & right.isna())).fillna(False).all()


def validate_sources(line, decisions, uploads):
    line = line.rename(columns=str.lower).copy()
    decisions = decisions.rename(columns=str.lower).copy()
    uploads = uploads.rename(columns=str.lower).copy()
    matched = line.loc[line.line_source_rows.gt(0)].copy()
    identity = [
        "rx_id",
        "customer_id",
        "first_order_id",
        "first_order_line_id",
    ]
    line_identity = normalized(matched, identity)
    line_identity["approval_channel"] = matched.approval_channel.to_numpy()
    if (
        not line_identity.rx_id.is_unique
        or line_identity[identity].isna().any().any()
    ):
        raise ValueError(
            "First-order population has missing or duplicate keys"
        )
    if (
        matched.line_status_variants.ne(1).any()
        or matched.cancel_reason_variants.ne(1).any()
    ):
        raise ValueError("First-order shipment evidence is inconsistent")

    decision_identity = normalized(
        decisions,
        [
            "rx_id",
            "customer_id",
            "first_order_id",
            "first_order_line_id",
            "order_id",
            "order_line_id",
            "approval_channel",
        ],
    )
    if not decision_identity.rx_id.is_unique:
        raise ValueError("Decision extract has duplicate prescription rows")
    if set(decision_identity.rx_id) != set(line_identity.rx_id):
        raise ValueError(
            "Decision extract membership differs from first-order population"
        )
    expected = line_identity.merge(
        decision_identity,
        on="rx_id",
        suffixes=("_population", "_decision"),
        validate="one_to_one",
    )
    for column in [
        "customer_id",
        "first_order_id",
        "first_order_line_id",
    ]:
        if not equal_values(
            expected[f"{column}_population"],
            expected[f"{column}_decision"],
        ):
            raise ValueError(f"Decision {column} differs from population")
    if not equal_values(
        expected.approval_channel_population,
        expected.approval_channel_decision,
    ):
        raise ValueError("Decision approval channel differs from population")
    if (
        not decision_identity.order_id.eq(
            decision_identity.first_order_id
        ).all()
        or not decision_identity.order_line_id.eq(
            decision_identity.first_order_line_id
        ).all()
    ):
        raise ValueError(
            "Decision extract does not match both first-order keys"
        )

    reason_check = (
        matched[["rx_id", "order_cancel_reason"]]
        .rename(columns={"order_cancel_reason": "population_reason"})
        .merge(
            decisions[["rx_id", "cancel_reason"]].rename(
                columns={"cancel_reason": "decision_reason"}
            ),
            on="rx_id",
            validate="one_to_one",
        )
    )
    for column in ["population_reason", "decision_reason"]:
        reason_check[column] = (
            reason_check[column]
            .astype("string")
            .str.strip()
            .str.casefold()
            .replace("", pd.NA)
            .fillna("[missing]")
        )
    if not reason_check.population_reason.eq(
        reason_check.decision_reason
    ).all():
        raise ValueError("Cancellation reasons differ between extracts")

    upload_rows = uploads.loc[
        uploads.matched_rx_id.notna()
        & uploads.matched_order_id.notna()
        & uploads.matched_order_line_id.notna()
    ].copy()
    upload_identity = normalized(
        upload_rows,
        [
            "matched_rx_id",
            "rx_customer_id",
            "upload_customer_id",
            "first_order_id",
            "first_order_line_id",
            "matched_order_id",
            "matched_order_line_id",
        ],
    )
    population_keys = keys(
        line_identity,
        ["rx_id", "customer_id", "first_order_id", "first_order_line_id"],
    )
    upload_keys = keys(
        upload_identity.rename(
            columns={"matched_rx_id": "rx_id", "rx_customer_id": "customer_id"}
        ),
        ["rx_id", "customer_id", "first_order_id", "first_order_line_id"],
    )
    if not upload_keys.issubset(population_keys):
        raise ValueError(
            "Upload/customer association is outside the population"
        )
    if not upload_identity.rx_customer_id.eq(
        upload_identity.upload_customer_id
    ).all():
        raise ValueError("Upload customer differs from prescription customer")
    if (
        not upload_identity.matched_order_id.eq(
            upload_identity.first_order_id
        ).all()
        or not upload_identity.matched_order_line_id.eq(
            upload_identity.first_order_line_id
        ).all()
    ):
        raise ValueError("Upload extract does not match both first-order keys")


def commit(staged_files):
    backups = {}
    installed = []
    backup_root = next(iter(staged_files)).parent / "backups"
    backup_root.mkdir()
    try:
        for destination in staged_files.values():
            if destination.exists():
                backup = backup_root / f"{len(backups)}-{destination.name}"
                shutil.copy2(destination, backup)
                backups[destination] = backup
        for staged, destination in staged_files.items():
            destination.parent.mkdir(parents=True, exist_ok=True)
            os.replace(staged, destination)
            installed.append(destination)
    except Exception:
        for destination in installed:
            destination.unlink(missing_ok=True)
        for destination, backup in backups.items():
            os.replace(backup, destination)
        raise


def main():
    environment = os.environ.copy()
    environment["RXP_REFRESH_RUN_ID"] = RUN_ID
    subprocess.run(
        [
            "make",
            "--no-print-directory",
            "cmpu-first-order-line-status",
            "CACHED=0",
            f"START_DATE={START_DATE}",
            f"END_DATE={END_DATE}",
            f"UPLOAD_START_DATE={UPLOAD_START_DATE}",
        ],
        cwd=ROOT,
        env=environment,
        check=True,
    )
    line_directory = line_source_directory()
    line_manifest_path = line_directory / "source.json"
    line_source_path = line_directory / "source.parquet"
    if not line_manifest_path.is_file() or not line_source_path.is_file():
        raise FileNotFoundError(
            "First-order population extraction must run before study inputs"
        )
    line_manifest = json.loads(line_manifest_path.read_text())
    if line_manifest.get("refresh_run_id") != RUN_ID:
        raise ValueError("First-order population belongs to another run")
    if digest(line_source_path) != line_manifest["parquet_sha256"]:
        raise ValueError("First-order population fingerprint mismatch")
    line = pd.read_parquet(line_source_path)

    count_data = ROOT / "targets/study-population-counts/data"
    upload_destination = artifact_path(ROOT / "data" / UPLOAD_DATASET)
    decision_destination = artifact_path(ROOT / "data" / DECISION_DATASET)
    parameters = {
        "start_date": START_DATE,
        "end_date": END_DATE,
        "upload_start_date": UPLOAD_START_DATE,
        "upload_end_date": UPLOAD_END_DATE,
        "as_of_date": AS_OF_DATE,
    }

    with TemporaryDirectory(
        prefix=f".refresh-{RUN_ID}-", dir=count_data
    ) as temporary:
        stage = Path(temporary)
        staged = {}
        extracted = {}
        queries = {
            "upload": (
                ROOT / "targets/study-population-counts/src/sql/"
                "refresh_study_population_uploaded_documents.sql.j2",
                upload_destination,
            ),
            "decision": (
                ROOT / "targets/study-prescription-decisions/src/sql/"
                "refresh_study_population_prescription_decisions.sql.j2",
                decision_destination,
            ),
        }
        for name, (template, destination) in queries.items():
            query = render(template, **parameters)
            query_path = stage / f"{name}.sql"
            source_path = stage / f"{name}.parquet"
            query_dir = stage / name
            query_dir.mkdir()
            write_text(query_path, query)
            engine = extract(query_path, source_path, query_dir)
            frame = pd.read_parquet(source_path)
            extracted[name] = frame
            source_manifest = {
                "refresh_run_id": RUN_ID,
                "parameters": parameters,
                "sql": query,
                "sql_sha256": hashlib.sha256(query.encode()).hexdigest(),
                "parquet_sha256": digest(source_path),
                "extracted_at_utc": datetime.now(UTC).isoformat(),
                "query_id": engine.get("query_id"),
                "engine": engine.get("engine"),
                "population_dependency_sha256": digest(line_source_path),
            }
            manifest_path = stage / f"{name}.json"
            write_text(
                manifest_path, json.dumps(source_manifest, indent=2) + "\n"
            )
            staged[source_path] = destination / "source.parquet"
            staged[manifest_path] = destination / "source.json"
            staged[query_path] = destination / "query.sql"

        validate_sources(line, extracted["decision"], extracted["upload"])

        commit(staged)

    print(
        f"Validated and installed study-population inputs for run {RUN_ID}: "
        f"{len(extracted['decision']):,} decisions and "
        f"{len(extracted['upload']):,} upload associations."
    )


if __name__ == "__main__":
    main()

import sys
from pathlib import Path

from shared.cohort_queries import render_cohort_query
from shared.paths import artifact_path
from shared.sql_templates import module_sql

sys.path.insert(
    0,
    str(
        next(
            p
            for p in Path(__file__).resolve().parents
            if (p / "analysis.yaml").exists()
        )
    ),
)
"""REFNUM 60: first/all-order cancellation comparison and exact net sales."""
import hashlib
import json
import os
import shutil
import sys
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

from shared.paths import canonical_sql_path, repository_root

ROOT = repository_root()
sys.path.insert(0, str(ROOT))
import click
import duckdb
import pandas as pd

from shared.python import (
    create_opportunity_order_cancellation_summary as opportunity,
)
from shared.python.markdown_tables import markdown_table, write_text

DIRECTORY = artifact_path(
    ROOT
    / (
        "data/opportunity/prescription-cohort-order-comparison/2026-"
        "08-15_2026-10-15_as-of-2026-10-27"
    )
)
TEMPLATE = canonical_sql_path("prescription_cohort_order_sales.sql")
CUTOFF = pd.Timestamp("2026-10-27", tz="UTC")
KEYS = opportunity.KEYS
MONEY = "order_line_net_sales"


def summarize(frozen, raw):
    frozen, raw = frozen.copy(), raw.rename(columns=str.lower).copy()
    for frame in [frozen, raw]:
        for col in KEYS + ["customer_id"]:
            frame[col] = frame[col].map(opportunity.identifier)
    raw["shipment_key"] = raw.shipment_key.map(opportunity.identifier)
    if frozen[KEYS].isna().any().any() or frozen.duplicated(KEYS).any():
        raise ValueError("invalid frozen physical-line membership")
    if raw[KEYS].isna().any().any():
        raise ValueError("missing financial physical-line keys")
    if set(map(tuple, raw[KEYS].to_numpy())) != set(
        map(tuple, frozen[KEYS].to_numpy())
    ):
        raise ValueError("financial source keys differ from frozen cohort")
    raw[MONEY] = raw[MONEY].map(opportunity.money).astype(object)
    for col in ["order_placed_utc", "order_cancel_utc"]:
        raw[col] = pd.to_datetime(
            raw[col], utc=True, format="mixed", errors="raise"
        )
    raw["reason_key"] = (
        raw.order_cancel_reason.astype("string")
        .str.strip()
        .str.casefold()
        .replace("", pd.NA)
        .fillna(opportunity.MISSING_REASON)
    )
    if (
        raw.groupby(KEYS)[
            [
                "customer_id",
                "reason_key",
                "order_placed_utc",
                "order_cancel_utc",
            ]
        ]
        .nunique(dropna=False)
        .gt(1)
        .any()
        .any()
    ):
        raise ValueError(
            "conflicting financial line identity or "
            "cancellation/placement evidence"
        )
    if (
        raw.groupby(KEYS + ["shipment_key"], dropna=False)[MONEY]
        .nunique(dropna=False)
        .gt(1)
        .any()
    ):
        raise ValueError("conflicting sales on the same financial source key")
    ships = raw.drop_duplicates(KEYS + ["shipment_key"]).copy()
    ships["missing_sales"] = ships[MONEY].isna()
    amounts = (
        ships.groupby(KEYS, dropna=False)
        .agg(
            known_net_sales=(MONEY, opportunity.decimal_sum),
            missing_sales_records=("missing_sales", "sum"),
            shipment_records=("shipment_key", "size"),
        )
        .reset_index()
    )
    identity = ships.drop_duplicates(KEYS)[
        KEYS
        + ["customer_id", "reason_key", "order_placed_utc", "order_cancel_utc"]
    ]
    compare = frozen.merge(
        identity, on=KEYS, validate="one_to_one", suffixes=("", "_current")
    )
    if (
        not compare.customer_id.eq(compare.customer_id_current).all()
        or not compare.reason.eq(compare.reason_key).all()
    ):
        raise ValueError(
            "financial source identity/reason differs from frozen comparison"
        )
    expected_aged = compare.reason_key.eq(
        "aged order"
    ) & compare.order_cancel_utc.le(CUTOFF)
    if not expected_aged.eq(compare.aged_by_prior_cutoff.eq(1)).all():
        raise ValueError(
            "aged-cancellation membership differs from frozen cutoff"
        )
    lines = frozen.merge(amounts, on=KEYS, validate="one_to_one")
    lines["actual_net_sales"] = lines.known_net_sales.where(
        lines.missing_sales_records.eq(0), None
    )
    rows = []

    def row(g, label, kind):
        r = {"row_type": kind, "cancellation_reason": label}
        for prefix, part in [
            ("first", g.loc[g.first_order_line.eq(1)]),
            ("all", g),
        ]:
            missing = int(part.missing_sales_records.sum())
            known = opportunity.decimal_sum(part.known_net_sales)
            r.update(
                {
                    prefix + "_orders": part.order_id.nunique(),
                    prefix + "_lines": len(part),
                    prefix + "_net_sales": None if missing else known,
                    prefix + "_known_net_sales": known,
                    prefix + "_missing_sales_records": missing,
                }
            )
        return r

    for reason, g in lines.groupby("report_reason", sort=True):
        label = reason if reason.startswith("[") else reason.capitalize()
        rows.append(row(g, label, "reason"))
    rows.append(row(lines, "TOTAL", "total"))
    summary = pd.DataFrame(rows)
    for prefix in ["first", "all"]:
        detail = summary.loc[summary.row_type.eq("reason")]
        total = summary.loc[summary.row_type.eq("total")].iloc[0]
        if (
            detail[prefix + "_lines"].sum() != total[prefix + "_lines"]
            or opportunity.decimal_sum(detail[prefix + "_known_net_sales"])
            != total[prefix + "_known_net_sales"]
        ):
            raise ValueError("reason subtotals do not reconcile")
    return ships, lines, summary


def derive_population(raw):
    """Derive comparison membership from the database result, not saved IDs."""
    frame = raw.rename(columns=str.lower).copy()
    for column in KEYS + ["customer_id"]:
        frame[column] = frame[column].map(opportunity.identifier)
    if frame[KEYS + ["customer_id"]].isna().any().any():
        raise ValueError("financial query returned missing physical-line keys")
    frame["order_cancel_utc"] = pd.to_datetime(
        frame.order_cancel_utc, utc=True, format="mixed", errors="raise"
    )
    frame["reason"] = (
        frame.order_cancel_reason.astype("string")
        .str.strip()
        .str.casefold()
        .replace("", pd.NA)
        .fillna(opportunity.MISSING_REASON)
    )
    frame["first_order_line"] = pd.to_numeric(
        frame.first_order_line, errors="raise"
    )
    if not frame.first_order_line.isin([0, 1]).all():
        raise ValueError("invalid database-derived first-order flag")
    dimensions = [
        "customer_id",
        "reason",
        "order_cancel_utc",
        "first_order_line",
    ]
    if (
        frame.groupby(KEYS, dropna=False)[dimensions]
        .nunique(dropna=False)
        .gt(1)
        .any()
        .any()
    ):
        raise ValueError("conflicting physical-line cohort evidence")
    population = frame.drop_duplicates(KEYS)[KEYS + dimensions].copy()
    population["aged_by_prior_cutoff"] = (
        population.reason.eq("aged order")
        & population.order_cancel_utc.le(CUTOFF)
    ).astype("int64")
    population["report_reason"] = population.reason
    population.loc[
        population.reason.eq("aged order")
        & population.aged_by_prior_cutoff.eq(0),
        "report_reason",
    ] = "[Aged order outside cutoff]"
    return population.drop(columns="order_cancel_utc")


def validate_population_dependency(frozen, run_id):
    period = (
        "2026-08-15_2026-10-15_uploads-from-2026-08-01_"
        "uploads-end-2026-10-26_accepted-state-change_order-placed_"
        "block-reasons"
    )
    line_directory = artifact_path(
        ROOT / "data/cmpu-first-order-line-status" / period
    )
    source_path = line_directory / "source.parquet"
    manifest = json.loads((line_directory / "source.json").read_text())
    if opportunity.digest(source_path) != manifest.get("parquet_sha256"):
        raise ValueError("First-order population fingerprint mismatch")
    if run_id is not None and manifest.get("refresh_run_id") != run_id:
        raise ValueError("Financial and first-order sources mix refresh runs")
    line = pd.read_parquet(source_path).rename(columns=str.lower)
    line = line.loc[
        line.line_source_rows.gt(0)
        & line.approval_channel.eq("CUSTOMER_UPLOAD")
    ]
    expected = line[
        ["customer_id", "first_order_id", "first_order_line_id"]
    ].rename(
        columns={
            "first_order_id": "order_id",
            "first_order_line_id": "order_line_id",
        }
    )
    expected = expected.apply(
        lambda column: column.map(opportunity.identifier)
    )
    actual = frozen.loc[
        frozen.first_order_line.eq(1),
        ["customer_id", "order_id", "order_line_id"],
    ].apply(lambda column: column.map(opportunity.identifier))
    if set(map(tuple, expected.to_numpy())) != set(
        map(tuple, actual.to_numpy())
    ):
        raise ValueError(
            "Financial first-order membership differs from the population"
        )
    return manifest["parquet_sha256"]


def promote_refresh(stage, metadata):
    """Install validated source files and roll back failed replacements."""
    DIRECTORY.mkdir(parents=True, exist_ok=True)
    files = {
        "query.sql": DIRECTORY / "query.sql",
        "source.parquet": DIRECTORY / "source.parquet",
        "population.parquet": DIRECTORY / "population.parquet",
    }
    metadata_path = DIRECTORY / "source.json"
    staged_metadata = stage / "source.json"
    write_text(staged_metadata, json.dumps(metadata, indent=2) + "\n")
    files["source.json"] = metadata_path
    backups = stage / "backup"
    backups.mkdir()
    previous = {}
    installed = []
    try:
        for name, destination in files.items():
            if destination.exists():
                backup = backups / name
                shutil.copy2(destination, backup)
                previous[destination] = backup
        for name, destination in files.items():
            os.replace(stage / name, destination)
            installed.append(destination)
    except Exception:
        for destination in installed:
            destination.unlink(missing_ok=True)
        for destination, backup in previous.items():
            os.replace(backup, destination)
        raise


def verify(frozen, raw, summary):
    # Another engine recomputes counts and money directly from unique source
    # shipment records and the frozen line flags/reason labels.
    sql = module_sql(
        __file__,
        "summarize_prescription_cohort_order_comparison-query-1.sql.j2",
    )
    with duckdb.connect() as c:
        c.register("source", raw.rename(columns=str.lower))
        c.register("frozen", frozen)
        results = c.execute(sql).fetchall()
    observed = {
        (scope, kind, reason.casefold()): (orders, n, amount)
        for scope, kind, reason, orders, n, amount in results
    }
    expected = {}
    for r in summary.to_dict("records"):
        for scope in ["first", "all"]:
            value = r[scope + "_net_sales"]
            expected[
                (scope, r["row_type"], r["cancellation_reason"].casefold())
            ] = (
                r[scope + "_orders"],
                r[scope + "_lines"],
                None if pd.isna(value) else value,
            )
    # SQL omits a completely empty first-order reason group. Its additive
    # contribution is explicitly zero in the report table.
    for key, value in expected.items():
        if key not in observed and value == (0, 0, Decimal("0.00000")):
            observed[key] = value
    if observed != expected:
        raise ValueError("independent source-based counts or net sales differ")
    return {
        "engine": "DuckDB raw shipment/source aggregation",
        "sql": sql,
        "verified_cells": len(expected),
    }


def fmt_money(value):
    return "Incomplete" if pd.isna(value) else f"{value:,.2f}"


def latex_table(summary):
    def escape(value):
        for old, new in [
            ("\\", r"\textbackslash{}"),
            ("&", r"\&"),
            ("%", r"\%"),
            ("_", r"\_"),
            ("#", r"\#"),
        ]:
            value = value.replace(old, new)
        return value

    body = []
    for r in summary.to_dict("records"):
        if r["row_type"] == "total":
            body.append(r"\midrule")
        values = ["{" + escape(r["cancellation_reason"]) + "}"]
        for scope in ["first", "all"]:
            amount = fmt_money(r[scope + "_net_sales"])
            if (
                r["row_type"] == "reason"
                and r["cancellation_reason"] != opportunity.MISSING_REASON
            ):
                amount = r"\textcolor{gray}{" + amount + "}"
            values += [
                f"{r[scope + '_orders']:,}",
                f"{r[scope + '_lines']:,}",
                amount,
            ]
        body.append(" & ".join(values) + r" \\")
    return (
        (
            "% BEGIN FIRST-ALL-ORDER-CANCELLATION-"
            "COMPARISON\n\\begin{table}[htbp]\n\\centering\n\\captio"
            "n{Cancellation reasons, order counts and net sales for "
            "first orders and all linked "
            "orders.}\n\\label{tab:first-all-order-"
            "cancellations}\n\\small\n\\setlength{\\tabcolsep}{5pt}"
            "\n\\begin{tabular}{@{}>{\\raggedright\\arraybackslash}p"
            "{0.28\\linewidth}rrrrrr@{}}\n\\toprule\n & "
            "\\multicolumn{3}{c}{First orders} & "
            "\\multicolumn{3}{c}{All orders} \\\\\n\\cmidrule(lr){2-"
            "4}\\cmidrule(lr){5-7}\nCancellation reason & Orders & "
            "Lines & Net sales & Orders & Lines & Net sales "
            "\\\\\n\\midrule\n"
        )
        + "\n".join(body)
        + (
            "\n\\bottomrule\n\\end{tabular}\n\n\\begin{minipage}{\\l"
            "inewidth}\n\\footnotesize\n\\textit{Notes:} CMPU vet-"
            "diet \\texttt{CUSTOMER\\_UPLOAD} prescriptions "
            "created\nAugust 15--October 14, 2026, UTC. All orders "
            "includes first and subsequent linked\norders, without "
            "an order-placement window. Qualifying aged "
            "cancellations are\nobserved on or before October 27, "
            "2026, 00:00 UTC; current aged reasons outside\nthat "
            "cutoff are shown separately for reconciliation. Other "
            "reasons reflect\nthe comparison snapshot. Counts are "
            "distinct orders and physical lines within\neach group. "
            "Net sales sum \\texttt{ORDER\\_LINE\\_NET\\_SALES} "
            "once per\nshipment/line record, for qualifying lines "
            "only. Amounts are displayed\nto two decimals; five-"
            "decimal values remain in the data exports.\nGray net-"
            "sales amounts have a recorded cancellation reason and "
            "represent\nunrealized sales, not realized revenue. "
            "TOTAL includes these gray amounts. The financial cohort "
            "is derived from current prescription/order records and "
            "reconciled to the current first-order population.\n"
            "\\end{minipage}\n\\end{table}\n% END FIRST-"
            "ALL-ORDER-CANCELLATION-COMPARISON\n"
        )
    )


def write_exports(ships, lines, summary, metadata, write_latex):
    for name, frame in [
        ("shipments", ships),
        ("order-lines-with-sales", lines),
        ("summary", summary),
    ]:
        # Extend the existing exact-decimal writer to both population columns.
        money_cols = [c for c in frame if c.endswith("net_sales")]
        import pyarrow as pa
        import pyarrow.parquet as pq

        table = pa.Table.from_pandas(
            frame.drop(columns=money_cols), preserve_index=False
        )
        for col in money_cols:
            table = table.append_column(
                col, pa.array(frame[col].tolist(), type=pa.decimal128(38, 5))
            )
        pq.write_table(table, DIRECTORY / f"{name}.parquet")
    shown = summary[
        [
            "cancellation_reason",
            "first_orders",
            "first_lines",
            "first_net_sales",
            "all_orders",
            "all_lines",
            "all_net_sales",
        ]
    ].copy()
    for col in shown:
        if col.endswith("net_sales"):
            shown[col] = shown[col].map(fmt_money)
        elif col != "cancellation_reason":
            shown[col] = shown[col].map(lambda n: f"{n:,}")
    tables = artifact_path(
        ROOT / "outputs/tables/opportunity/2026-08-15_2026-10-14"
    )
    tables.mkdir(parents=True, exist_ok=True)
    note = (
        "Uses the fingerprint-verified all-order comparison membership and "
        "the inclusive October 27, 2026, 00:00 UTC aged cutoff. "
        "First orders are a subset of all orders; do not add the two "
        "populations. Net sales sum unique shipment/line contributions, "
        "preserving zero and negative sales. Five-decimal precision remains "
        "in Parquet; only display is rounded. "
        f"Financial source extracted {metadata['extracted_at_utc']}.\n\n"
    )
    write_text(
        tables / "first-all-order-cancellation-comparison.md",
        "# First/all-order cancellation and net-sales comparison\n\n"
        + note
        + markdown_table(shown)
        + "\n",
    )
    write_text(DIRECTORY / "comparison-table.tex", latex_table(summary))
    write_text(
        DIRECTORY / "analysis.json",
        json.dumps(
            dict(
                metadata,
                exports={
                    p.name: opportunity.digest(p)
                    for p in DIRECTORY.glob("*.parquet")
                },
            ),
            indent=2,
        )
        + "\n",
    )
    if write_latex:
        target = artifact_path(
            ROOT
            / "targets/report/src/latex/retained/appendix"
            / "study_population_analysis.tex"
        )
        text = target.read_text()
        start = "% BEGIN FIRST-ALL-ORDER-CANCELLATION-COMPARISON"
        end = "% END FIRST-ALL-ORDER-CANCELLATION-COMPARISON"
        if start in text:
            left = text.index(start)
            right = text.index(end, left) + len(end)
            text = text[:left] + latex_table(summary).rstrip() + text[right:]
        else:
            text = text.rstrip() + "\n\n" + latex_table(summary)
        write_text(target, text)


@click.command()
@click.option(
    "--refresh",
    is_flag=True,
    help="Fetch current sales and derive the comparison cohort from SQL.",
)
@click.option(
    "--write-latex",
    is_flag=True,
    help="Update the labelled table in the report appendix.",
)
def main(refresh, write_latex):
    sql = render_cohort_query(TEMPLATE)
    DIRECTORY.mkdir(parents=True, exist_ok=True)
    raw_path = DIRECTORY / "source.parquet"
    manifest = DIRECTORY / "source.json"
    if refresh:
        parameters = {
            "start_date": "2026-08-15",
            "end_date": "2026-10-15",
            "as_of_date": "2026-10-27",
        }
        run_id = os.environ.get("RXP_REFRESH_RUN_ID") or uuid4().hex
        with TemporaryDirectory(
            prefix=".study-population-refresh-", dir=DIRECTORY
        ) as temporary:
            stage = Path(temporary)
            query = stage / "query.sql"
            staged_raw = stage / "source.parquet"
            write_text(query, sql + "\n")
            engine = opportunity.extract(query, staged_raw, stage)
            raw = pd.read_parquet(staged_raw)
            frozen = derive_population(raw)
            population_hash = validate_population_dependency(frozen, run_id)
            ships, lines, summary = summarize(frozen, raw)
            verification = verify(frozen, raw, summary)
            staged_population = stage / "population.parquet"
            frozen.to_parquet(staged_population, index=False)
            metadata = {
                "refresh_run_id": run_id,
                "parameters": parameters,
                "sql": sql,
                "sql_sha256": hashlib.sha256(sql.encode()).hexdigest(),
                "parquet_sha256": opportunity.digest(staged_raw),
                "population_sha256": opportunity.digest(staged_population),
                "population_dependency_sha256": population_hash,
                "extracted_at_utc": datetime.now(UTC).isoformat(),
                "query_id": engine.get("query_id"),
                "engine": engine.get("engine"),
                "independent_verification": verification,
            }
            promote_refresh(stage, metadata)
    else:
        if not manifest.is_file() or not raw_path.is_file():
            raise click.ClickException(
                "No retained financial extract; run with REFRESH=1."
            )
        metadata = json.loads(manifest.read_text())
        frozen_path = DIRECTORY / "population.parquet"
        if (
            metadata["parquet_sha256"] != opportunity.digest(raw_path)
            or metadata.get("sql_sha256")
            != hashlib.sha256(sql.encode()).hexdigest()
            or not frozen_path.is_file()
            or metadata.get("population_sha256")
            != opportunity.digest(frozen_path)
        ):
            raise click.ClickException(
                "cached financial extract or derived membership fingerprint "
                "differs; use REFRESH=1"
            )
        frozen = pd.read_parquet(frozen_path)
        raw = pd.read_parquet(raw_path)
        validate_population_dependency(frozen, metadata.get("refresh_run_id"))
        ships, lines, summary = summarize(frozen, raw)
        metadata["independent_verification"] = verify(frozen, raw, summary)
    write_exports(ships, lines, summary, metadata, write_latex)
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()

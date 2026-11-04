"""
Split the frozen section 2.1.2 successful lines by ECOM auto-reorder flag.
"""

import hashlib
import json
from datetime import UTC, datetime

import click
import duckdb
import pandas as pd

from shared.cohort_queries import cached_expectations, render_cohort_query
from shared.paths import artifact_path, canonical_sql_path, latex_fragment_path
from shared.python import create_opportunity_order_cancellation_summary as base
from shared.python.follow_up_tables import SOURCES, read_table
from shared.python.markdown_tables import markdown_table, write_text
from shared.sql_templates import module_sql

ROOT = base.ROOT
HORIZONS = list(range(7, 71, 7))
KEYS = ["reorder_order_id", "reorder_line_id"]
PERIOD = "2026-05-01_2026-08-01_7d-70d_as-of-2026-10-28"
FOLDERS = [
    "aged-reorder-studies",
    "new-upload-customer-follow-up-studies",
    "new-vet-diet-customer-follow-up-studies",
]
OUT = artifact_path(ROOT / "data/opportunity/same-pet-part-auto-reorder")
TABLES = artifact_path(
    ROOT / "outputs/tables/opportunity/same-pet-part-auto-reorder"
)


def load_inputs():
    inputs, fingerprints = {}, {}
    for i, (label, filename) in enumerate(SOURCES):
        period = (
            PERIOD
            if i
            else PERIOD.replace("7d-70d", "-".join(f"{d}d" for d in HORIZONS))
        )
        directory = artifact_path(
            ROOT / "data/opportunity" / FOLDERS[i] / period
        )
        manifest = directory / ("source.json" if i == 0 else "analysis.json")
        meta = json.loads(manifest.read_text())

        def read(name, directory=directory, meta=meta):
            path = directory / name
            digest = base.digest(path)
            if digest != meta["exports"][name]:
                raise ValueError(f"Frozen export fingerprint differs: {path}")
            fingerprints[str(path.relative_to(ROOT))] = digest
            return pd.read_parquet(path)

        fragment = latex_fragment_path(filename, root=ROOT)
        published, denominator, _, cutoff = read_table(fragment)
        if cutoff != "2026-10-28 00:00 UTC":
            raise ValueError("Published observation cutoff changed")
        fingerprints[str(fragment.relative_to(ROOT))] = base.digest(fragment)
        summary = read("summary.parquet")
        if "study" in summary:
            summary = summary.loc[summary.study.eq("same-part-pet")]
        for day, printed in zip(HORIZONS, published, strict=True):
            r = read(f"same-part-pet-{day}d-reorders.parquet")
            for col in KEYS + ["reorder_customer_id", "original_customer_id"]:
                r[col] = r[col].map(base.identifier)
            if r.duplicated(KEYS).any() or r[KEYS].isna().any().any():
                raise ValueError("Invalid physical line keys")
            if not (
                r.qualifying_non_cancelled.all()
                and r.reorder_order_has_cancellation.eq(0).all()
                and r.reorder_order_has_unknown_status.eq(0).all()
                and r.original_customer_id.eq(r.reorder_customer_id).all()
            ):
                raise ValueError("Successful-order/customer validation failed")
            sales = base.decimal_sum(r.reorder_known_net_sales.map(base.money))
            s = summary.loc[summary.followup_days.eq(day)].iloc[0]
            denom = int(denominator.replace(",", ""))
            if not (
                int(s.cohort_customers) == denom
                and len(r) == int(s.matching_lines)
                and sales == base.money(s.known_net_sales)
                and int(r.missing_sales_records.sum())
                == int(s.missing_sales_records)
            ):
                raise ValueError("Frozen line totals differ from summary")
            expected = [
                str(day),
                f"{r.reorder_customer_id.nunique():,}",
                f"{100 * r.reorder_customer_id.nunique() / denom:.2f}\\%",
                f"{r.reorder_order_id.nunique():,}",
                f"{sales:,.2f}",
            ]
            if [v.strip() for v in printed] != expected:
                raise ValueError(f"Published table differs: {label}, {day}")
            inputs[(label, day)] = (r, denom)
    return inputs, fingerprints


def lookup_sql():
    return render_cohort_query(
        canonical_sql_path("opportunity_auto_reorder_flags.sql")
    )


@click.command()
@click.option("--cached", is_flag=True)
def main(cached):
    inputs, fingerprints = load_inputs()
    OUT.mkdir(parents=True, exist_ok=True)
    TABLES.mkdir(parents=True, exist_ok=True)
    keys = (
        pd.concat([r[KEYS] for r, _ in inputs.values()])
        .drop_duplicates()
        .sort_values(KEYS)
    )
    sql = lookup_sql()
    identity = {
        "inputs": fingerprints,
        "sql_sha256": hashlib.sha256(sql.encode()).hexdigest(),
    }
    source, manifest = OUT / "flags.parquet", OUT / "source.json"
    if cached:
        metadata = json.loads(manifest.read_text())
        recorded_identity = dict(
            metadata["identity"],
            inputs={
                str(artifact_path(ROOT / path).relative_to(ROOT)): fingerprint
                for path, fingerprint in metadata["identity"]["inputs"].items()
            },
        )
        identity = cached_expectations(
            dict(recorded_identity, source_sha256=metadata["source_sha256"]),
            identity,
        )
        if recorded_identity != identity or metadata[
            "source_sha256"
        ] != base.digest(source):
            raise ValueError(
                "Cached flag lookup or frozen inputs changed; rerun "
                "without CACHED=1"
            )
    else:
        query = artifact_path(
            ROOT / "src/autogenerated/opportunity-auto-reorder-flags.sql"
        )
        query.parent.mkdir(parents=True, exist_ok=True)
        write_text(query, sql)
        engine = base.extract(query, source, OUT)
        metadata = {
            "identity": identity,
            "source_sha256": base.digest(source),
            "engine": engine,
            "extracted_at_utc": datetime.now(UTC).isoformat(),
        }
        write_text(manifest, json.dumps(metadata, indent=2) + "\n")
    flags = pd.read_parquet(source).rename(columns=str.lower)
    for col in KEYS + ["ecom_customer_id"]:
        flags[col] = flags[col].map(base.identifier)
    flags = flags.drop_duplicates()
    if flags.duplicated(KEYS).any():
        raise ValueError(
            "Conflicting ECOM flags/customer values for one physical line"
        )
    if set(map(tuple, flags[KEYS].to_numpy())) != set(
        map(tuple, keys.to_numpy())
    ):
        raise ValueError("Flag lookup keys differ from requested keys")
    if not flags.auto_reorder_flag.dropna().isin([True, False]).all():
        raise ValueError("Unexpected non-Boolean flag")
    flags["flag_group"] = flags.auto_reorder_flag.map(
        {True: "TRUE", False: "FALSE"}
    ).fillna("NULL")
    flags.loc[flags.ecom_matched.eq(0), "flag_group"] = "UNMATCHED"
    rows, overlaps = [], []
    for (label, day), (r, denominator) in inputs.items():
        merged = r.merge(flags, on=KEYS, how="left", validate="one_to_one")
        found = merged.ecom_matched.eq(1)
        if (
            not merged.loc[found, "reorder_customer_id"]
            .eq(merged.loc[found, "ecom_customer_id"])
            .all()
        ):
            raise ValueError("ECOM customer does not match frozen customer")
        totals = []
        for flag in ["FALSE", "TRUE", "NULL", "UNMATCHED"]:
            part = merged.loc[merged.flag_group.eq(flag)]
            sales = base.decimal_sum(
                part.reorder_known_net_sales.map(base.money)
            )
            totals.append(sales)
            missing = int(part.missing_sales_records.sum())
            rows.append(
                {
                    "cohort": label,
                    "days": day,
                    "auto_reorder": flag,
                    "cohort_customers": denominator,
                    "customers": part.reorder_customer_id.nunique(),
                    "percentage": 100
                    * part.reorder_customer_id.nunique()
                    / denominator,
                    "orders": part.reorder_order_id.nunique(),
                    "lines": len(part),
                    "net_sales": None if missing else sales,
                    "known_net_sales": sales,
                    "missing_sales_records": missing,
                }
            )
        # Independent SQL aggregation verifies each partition at retained
        # decimal precision.
        sql_lines = merged[
            [
                "flag_group",
                "reorder_customer_id",
                "reorder_order_id",
                "reorder_known_net_sales",
                "missing_sales_records",
            ]
        ].copy()
        sql_lines["reorder_known_net_sales"] = (
            sql_lines.reorder_known_net_sales.map(str)
        )
        with duckdb.connect() as con:
            con.register("matched_lines", sql_lines)
            independently = con.execute(
                module_sql(
                    __file__, "create_opportunity_auto_reorder-query-2.sql.j2"
                )
            ).fetchall()
        expected = {row["auto_reorder"]: row for row in rows[-4:]}
        for flag, lines, customers, orders, sales, missing in independently:
            row = expected[flag]
            if (lines, customers, orders, sales, missing) != (
                row["lines"],
                row["customers"],
                row["orders"],
                row["known_net_sales"],
                row["missing_sales_records"],
            ):
                raise ValueError(
                    "Independent SQL partition aggregation differs"
                )
        if sum(totals) != base.decimal_sum(
            r.reorder_known_net_sales.map(base.money)
        ):
            raise ValueError("Partitioned sales do not reconcile")
        if sum(row["lines"] for row in rows[-4:]) != len(r):
            raise ValueError("Partitioned lines do not reconcile")
        f, t = [merged.loc[merged.flag_group.eq(v)] for v in ["FALSE", "TRUE"]]
        overlaps.append(
            {
                "cohort": label,
                "days": day,
                "customers_in_both": len(
                    set(f.reorder_customer_id) & set(t.reorder_customer_id)
                ),
                "orders_in_both": len(
                    set(f.reorder_order_id) & set(t.reorder_order_id)
                ),
            }
        )
        merged.to_parquet(
            OUT
            / (
                f"{FOLDERS[[s[0] for s in SOURCES].index(label)]}"
                "-"
                f"{day}"
                "d-lines.parquet"
            ),
            index=False,
        )
    result = pd.DataFrame(rows)
    base.write_parquet(result, OUT / "summary.parquet")
    pd.DataFrame(overlaps).to_parquet(OUT / "overlaps.parquet", index=False)
    note = (
        "Original cancellation cohort: May 1–July 31, 2026 UTC; follow-up "
        "cutoff October 28, 2026 00:00 UTC. "
        "Only later successful lines are split; original cohorts and "
        "denominators are unchanged. "
        "Same customer, pet and exact part number, with existing whole-order "
        "cancellation/unknown-status exclusions. "
        "Money is retained RxP shipment-aggregated line net sales, not ECOM "
        "sales. "
        "Customers and orders can occur in both groups; do not add their "
        "distinct counts. "
        "NULL and unmatched flags are excluded from TRUE/FALSE and audited "
        "separately. "
        f"Flags reflect the ECOM snapshot retrieved "
        f"{metadata['extracted_at_utc']}; they are not historical as-of "
        f"flags.\n\n"
    )
    for flag in ["FALSE", "TRUE"]:
        text = f"# Section 2.1.2 — auto-reorder {flag}\n\n" + note
        for label, _ in SOURCES:
            shown = result.loc[
                result.auto_reorder.eq(flag) & result.cohort.eq(label),
                [
                    "days",
                    "cohort_customers",
                    "customers",
                    "percentage",
                    "orders",
                    "lines",
                    "net_sales",
                ],
            ].copy()
            shown.percentage = shown.percentage.map(lambda v: f"{v:.2f}%")
            shown.net_sales = shown.net_sales.map(
                lambda v: "Incomplete" if pd.isna(v) else f"{v:,.2f}"
            )
            text += f"## {label}\n\n" + markdown_table(shown) + "\n\n"
        write_text(artifact_path(TABLES / f"{flag.lower()}.md"), text)
        click.echo(text)
    write_text(
        artifact_path(TABLES / "audit.md"),
        "# Flag coverage and overlaps\n\n"
        + note
        + markdown_table(
            result.loc[
                result.auto_reorder.isin(["NULL", "UNMATCHED"]),
                [
                    "cohort",
                    "days",
                    "auto_reorder",
                    "customers",
                    "orders",
                    "lines",
                    "known_net_sales",
                ],
            ]
        )
        + "\n\n"
        + markdown_table(pd.DataFrame(overlaps))
        + "\n",
    )
    write_text(
        OUT / "analysis.json",
        json.dumps(
            {
                "identity": identity,
                "flag_source_sha256": base.digest(source),
                "reconciled_windows": len(inputs),
                "exports": {
                    p.name: base.digest(p) for p in OUT.glob("*.parquet")
                },
            },
            indent=2,
        )
        + "\n",
    )


if __name__ == "__main__":
    main()

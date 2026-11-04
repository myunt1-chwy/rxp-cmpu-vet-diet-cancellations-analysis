"""REFNUM 51: upload creation to current state-change timing."""

import hashlib
import json
import subprocess
import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import click
import pandas as pd
from jinja2 import Environment, StrictUndefined

from shared.python.duration_plots import boxplot, statistics
from shared.python.markdown_tables import markdown_table, write_text
from shared.python.paths import (
    artifact_path,
    canonical_sql_path,
    output_path,
    repository_root,
    source_ownership,
)
from shared.python.runtime import RUNNER, digest
from shared.python.upload_entities import parameters, validate

ROOT = repository_root()
NAME = "cmpu-upload-entity-state-change-distributions"
TEMPLATE = canonical_sql_path(
    "cmpu_upload_entity_state_change_distributions.sql"
)
VERSION = 1
POPULATIONS = ("all-study-linked", "aged-order")


def render_sql(start, end, upload_start, as_of):
    return (
        Environment(undefined=StrictUndefined)
        .from_string(TEMPLATE.read_text())
        .render(**parameters(start, end, upload_start, as_of))
    )


def write_outputs(frame, metadata, directory, charts, tables):
    params = metadata["parameters"]
    associations, entities, audit = validate(frame, params)
    states = sorted(entities.state_label.unique()) or ["[No entities]"]
    values = entities.loc[entities.usable_duration, "elapsed_hours"]
    domain = [
        min(float(values.min()), 0.0) if len(values) else 0.0,
        max(float(values.max()), 0.0) if len(values) else 0.0,
    ]
    # Share a domain including zero; pad endpoints and singletons.
    domain = [
        domain[0] * 1.1 if domain[0] < 0 else -1 / 3600,
        domain[1] * 1.1 if domain[1] > 0 else 1 / 3600,
    ]
    for path in [directory, charts, tables]:
        path.mkdir(parents=True, exist_ok=True)
    exports = {"associations": associations, "audit": audit}
    note = (
        "One UPLOAD_ID per population. All current states and all matching "
        "entities; no ACCEPTED or 60-second filter. "
        "Elapsed hours = (STATE_CHANGED_TS_UTC − CREATED_TS_UTC) / 3600 "
        "seconds. "
        "Negative durations remain usable and flagged. Missing timestamps "
        "remain in exports and counts but not duration marks. "
        "Null creation dates have unknown discovery-window membership and are "
        "retained for audit. "
        "Aged membership requires any matched first-order pair with "
        "normalized reason Aged Order and cancellation at/before "
        f"{params['as_of_date']} 00:00 UTC. Current state changes are not "
        f"censored at cancellation or cutoff. "
        "Quantiles use linear interpolation; whiskers are observed extrema "
        "within 1.5×IQR fences. All outliers retained. "
        "Shared symmetric-log hours axis, linear-region constant one second. "
        "n = usable / total entities. "
        f"Prescription window [{params['start_date']}, {params['end_date']}); "
        f"upload creation window "
        f"[{params['upload_start_date']}, {params['upload_end_date']}) UTC. "
        f"Extracted {metadata['extracted_at_utc']}; source SHA-256 "
        f"{metadata['parquet_sha256']}.\n\n"
    )
    for population in POPULATIONS:
        selected = (
            entities
            if population == POPULATIONS[0]
            else entities.loc[entities.aged_entity]
        )
        population_audit = [
            ("entities", len(selected)),
            ("null states", int(selected.state_name.isna().sum())),
            ("zero durations", int(selected.elapsed_hours.eq(0).sum())),
        ]
        population_audit += [
            (column, int(selected[column].sum()))
            for column in [
                "usable_duration",
                "missing_creation",
                "missing_state_change",
                "unknown_discovery_window",
                "negative_duration",
            ]
        ]
        audit = pd.concat(
            [
                audit,
                pd.DataFrame(
                    [
                        (population + ": " + key, value)
                        for key, value in population_audit
                    ],
                    columns=["measure", "count"],
                ),
            ],
            ignore_index=True,
        )
        stats = statistics(selected, states)
        if (
            stats.entities.sum() != len(selected)
            or stats.usable.sum() != selected.usable_duration.sum()
        ):
            raise ValueError("state counts do not reconcile")
        exports[population + "-entities"] = selected
        exports[population + "-statistics"] = stats
        subtitle = [
            (
                f"CMPU vet diet · CUSTOMER_UPLOAD · Rx {params['start_date']} "
                f"to {params['end_date']} exclusive (UTC)"
            ),
            (
                f"Uploads {params['upload_start_date']} to "
                f"{params['upload_end_date']} exclusive (UTC)"
            ),
            (
                f"{len(selected):,} entities · "
                f"{int(selected.usable_duration.sum()):,} usable durations · "
                f"n = usable / total"
            ),
            (
                "Median, quartiles, 1.5×IQR whiskers and all outliers · "
                "One-second linear region around zero"
            ),
        ]
        if population == POPULATIONS[1]:
            subtitle.insert(
                2,
                (
                    f"Aged first-order cancellation ≤ {params['as_of_date']} "
                    f"00:00 UTC · Current entity states"
                ),
            )
        chart = boxplot(
            selected,
            stats,
            states,
            domain,
            "Upload entity time to current state · "
            + (
                "All study-linked entities"
                if population == POPULATIONS[0]
                else "Aged-order entities"
            ),
            subtitle,
        )
        chart.save(output_path(charts / f"{population}.png"), scale_factor=2)
        write_text(
            tables / f"{population}-statistics.md",
            f"# {population} statistics\n\n"
            + note
            + markdown_table(stats)
            + "\n",
        )
    aged = exports["aged-order-entities"]
    exports["audit"] = audit
    if (
        not set(aged.upload_id).issubset(set(entities.upload_id))
        or entities.upload_id.duplicated().any()
    ):
        raise ValueError("population reconciliation failed")
    for name, data in exports.items():
        data.to_parquet(directory / f"{name}.parquet", index=False)
    write_text(
        tables / "summary.md",
        "# REFNUM 51: upload entities\n\n"
        + note
        + markdown_table(audit)
        + "\n\n"
        "## Entity preview (first 25; complete populations in data/)\n\n"
        + markdown_table(entities.head(25))
        + "\n",
    )
    write_text(
        tables / "audit.md",
        "# Source audit\n\n" + note + markdown_table(audit) + "\n",
    )
    write_text(
        directory / "analysis.json",
        json.dumps(
            dict(
                metadata,
                version=VERSION,
                populations=POPULATIONS,
                shared_state_order=states,
                shared_hours_domain=domain,
                symlog_constant_hours=1 / 3600,
                generated_at_utc=datetime.now(UTC).isoformat(),
                exports={
                    name + ".parquet": digest(directory / f"{name}.parquet")
                    for name in exports
                },
            ),
            indent=2,
        )
        + "\n",
    )
    return audit


def load_source(params, sql, cached):
    identity = {
        "version": VERSION,
        "parameters": params,
        "populations": POPULATIONS,
        "sql_sha256": hashlib.sha256(sql.encode()).hexdigest(),
        "implementation_sha256": digest(Path(__file__)),
    }
    key = hashlib.sha256(
        json.dumps(identity, sort_keys=True).encode()
    ).hexdigest()[:16]
    period = (
        f"{params['start_date']}_{params['end_date']}_uploads-"
        f"{params['upload_start_date']}_{params['upload_end_date']}_"
        f"asof-{params['as_of_date']}_{key}"
    )
    directory = artifact_path(ROOT / "data" / NAME / period)
    parquet, manifest = directory / "source.parquet", directory / "source.json"
    if cached:
        if not manifest.exists():
            # This one extraction historically keyed its cache on presentation
            # code as well as SQL. Accept only recorded pre-move identities;
            # query, parameters, source bytes and validation still must match.
            original = source_ownership()["original_sha256"][
                (
                    "src/python/create_cmpu_upload_entity_state_"
                    "change_distributions.py"
                )
            ]
            compatible = (
                source_ownership()
                .get("cache_compatible_implementations", {})
                .get(Path(__file__).stem, [])
            )
            for previous_hash in [*compatible, original]:
                previous_identity = dict(
                    identity, implementation_sha256=previous_hash
                )
                previous_key = hashlib.sha256(
                    json.dumps(previous_identity, sort_keys=True).encode()
                ).hexdigest()[:16]
                previous_period = period.rsplit("_", 1)[0] + "_" + previous_key
                previous_directory = artifact_path(
                    ROOT / "data" / NAME / previous_period
                )
                if (previous_directory / "source.json").exists():
                    identity = previous_identity
                    directory, period = previous_directory, previous_period
                    parquet, manifest = (
                        directory / "source.parquet",
                        directory / "source.json",
                    )
                    break
        metadata = json.loads(manifest.read_text())
        if (
            metadata.get("identity") != json.loads(json.dumps(identity))
            or metadata.get("sql") != sql
            or metadata.get("parquet_sha256") != digest(parquet)
        ):
            raise ValueError(
                "cached SQL, dates, populations or source fingerprint "
                "differs; rerun fresh"
            )
        frame = pd.read_parquet(parquet)
        validate(frame, params)
    else:
        directory.mkdir(parents=True, exist_ok=True)
        query_dir = artifact_path(ROOT / "src/autogenerated" / NAME / period)
        query_dir.mkdir(parents=True, exist_ok=True)
        query = query_dir / "extract.sql"
        write_text(query, sql + "\n")
        manifest.unlink(missing_ok=True)
        subprocess.run(
            [
                sys.executable,
                str(RUNNER),
                str(query),
                "--output-parquet",
                str(parquet.relative_to(ROOT)),
                "--sql-log-dir",
                str((query_dir / "sql-history").relative_to(ROOT)),
            ],
            cwd=ROOT,
            check=True,
        )
        frame = pd.read_parquet(parquet)
        validate(frame, params)
        metadata = {
            "identity": identity,
            "parameters": params,
            "sql": sql,
            "parquet_sha256": digest(parquet),
            "extracted_at_utc": datetime.now(UTC).isoformat(),
        }
        write_text(manifest, json.dumps(metadata, indent=2) + "\n")
    return frame, metadata, directory, period


@click.command()
@click.option("--start-date", default="2026-08-15", show_default=True)
@click.option(
    "--end-date",
    default="2026-10-15",
    show_default=True,
    help="Exclusive prescription end; uploads extend 11 days.",
)
@click.option("--upload-start-date", default="2026-08-01", show_default=True)
@click.option(
    "--as-of-date",
    default="2026-10-27",
    show_default=True,
    help="Inclusive aged cancellation cutoff at 00:00 UTC.",
)
@click.option("--cached", is_flag=True)
@click.option("--print-sql", is_flag=True)
def main(
    start_date, end_date, upload_start_date, as_of_date, cached, print_sql
):
    try:
        params = parameters(
            start_date, end_date, upload_start_date, as_of_date
        )
        sql = render_sql(start_date, end_date, upload_start_date, as_of_date)
        if print_sql:
            click.echo(sql)
            return
        frame, metadata, directory, _period = load_source(params, sql, cached)
        dated = (
            f"{start_date}_{date.fromisoformat(end_date) - timedelta(days=1)}"
        )
        charts = artifact_path(ROOT / "outputs/charts" / dated / NAME)
        tables = artifact_path(ROOT / "outputs/tables" / dated / NAME)
        audit = write_outputs(frame, metadata, directory, charts, tables)
        click.echo(audit.to_string(index=False))
        click.echo(
            f"Charts: {charts}\nTables: {tables}\nComplete data: {directory}"
        )
    except (
        ValueError,
        OSError,
        KeyError,
        subprocess.CalledProcessError,
    ) as error:
        raise click.ClickException(str(error)) from error


if __name__ == "__main__":
    main()

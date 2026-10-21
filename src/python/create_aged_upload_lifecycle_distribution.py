"""Stack the existing aged-order upload cohort by latest prescription state."""

from datetime import date, datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

import altair as alt
import click
from jinja2 import Environment, StrictUndefined
import numpy as np
import pandas as pd

from src.python.create_vdam_upload_distribution import ROOT, RUNNER, histogram, render_sql, summarize

TEMPLATE = ROOT / "src/sql/aged_upload_lifecycle_states.sql"
STEM = "distribution-aged-orders-by-lifecycle-state"
UNMATCHED = "[Unmatched prescription]"
MISSING = "[Missing lifecycle state]"
COLORS = {
    "CUSTOMER CANCELED": "#4E79A7", "SYSTEM_CLOSED": "#79706E",
    "VET APPROVED": "#59A14F", "VET_REVIEW": "#F28E2B",
    "VET APPROVED - CLOSED": "#B07AA1", "DENIED": "#E15759",
    UNMATCHED: "#BAB0AC", MISSING: "#D7D7D7",
}
EXTRA_COLORS = ("#76B7B2", "#EDC948", "#FF9DA7", "#9C755F")


def load_cohort(directory: Path, start: str, end: str):
    expected_sql = render_sql(start, end)
    prerequisite = f"make create-vdam-upload-distribution START_DATE={start} END_DATE={end}"
    if not (directory / "uploads.parquet").exists() or not (directory / "source.json").exists():
        raise ValueError(f"upload cache is missing; first run: {prerequisite}")
    source = json.loads((directory / "source.json").read_text())
    if (source.get("sql") != expected_sql or source.get("start_date") != start
            or source.get("end_date_exclusive") != end or not source.get("extracted_at_utc")):
        raise ValueError(f"upload cache provenance differs from the requested cohort; inspect it before running: {prerequisite}")
    selected, _ = summarize(pd.read_parquet(directory / "uploads.parquet"))
    bins = histogram(selected.elapsed_hours)
    aged = selected.loc[selected.cancel_group.eq("Aged orders")].copy()
    # Include selected observations and global bin edges; unrelated row ordering
    # in the Parquet file must not change the analysis identity.
    identity = {
        "cohort": aged.sort_values("rx_id")[["rx_id", "upload_id", "order_id", "elapsed_hours"]].to_json(orient="records", double_precision=15),
        "bins": bins[["lower_hours", "upper_hours"]].to_json(orient="records", double_precision=15),
        "start_date": start, "end_date_exclusive": end,
    }
    fingerprint = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
    return aged, bins, fingerprint, source


def state_sql(rx_ids: pd.Series) -> str:
    identifiers = sorted(set(rx_ids))
    if any(not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", value) for value in identifiers):
        raise ValueError("unexpected prescription ID format")
    return Environment(undefined=StrictUndefined).from_string(TEMPLATE.read_text()).render(
        rx_ids=", ".join(f"'{value}'" for value in identifiers)
    ).strip()


def attach_states(aged: pd.DataFrame, states: pd.DataFrame) -> pd.DataFrame:
    states = states.rename(columns=str.lower)
    if states.rx_id.isna().any() or states.rx_id.duplicated().any():
        raise ValueError("lifecycle source contains null or duplicate RX_ID values; inspect before plotting")
    if not set(states.rx_id).issubset(set(aged.rx_id)):
        raise ValueError("lifecycle extract contains prescriptions outside the aged cohort")
    merged = aged.merge(states[["rx_id", "rx_lifecycle_state"]], how="left", on="rx_id", validate="one_to_one", indicator=True)
    merged["lifecycle_state"] = merged.rx_lifecycle_state.astype("string").fillna(MISSING)
    merged.loc[merged["_merge"].eq("left_only"), "lifecycle_state"] = UNMATCHED
    return merged.drop(columns="_merge")


def state_histograms(merged: pd.DataFrame, bins: pd.DataFrame) -> pd.DataFrame:
    if merged.empty:
        return pd.DataFrame(columns=[*bins.columns, "lifecycle_state"])
    if bins.empty:
        raise ValueError("nonempty aged cohort has no shared bin boundaries")
    edges = np.append(bins.lower_hours.to_numpy(), bins.upper_hours.iloc[-1])
    frames = []
    for state in sorted(merged.lifecycle_state.unique()):
        frame = histogram(merged.loc[merged.lifecycle_state.eq(state), "elapsed_hours"], edges)
        frame["lifecycle_state"] = state
        frames.append(frame)
    result = pd.concat(frames, ignore_index=True)
    expected = histogram(merged.elapsed_hours, edges).prescriptions.to_numpy()
    actual = result.groupby(["lower_hours", "upper_hours"]).prescriptions.sum().to_numpy()
    if not np.array_equal(actual, expected) or int(actual.sum()) != len(merged):
        raise ValueError("stacked counts do not reconcile to the aged cohort")
    return result


def write_outputs(merged: pd.DataFrame, bins: pd.DataFrame, metadata: dict,
                  chart_dir: Path, table_dir: Path) -> None:
    stacked = state_histograms(merged, bins)
    totals = merged.lifecycle_state.value_counts().rename_axis("state").reset_index(name="prescriptions")
    totals = totals.sort_values(["prescriptions", "state"], ascending=[False, True])
    period = f"{metadata['start_date']} through {date.fromisoformat(metadata['end_date_exclusive']) - timedelta(days=1)} UTC"
    lines = ["# Aged-order upload distribution by latest lifecycle state", "", f"Upload dates: {period}.",
             f"Frozen upload extract: {metadata['upload_extracted_at_utc']}.",
             f"Lifecycle states extracted: {metadata['extracted_at_utc']}.",
             f"Cohort fingerprint: `{metadata['cohort_fingerprint']}`.", "",
             f"{len(merged):,} distinct prescriptions from the existing aged-order cohort. Each prescription uses its earliest qualifying order-linked upload, selected before filtering to Aged Order.",
             "Latest state means RX_LIFECYCLE_STATE at extraction time, not the state at upload or cancellation and not necessarily a terminal state.",
             "Same 50 bin boundaries as the existing aged-orders figure; signed durations and outliers are retained. Stacks show counts, not normalized percentages.",
             "Source: EDLDB.BT_HCA_HCDM.RXP_PRESCRIPTIONS, left-joined by individual RX_ID. Unmatched prescriptions and matched prescriptions with null state remain separate.", "",
             "| Lifecycle state | Prescriptions | Percent of aged cohort |", "| --- | ---: | ---: |"]
    def label(value):
        return str(value).replace("|", "\\|").replace("\n", " ")
    for row in totals.itertuples(index=False):
        lines.append(f"| {label(row.state)} | {row.prescriptions:,} | {row.prescriptions / len(merged) * 100:.6f}% |")
    lines.extend(["", "Bins include their lower bound and exclude their upper bound; the final bin also includes its upper bound.",
                  "", "| Lower hours | Upper hours | Lifecycle state | Prescriptions |", "| ---: | ---: | --- | ---: |"])
    for row in stacked.itertuples(index=False):
        lines.append(f"| {row.lower_hours:.9f} | {row.upper_hours:.9f} | {label(row.lifecycle_state)} | {row.prescriptions:,} |")
    chart_dir.mkdir(parents=True, exist_ok=True)
    table_dir.mkdir(parents=True, exist_ok=True)
    png = chart_dir / f"{STEM}.png"
    if merged.empty:
        png.unlink(missing_ok=True)
        lines.extend(["", "No aged-order prescriptions; no chart generated."])
    else:
        states = totals.state.tolist()
        extras = sorted(set(states) - COLORS.keys())
        colors = {**COLORS, **{state: EXTRA_COLORS[i % len(EXTRA_COLORS)] for i, state in enumerate(extras)}}
        stacked["stack_order"] = stacked.lifecycle_state.map({state: i for i, state in enumerate(states)})
        chart = alt.Chart(stacked).mark_bar(binSpacing=0).encode(
            x=alt.X("lower_hours:Q", bin="binned", title="Hours from order placement to upload", scale=alt.Scale(zero=False)),
            x2="upper_hours:Q",
            y=alt.Y("prescriptions:Q", stack="zero", title="Number of prescriptions", scale=alt.Scale(zero=True)),
            color=alt.Color("lifecycle_state:N", title="Latest lifecycle state", sort=states,
                            scale=alt.Scale(domain=states, range=[colors[state] for state in states]),
                            legend=alt.Legend(orient="bottom", columns=3, labelLimit=280)),
            order=alt.Order("stack_order:Q", sort="ascending"),
            tooltip=["lifecycle_state:N", "prescriptions:Q", alt.Tooltip("lower_hours:Q", format=".2f"), alt.Tooltip("upper_hours:Q", format=".2f")],
        ).properties(width=960, height=440, padding=24, background="transparent", title=alt.Title(
            "Aged-order prescription upload delay by latest lifecycle state", subtitle=[
                period, f"{len(merged):,} prescriptions · 50 shared bins · all signed durations retained",
                f"Lifecycle snapshot: {metadata['extracted_at_utc']}",
            ],
        )).configure_axis(labelFontSize=12, titleFontSize=14, gridColor="#DDE2E7").configure_legend(labelFontSize=12, titleFontSize=13).configure_view(stroke=None)
        chart.save(png, scale_factor=2)
    (table_dir / f"{STEM}.md").write_text("\n".join(lines) + "\n")
    click.echo(totals.to_string(index=False) if len(totals) else "No aged-order prescriptions.")


def validate_state_cache(metadata: dict, fingerprint: str, sql: str) -> None:
    if metadata.get("cohort_fingerprint") != fingerprint or metadata.get("sql") != sql or not metadata.get("extracted_at_utc"):
        raise ValueError("lifecycle cache does not match this cohort/query; run without CACHED=1 to refresh states")


@click.command()
@click.option("--start-date", required=True)
@click.option("--end-date", required=True, help="Exclusive UTC upload date.")
@click.option("--print-sql", is_flag=True, help="Read the upload cache and print the state query only.")
@click.option("--cached", is_flag=True, help="Render saved lifecycle states without contacting Snowflake.")
def main(start_date: str, end_date: str, print_sql: bool, cached: bool) -> None:
    try:
        start_date, end_date = date.fromisoformat(start_date).isoformat(), date.fromisoformat(end_date).isoformat()
        run_name = f"{start_date}_{end_date}"
        base = ROOT / "data/vdam-upload-distribution" / run_name
        aged, bins, fingerprint, source = load_cohort(base, start_date, end_date)
        sql = state_sql(aged.rx_id)
        if print_sql:
            click.echo(sql)
            return
        directory = base / "aged-lifecycle"
        parquet, manifest = directory / "states.parquet", directory / "source.json"
        if cached:
            if not parquet.exists() or not manifest.exists():
                raise ValueError("lifecycle cache is missing; run without CACHED=1 first")
            metadata = json.loads(manifest.read_text())
            validate_state_cache(metadata, fingerprint, sql)
            states = pd.read_parquet(parquet)
        else:
            directory.mkdir(parents=True, exist_ok=True)
            query = directory / "source.sql"
            query.write_text(sql + "\n")
            manifest.unlink(missing_ok=True)
            if aged.empty:
                states = pd.DataFrame(columns=["rx_id", "rx_lifecycle_state"])
                states.to_parquet(parquet, index=False)
            else:
                subprocess.run([sys.executable, str(RUNNER), str(query), "--output-parquet", str(parquet.relative_to(ROOT)),
                                "--sql-log-dir", str((directory / "sql-history").relative_to(ROOT))], cwd=ROOT, check=True)
                states = pd.read_parquet(parquet)
            metadata = {"sql": sql, "cohort_fingerprint": fingerprint, "cohort_size": len(aged),
                        "start_date": start_date, "end_date_exclusive": end_date,
                        "upload_extracted_at_utc": source["extracted_at_utc"],
                        "extracted_at_utc": datetime.now(timezone.utc).isoformat()}
            attach_states(aged, states)  # Validate source grain before blessing the cache.
            manifest.write_text(json.dumps(metadata, indent=2) + "\n")
        merged = attach_states(aged, states)
        chart_dir = ROOT / "outputs/charts/vdam-upload-distribution" / run_name
        table_dir = ROOT / "outputs/tables/vdam-upload-distribution" / run_name
        write_outputs(merged, bins, metadata, chart_dir, table_dir)
        click.echo(f"Table: {(table_dir / (STEM + '.md')).relative_to(ROOT)}")
        if len(merged):
            click.echo(f"Chart: {(chart_dir / (STEM + '.png')).relative_to(ROOT)}")
    except (ValueError, OSError, KeyError, subprocess.CalledProcessError) as error:
        raise click.ClickException(str(error)) from error


if __name__ == "__main__":
    main()

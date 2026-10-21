"""Plot the first qualifying order-linked upload for each distinct prescription."""

from datetime import date, timedelta, datetime, timezone
import json
from pathlib import Path
import subprocess
import sys

import altair as alt
import click
from jinja2 import Environment, StrictUndefined
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
SQL_TEMPLATE = ROOT / "src/sql/vdam_upload_distribution.sql"
RUNNER = ROOT / ".agents/skills/rxp-sql/scripts/run_snowflake_query.py"
STATUSES = (
    "missing_prescription_id",
    "missing_order_id", "invalid_order_id", "unmatched_order",
    "missing_order_timestamp", "matched",
)
CANCEL_GROUPS = ("Not cancelled", "Aged orders", "Customer initiated", "Customer requested", "Other")
CANCEL_REASON_MAP = {
    "aged order": "Aged orders",
    "customer initiated cancellation": "Customer initiated",
    "customer request": "Customer requested",
}


def cancellation_groups(reasons: pd.Series) -> pd.Series:
    groups = reasons.astype("string").str.strip().str.lower().map(CANCEL_REASON_MAP).fillna("Other")
    return groups.mask(reasons.isna(), "Not cancelled")


def render_sql(start_date: str, end_date: str) -> str:
    start, end = date.fromisoformat(start_date), date.fromisoformat(end_date)
    if start >= end:
        raise ValueError("start date must be before exclusive end date")
    return Environment(undefined=StrictUndefined).from_string(
        SQL_TEMPLATE.read_text()
    ).render(start_date=start.isoformat(), end_date=end.isoformat())


def summarize(frame: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, int]]:
    frame = frame.rename(columns=str.lower)
    if frame.upload_id.isna().any() or frame.duplicated(["upload_id", "rx_id"]).any():
        raise ValueError("upload/prescription pairs must be unique with non-null upload IDs")
    identifiers = frame.rx_id.dropna().astype(str)
    if not identifiers.str.fullmatch(r"[A-Za-z0-9_-]+").all():
        raise ValueError("unexpected prescription ID format; inspect the extract")
    if not frame.row_status.isin(STATUSES).all():
        raise ValueError("unexpected row status or duplicate order rows; inspect the extract")
    matched = frame[frame.row_status.eq("matched")]
    if matched.rx_id.isna().any() or matched.order_id.isna().any() or matched.uploaded_at_utc.isna().any():
        raise ValueError("matched prescriptions must have IDs, order IDs, and upload timestamps")
    selected = matched.sort_values(["uploaded_at_utc", "upload_id", "order_id"]).drop_duplicates("rx_id").copy()
    selected["cancel_group"] = cancellation_groups(selected.order_cancel_reason)
    selected["elapsed_hours"] = pd.to_numeric(selected.elapsed_hours)
    if not np.isfinite(selected.elapsed_hours.to_numpy(dtype=float)).all():
        raise ValueError("eligible prescriptions must have finite durations")
    counts = {status: int(frame.row_status.eq(status).sum()) for status in STATUSES}
    counts.update(
        qualifying_uploads=int(frame.upload_id.nunique()),
        prescription_upload_rows=len(frame),
        repeat_matched_prescription_uploads=len(matched) - len(selected),
        eligible_prescriptions=len(selected),
        prescriptions_linked_to_multiple_orders=int((matched.groupby("rx_id").order_id.nunique() > 1).sum()),
        negative_prescriptions=int(selected.elapsed_hours.lt(0).sum()),
    )
    return selected, counts


def histogram(values: pd.Series, edges: np.ndarray | None = None) -> pd.DataFrame:
    values = values.to_numpy(dtype=float)
    if not len(values) and edges is None:
        return pd.DataFrame(columns=["lower_hours", "upper_hours", "prescriptions", "percent"])
    if edges is None:
        low, high = float(values.min()), float(values.max())
        if low == high:
            low, high = low - 0.5, high + 0.5
        edges = np.linspace(low, high, 51)
    counts, edges = np.histogram(values, bins=edges)
    return pd.DataFrame({
        "lower_hours": edges[:-1], "upper_hours": edges[1:],
        "prescriptions": counts, "percent": counts / len(values) * 100 if len(values) else np.zeros(len(counts)),
    })


def cancellation_histograms(selected: pd.DataFrame, bins: pd.DataFrame) -> pd.DataFrame:
    if bins.empty:
        return pd.DataFrame(columns=[*bins.columns, "cancel_group", "panel"])
    edges = np.append(bins.lower_hours.to_numpy(), bins.upper_hours.iloc[-1])
    frames = []
    for group in CANCEL_GROUPS:
        values = selected.loc[selected.cancel_group.eq(group), "elapsed_hours"]
        frame = histogram(values, edges)
        frame["cancel_group"] = group
        frame["panel"] = f"{group} · {len(values):,} prescriptions"
        frames.append(frame)
    return pd.concat(frames, ignore_index=True)


def write_cancellation_outputs(selected: pd.DataFrame, bins: pd.DataFrame, period: str,
                               chart_dir: Path, table_dir: Path) -> None:
    grouped = cancellation_histograms(selected, bins)
    lines = [
        "# Upload delay by order cancellation reason", "", f"Upload dates: {period}.", "",
        "Same distinct-prescription cohort and first qualifying matched upload as distribution.md.",
        "Cancellation reason comes from the order selected for that prescription, as recorded at extraction time; it is not a historical status at upload time.",
        "NULL → Not cancelled; Aged Order → Aged orders; Customer Initiated Cancellation → Customer initiated; Customer Request → Customer requested; all other non-null values → Other. Matching ignores case and outer whitespace.",
        "", "All five panels use the same 50 time bins and retain negative durations and outliers. Count scales differ by panel.",
        "", "| Group | Prescriptions | Share of cohort |", "| --- | ---: | ---: |",
    ]
    for group in CANCEL_GROUPS:
        count = int(selected.cancel_group.eq(group).sum())
        share = count / len(selected) * 100 if len(selected) else 0
        lines.append(f"| {group} | {count:,} | {share:.4f}% |")
    lines.extend(["", "Percentages below use each group's prescription count as the denominator; empty groups have zero counts and percentages.",
                  "Bin intervals include the lower bound and exclude the upper bound, except the last interval includes the maximum.",
                  "", "| Group | Lower hours | Upper hours | Prescriptions | Percent within group |",
                  "| --- | ---: | ---: | ---: | ---: |"])
    lines.extend(
        f"| {row.cancel_group} | {row.lower_hours:.9f} | {row.upper_hours:.9f} | {row.prescriptions:,} | {row.percent:.6f}% |"
        for row in grouped.itertuples(index=False)
    )
    png = chart_dir / "distribution-by-cancel-reason.png"
    if grouped.empty:
        png.unlink(missing_ok=True)
        for group in CANCEL_GROUPS:
            (chart_dir / f"distribution-{group.lower().replace(' ', '-')}.png").unlink(missing_ok=True)
        lines.extend(["", "No eligible observations; no chart generated."])
    else:
        base = alt.Chart(grouped).mark_bar(color="#326A99", binSpacing=0).encode(
            x=alt.X("lower_hours:Q", bin="binned", title="Hours from order placement to upload",
                    scale=alt.Scale(zero=False), axis=alt.Axis(tickCount=7)),
            x2="upper_hours:Q",
            y=alt.Y("prescriptions:Q", title="Number of prescriptions", scale=alt.Scale(zero=True)),
            tooltip=["cancel_group:N", alt.Tooltip("lower_hours:Q", format=".2f"),
                     alt.Tooltip("upper_hours:Q", format=".2f"), "prescriptions:Q",
                     alt.Tooltip("percent:Q", title="% within group", format=".2f")],
        )
        chart = base.properties(width=440, height=210).facet(
            facet=alt.Facet("panel:N", sort=grouped.panel.drop_duplicates().tolist(),
                            title=None, header=alt.Header(labelFontSize=14, labelFontWeight="bold")),
            columns=2,
        ).resolve_scale(x="shared", y="independent").resolve_axis(x="independent").properties(
            background="transparent", spacing=32,
            title=alt.Title("Prescription upload delay by order cancellation reason", subtitle=[
                period, f"{len(selected):,} prescriptions · 50 shared bins · count scales differ by panel",
            ]),
        ).configure_axis(labelFontSize=12, titleFontSize=13, gridColor="#DDE2E7").configure_view(stroke=None)
        chart.save(png, scale_factor=2)
        for group in CANCEL_GROUPS:
            total = int(grouped.loc[grouped.cancel_group.eq(group), "prescriptions"].sum())
            individual = base.copy()
            individual.data = grouped.loc[grouped.cancel_group.eq(group)].copy()
            individual = individual.properties(
                width=960, height=440, background="transparent", padding=24,
                title=alt.Title(f"Prescription upload delay — {group}", subtitle=[
                    period, f"{total:,} prescriptions · 50 shared bins · all signed durations retained",
                ]),
            ).configure_axis(labelFontSize=12, titleFontSize=14, gridColor="#DDE2E7").configure_view(stroke=None)
            individual.save(chart_dir / f"distribution-{group.lower().replace(' ', '-')}.png", scale_factor=2)
    (table_dir / "distribution-by-cancel-reason.md").write_text("\n".join(lines) + "\n")


def write_outputs(frame: pd.DataFrame, start: str, end: str, chart_dir: Path, table_dir: Path) -> dict:
    selected, counts = summarize(frame)
    bins = histogram(selected.elapsed_hours)
    chart_dir.mkdir(parents=True, exist_ok=True)
    table_dir.mkdir(parents=True, exist_ok=True)
    period = f"{start} through {date.fromisoformat(end) - timedelta(days=1)} UTC"
    lines = [
        "# VDAM prescription-upload distribution", "", f"Upload dates: {period}.", "",
        "One observation per distinct prescription: earliest qualifying order-linked upload within this window.",
        "Both UPLOAD_TYPE and ASSOCIATED_RESOURCE_TYPE must be DIET_PRESCRIPTION; HAS_ASSOCIATED_RX and HAS_UPLOADED_FILE must be TRUE.",
        "Brace-delimited RX_ID lists are expanded. Repeated IDs within one upload are deduplicated; ASSOCIATED_RX_CNT is not used as a weight.",
        "If a prescription is linked to multiple orders, use the order on its earliest qualifying matched upload (ties broken by upload ID, then order ID).",
        "Order timestamps are interpreted as UTC based on observed offsets from the Eastern companion column; metadata does not explicitly establish the timezone.",
        "Negative durations and outliers are retained. Uploads without timestamps cannot be assigned to this date cohort.",
        "", "| Audit measure | Count |", "| --- | ---: |",
    ]
    lines.extend(f"| {key} | {value:,} |" for key, value in counts.items())
    lines.extend([
        "", "Prescription-upload rows = missing prescription IDs + missing/invalid order IDs + unmatched orders + missing order timestamps + matched rows.",
        "Matched rows = eligible prescriptions + repeat matched prescription uploads. Negative prescriptions are a subset of eligible prescriptions.",
        "", "Bins include their lower bound and exclude their upper bound, except the final bin includes both.",
        "Percentages use eligible prescriptions as the denominator.", "",
        "| Lower hours | Upper hours | Prescriptions | Percent |", "| ---: | ---: | ---: | ---: |",
    ])
    lines.extend(
        f"| {row.lower_hours:.9f} | {row.upper_hours:.9f} | {row.prescriptions:,} | {row.percent:.6f}% |"
        for row in bins.itertuples(index=False)
    )
    png = chart_dir / "distribution.png"
    if not len(selected):
        lines.extend(["", "No eligible observations; no chart generated."])
        png.unlink(missing_ok=True)
    else:
        chart = alt.Chart(bins).mark_bar(color="#326A99", binSpacing=0).encode(
            x=alt.X("lower_hours:Q", bin="binned", title="Hours from order placement to upload",
                    scale=alt.Scale(zero=False)),
            x2="upper_hours:Q",
            y=alt.Y("prescriptions:Q", title="Number of prescriptions", scale=alt.Scale(zero=True)),
            tooltip=[alt.Tooltip("lower_hours:Q", format=".2f"),
                     alt.Tooltip("upper_hours:Q", format=".2f"), "prescriptions:Q",
                     alt.Tooltip("percent:Q", format=".2f")],
        ).properties(
            width=960, height=440, background="transparent",
            title=alt.Title("Time to first VDAM prescription upload", subtitle=[
                period,
                f"{len(selected):,} prescriptions · 50 equal-width bins · all signed durations retained",
            ]),
        ).configure_axis(labelFontSize=12, titleFontSize=14, gridColor="#DDE2E7").configure_view(stroke=None)
        chart.save(png, scale_factor=2)
    (table_dir / "distribution.md").write_text("\n".join(lines) + "\n")
    write_cancellation_outputs(selected, bins, period, chart_dir, table_dir)
    return counts


@click.command()
@click.option("--start-date", required=True, help="Inclusive UTC upload date, YYYY-MM-DD.")
@click.option("--end-date", required=True, help="Exclusive UTC upload date, YYYY-MM-DD.")
@click.option("--print-sql", is_flag=True, help="Print the SQL without connecting or writing files.")
@click.option("--cached", is_flag=True, help="Render the previously extracted data for these dates.")
def main(start_date: str, end_date: str, print_sql: bool, cached: bool) -> None:
    try:
        sql = render_sql(start_date, end_date)
    except ValueError as error:
        raise click.UsageError(str(error)) from error
    if print_sql:
        click.echo(sql)
        return
    run_name = f"{start_date}_{end_date}"
    data_dir = ROOT / "data/vdam-upload-distribution" / run_name
    chart_dir = ROOT / "outputs/charts/vdam-upload-distribution" / run_name
    table_dir = ROOT / "outputs/tables/vdam-upload-distribution" / run_name
    parquet = data_dir / "uploads.parquet"
    manifest = data_dir / "source.json"
    if cached:
        if not parquet.exists() or not manifest.exists():
            raise click.ClickException("no complete cached extract for these dates; run without --cached first")
        if json.loads(manifest.read_text()).get("sql") != sql:
            raise click.ClickException("cached SQL differs from current SQL; refresh the extract")
    else:
        data_dir.mkdir(parents=True, exist_ok=True)
        query_file = data_dir / "source.sql"
        query_file.write_text(sql + "\n")
        # An interrupted refresh must never leave an old manifest blessing partial data.
        manifest.unlink(missing_ok=True)
        subprocess.run([
            sys.executable, str(RUNNER), str(query_file),
            "--output-parquet", str(parquet.relative_to(ROOT)),
            "--sql-log-dir", str(data_dir.relative_to(ROOT) / "sql-history"),
        ], cwd=ROOT, check=True)
        manifest.write_text(json.dumps({
            "sql": sql, "extracted_at_utc": datetime.now(timezone.utc).isoformat(),
            "start_date": start_date, "end_date_exclusive": end_date,
        }, indent=2) + "\n")
    try:
        counts = write_outputs(pd.read_parquet(parquet), start_date, end_date, chart_dir, table_dir)
    except ValueError as error:
        raise click.ClickException(str(error)) from error
    click.echo(json.dumps(counts, indent=2))
    click.echo(f"Tables: {table_dir.relative_to(ROOT)}")
    if counts["eligible_prescriptions"]:
        click.echo(f"Chart: {(chart_dir / 'distribution.png').relative_to(ROOT)}")
        click.echo(f"Breakdown: {(chart_dir / 'distribution-by-cancel-reason.png').relative_to(ROOT)}")


if __name__ == "__main__":
    main()

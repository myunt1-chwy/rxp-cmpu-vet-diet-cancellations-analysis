"""Prescription-level approval/channel/order/upload Sankey generator."""

import hashlib
import json
import subprocess
import sys
from datetime import UTC, date, datetime, timedelta

import click
import pandas as pd
from jinja2 import Environment, StrictUndefined

from shared.paths import artifact_path, canonical_sql_path
from shared.prescription_uploads import (
    date_parameters,
    period_name,
    prepare_prescription_uploads,
)
from shared.python.markdown_tables import (
    markdown_table,
    table_layout,
    write_text,
)
from shared.runtime import ROOT, RUNNER, digest
from shared.sankey import render_sankey

NAME = "cmpu-prescription-first-order-status"
TEMPLATE = canonical_sql_path("cmpu_prescription_first_order_status.sql")
REASONS = {
    "aged order": "Aged Order",
    "customer initiated cancellation": "Customer Initiated Cancellation",
    "customer request": "Customer Request",
}


def render_sql(start, end, upload_start=None):
    parameters = date_parameters(start, end, upload_start)
    return (
        Environment(undefined=StrictUndefined)
        .from_string(TEMPLATE.read_text())
        .render(**parameters)
    )


def summarize(frame):
    frame, audits = prepare_prescription_uploads(frame)
    status = (
        frame.order_status.astype("string")
        .str.strip()
        .str.upper()
        .replace("", pd.NA)
    )
    reason = (
        frame.order_cancel_reason.astype("string")
        .str.strip()
        .str.lower()
        .replace("", pd.NA)
    )
    frame["order_group"] = "Not canceled"
    canceled = status.eq("X").fillna(False)
    frame.loc[canceled, "order_group"] = (
        reason[canceled].map(REASONS).fillna("Other cancellation reason")
    )
    frame.loc[canceled & reason.isna(), "order_group"] = (
        "Canceled - missing reason"
    )
    frame.loc[status.isna(), "order_group"] = "Unknown order status"
    frame.loc[frame.order_source_rows.eq(0), "order_group"] = (
        "First order not found"
    )
    frame.loc[frame.first_order_id.isna(), "order_group"] = "No first order ID"
    frame["upload_group"] = frame.upload_count.gt(0).map(
        {True: "Has matching upload", False: "No matching upload"}
    )
    groups = (
        frame.groupby(["channel", "upload_group", "order_group"])
        .size()
        .reset_index(name="prescriptions")
    )
    groups["percent_of_cohort"] = (
        100 * groups.prescriptions / len(frame) if len(frame) else 0.0
    )
    if int(groups.prescriptions.sum()) != len(frame):
        raise ValueError("group counts do not conserve the cohort")
    return frame, groups, audits


def make_flows(groups):
    """Channel-specific middle nodes preserve the complete three-way split."""
    rows = []
    for (channel, upload), subset in groups.groupby(
        ["channel", "upload_group"], sort=True
    ):
        source, middle = f"Channel: {channel}", f"{channel} / {upload}"
        rows.append((1, source, middle, int(subset.prescriptions.sum())))
        rows.extend(
            (
                2,
                middle,
                f"First order: {row.order_group}",
                int(row.prescriptions),
            )
            for row in subset.itertuples(index=False)
            if row.prescriptions > 0
        )
    flows = pd.DataFrame(
        rows, columns=["transition", "source", "target", "prescriptions"]
    )
    total = int(groups.prescriptions.sum())
    flows["percent_of_cohort"] = (
        100 * flows.prescriptions / total if total else 0.0
    )
    if not flows.empty:
        if (
            flows.prescriptions.le(0).any()
            or not flows.groupby("transition")
            .prescriptions.sum()
            .eq(total)
            .all()
        ):
            raise ValueError("invalid Sankey transition totals")
        incoming = (
            flows.loc[flows.transition.eq(1)].set_index("target").prescriptions
        )
        outgoing = (
            flows.loc[flows.transition.eq(2)]
            .groupby("source")
            .prescriptions.sum()
        )
        if not incoming.sort_index().equals(outgoing.sort_index()):
            raise ValueError("unbalanced Sankey intermediate nodes")
    return flows


def write_outputs(frame, metadata, diagram_dir, table_dir, table_prefix=""):
    prescriptions, groups, audits = summarize(frame)
    upload_start = metadata.get("upload_start_date", metadata["start_date"])
    start, end, upload_start_time = map(
        pd.Timestamp,
        [metadata["start_date"], metadata["end_date_exclusive"], upload_start],
    )
    if (
        prescriptions.rx_creation_datetime.lt(start)
        | prescriptions.rx_creation_datetime.ge(end)
    ).any():
        raise ValueError(
            "prescription creation timestamp outside cohort window"
        )
    uploaded = prescriptions.first_upload_at_utc.dropna()
    if (uploaded.lt(upload_start_time) | uploaded.ge(end)).any():
        raise ValueError(
            "matched upload timestamp outside upload search window"
        )
    flows = make_flows(groups)
    diagram_dir.mkdir(parents=True, exist_ok=True)
    table_dir.mkdir(parents=True, exist_ok=True)
    source, png = diagram_dir / "sankey.mmd", diagram_dir / "sankey.png"
    note = (
        f"Prescription creation: {metadata['start_date']} inclusive to "
        f"{metadata['end_date_exclusive']} exclusive, UTC. "
        f"Upload search: {upload_start} inclusive to "
        f"{metadata['end_date_exclusive']} exclusive, UTC. "
        f"Extracted: {metadata['extracted_at_utc']}.\n\n"
        "Count each CMPU vet-diet prescription once. First order means "
        "FIRST_ORDER_ID only, "
        "regardless of placement date. Status/reason is the latest snapshot; "
        "X means canceled. "
        "No deletion or prescription-status filter is applied. Match "
        "DIET_PRESCRIPTION upload "
        "entities by expanded RX_ID and numeric CUSTOMER_ID, within the "
        "upload search window; file and "
        "association flags are not filters. Matching upload entity does not "
        "verify file presence. "
        "The Sankey shows approval channel, then upload presence, then "
        "first-order status/reason. "
        "It is a categorical breakdown, not a chronological sequence. Upload "
        "middle nodes retain "
        "approval-channel identity. Node and flow percentages use the full "
        "prescription cohort "
        "for the main diagram, and only CUSTOMER_UPLOAD prescriptions for the "
        "focused diagram. "
        "They are rounded to two decimals in node labels, not percentages of "
        "the parent node. "
        "Missing/invalid upload-key audits describe the entire upload "
        "window.\n\n"
    )
    for name, table in [
        ("distribution", groups),
        ("flows", flows),
        ("prescriptions", prescriptions),
        ("audit", pd.DataFrame(audits.items(), columns=["measure", "count"])),
    ]:
        write_text(
            table_dir / (table_prefix + f"{name}.md"),
            f"# {name.title()}\n\n" + note + markdown_table(table) + "\n",
        )
    data_dir = artifact_path(
        ROOT
        / "data"
        / NAME
        / period_name(
            metadata["start_date"],
            metadata["end_date_exclusive"],
            upload_start,
        )
    )
    prescriptions.to_parquet(data_dir / "prescriptions.parquet", index=False)
    last_day = (
        date.fromisoformat(metadata["end_date_exclusive"]) - timedelta(days=1)
    ).isoformat()
    period = f"{metadata['start_date']} through {last_day}"
    if upload_start != metadata["start_date"]:
        period = f"Rx: {period}; uploads: {upload_start} through {last_day}"
    title = (
        f"CMPU vet-diet prescriptions | All approval channels | {period} | "
        f"Denominator: {len(prescriptions):,}"
    )
    diagram_note = render_sankey(flows, source, png, title)
    focused = groups.loc[groups.channel.eq("CUSTOMER_UPLOAD")].copy()
    focused_total = int(focused.prescriptions.sum())
    focused["percent_of_cohort"] = (
        100 * focused.prescriptions / focused_total if focused_total else 0.0
    )
    focused_flows = make_flows(focused)
    focused_title = (
        f"CMPU vet-diet prescriptions | CUSTOMER_UPLOAD only | {period} | "
        f"Denominator: {focused_total:,}"
    )
    focused_note = render_sankey(
        focused_flows,
        diagram_dir / "sankey-customer-upload.mmd",
        diagram_dir / "sankey-customer-upload.png",
        focused_title,
    )
    for name, table in [
        ("customer-upload-distribution", focused),
        ("customer-upload-flows", focused_flows),
    ]:
        write_text(
            table_dir / (table_prefix + f"{name}.md"),
            f"# {name.title()}\n\n"
            + note
            + (
                "Approval channel CUSTOMER_UPLOAD only. Percentages use this "
                "channel as the denominator.\n\n"
            )
            + markdown_table(table)
            + "\n",
        )
    write_text(
        table_dir / (table_prefix + "customer-upload-summary.md"),
        "# CUSTOMER_UPLOAD first-order status\n\n"
        + note
        + f"Approval channel CUSTOMER_UPLOAD only: **{focused_total:,} "
        "prescriptions**. "
        "Percentages use this channel as the denominator.\n\n"
        + markdown_table(focused)
        + "\n\n"
        + focused_note
        + "\n",
    )
    write_text(
        table_dir / (table_prefix + "summary.md"),
        "# CMPU prescriptions: first order and uploads\n\n"
        + note
        + markdown_table(
            pd.DataFrame(audits.items(), columns=["measure", "count"])
        )
        + "\n\n"
        + markdown_table(groups)
        + "\n\n"
        + diagram_note
        + "\n",
    )
    write_text(
        diagram_dir / "README.md",
        "# CMPU first-order status\n\n"
        + note
        + (
            f"Full-diagram percentage denominator: **{len(prescriptions):,} "
            f"prescriptions**.\n\n"
        )
        + (
            "![Prescription Sankey](sankey.png)\n"
            if len(flows)
            else diagram_note + "\n"
        )
        + "\n## CUSTOMER_UPLOAD only\n\n"
        + (
            f"Focused-diagram percentage denominator: **{focused_total:,} "
            f"CUSTOMER_UPLOAD prescriptions**.\n\n"
        )
        + (
            "![CUSTOMER_UPLOAD Sankey](sankey-customer-upload.png)\n"
            if focused_total
            else focused_note + "\n"
        ),
    )
    return audits


@click.command()
@click.option("--start-date", default="2026-08-15", show_default=True)
@click.option(
    "--end-date",
    default="2026-10-15",
    show_default=True,
    help="Exclusive end date",
)
@click.option(
    "--upload-start-date",
    default="2026-08-01",
    show_default=True,
    help="Inclusive upload search start",
)
@click.option("--cached", is_flag=True)
@click.option("--print-sql", is_flag=True)
def main(start_date, end_date, upload_start_date, cached, print_sql):
    try:
        sql = render_sql(start_date, end_date, upload_start_date)
        if print_sql:
            click.echo(sql)
            return
        period = period_name(start_date, end_date, upload_start_date)
        directory = artifact_path(ROOT / "data" / NAME / period)
        parquet, manifest = (
            directory / "source.parquet",
            directory / "source.json",
        )
        if cached:
            metadata = json.loads(manifest.read_text())
            if (
                metadata.get("sql") != sql
                or metadata.get("start_date") != start_date
                or metadata.get("end_date_exclusive") != end_date
                or metadata.get("upload_start_date", start_date)
                != upload_start_date
                or metadata.get("parquet_sha256") != digest(parquet)
            ):
                raise ValueError(
                    "cached SQL, dates or extract fingerprint differs; "
                    "refresh extract"
                )
            frame = pd.read_parquet(parquet).rename(columns=str.lower)
        else:
            directory.mkdir(parents=True, exist_ok=True)
            query = directory / "source.sql"
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
                    str((directory / "sql-history").relative_to(ROOT)),
                ],
                cwd=ROOT,
                check=True,
            )
            frame = pd.read_parquet(parquet).rename(columns=str.lower)
            summarize(frame)
            metadata = {
                "sql": sql,
                "sql_sha256": hashlib.sha256(sql.encode()).hexdigest(),
                "parquet_sha256": digest(parquet),
                "start_date": start_date,
                "end_date_exclusive": end_date,
                "upload_start_date": upload_start_date,
                "extracted_at_utc": datetime.now(UTC).isoformat(),
                "source_extracted_at_session_time": (
                    frame.extracted_at_session_time.unique().tolist()
                ),
                "warehouse": frame.extraction_warehouse.unique().tolist(),
            }
            write_text(manifest, json.dumps(metadata, indent=2) + "\n")
        table_dir, table_prefix = table_layout(ROOT, NAME, period)
        audits = write_outputs(
            frame,
            metadata,
            artifact_path(ROOT / "outputs/diagrams" / NAME / period),
            table_dir,
            table_prefix=table_prefix,
        )
        click.echo(json.dumps(audits, indent=2))
    except (
        ValueError,
        OSError,
        KeyError,
        subprocess.CalledProcessError,
    ) as error:
        raise click.ClickException(str(error)) from error


if __name__ == "__main__":
    main()

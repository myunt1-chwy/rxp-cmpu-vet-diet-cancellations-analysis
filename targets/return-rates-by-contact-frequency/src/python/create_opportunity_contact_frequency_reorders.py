"""Same-pet/part reorders segmented by customer contact-day frequency."""

import hashlib
import json
from datetime import UTC, date, datetime, timedelta

import click
import duckdb
import pandas as pd

from shared.paths import artifact_path
from shared.python import contact_analysis as contacts
from shared.python import create_opportunity_order_cancellation_summary as base
from shared.python import reorder_analysis as reorders
from shared.python.markdown_tables import markdown_table, write_text
from shared.sql_templates import module_sql

ROOT = base.ROOT


def queries(start, end, as_of, days):
    return {
        "contacts": contacts.render_sql(start, end),
        "reorders": reorders.render_sql(start, end, as_of, days),
    }


def analyze(
    contact_source, reorder_source, start, end, as_of, days, handled_only=False
):
    cf, contact_audit, _ = contacts.analyze(
        contact_source, start, end, handled_only
    )
    raw = reorder_source.rename(columns=str.lower).copy()
    frozen = (
        raw[reorders.KEYS + ["original_customer_id", "original_cancel_utc"]]
        .drop_duplicates()
        .rename(
            columns={
                "original_customer_id": "customer_id",
                "original_cancel_utc": "cancelled_at_utc",
            }
        )
    )
    for col in reorders.KEYS + ["customer_id"]:
        frozen[col] = frozen[col].map(base.identifier)
    frozen.cancelled_at_utc = pd.to_datetime(
        frozen.cancelled_at_utc, utc=True, format="mixed"
    )
    if frozen.duplicated(reorders.KEYS).any():
        raise ValueError("conflicting aged membership")
    if not frozen.cancelled_at_utc.between(
        pd.Timestamp(start, tz="UTC"),
        pd.Timestamp(end, tz="UTC"),
        inclusive="left",
    ).all():
        raise ValueError("cancellations outside requested dates")
    cols = ["order_id", "customer_id", "cancelled_at_utc"]
    cohort = frozen.rename(columns={"original_order_id": "order_id"})[
        cols
    ].drop_duplicates()
    cohort.cancelled_at_utc = cohort.cancelled_at_utc.astype(
        "datetime64[ns, UTC]"
    )
    pd.testing.assert_frame_equal(
        cohort.sort_values(cols).reset_index(drop=True),
        cf["aged_orders"][cols].sort_values(cols).reset_index(drop=True),
        check_dtype=False,
        obj="contact and reorder aged cohorts",
    )
    rf, _ = reorders.analyze(raw, frozen, days, as_of)
    matching = rf["matches"].loc[rf["matches"].qualifying_non_cancelled].copy()
    per_customer = (
        cf["customer_contact_days"]
        .merge(
            matching.groupby("original_customer_id")
            .reorder_order_id.nunique()
            .rename("reorder_orders"),
            left_on="customer_id",
            right_index=True,
            how="left",
            validate="one_to_one",
        )
        .fillna({"reorder_orders": 0})
    )
    per_customer.reorder_orders = per_customer.reorder_orders.astype("int64")
    per_customer["reordered"] = per_customer.reorder_orders.gt(0)
    rows = []
    for frequency in [1, 2]:
        segment = per_customer.loc[per_customer.days_contacted.eq(frequency)]
        count = int(segment.reordered.sum())
        denominator = len(segment)
        rows.append(
            {
                "days_contacted": frequency,
                "segment_customers": denominator,
                "reordered_customers": count,
                "reordered_percentage": 100 * count / denominator
                if denominator
                else None,
            }
        )
    summary = pd.DataFrame(rows)
    verify = module_sql(
        __file__,
        "create_opportunity_contact_frequency_reorders-query-1.sql.j2",
        handled_only=handled_only,
    )
    detail = cf["contact_details"].copy()
    detail["contact_time_sql"] = detail.contact_at_utc.dt.tz_localize(None)
    detail["cancellation_time_sql"] = detail.cancelled_at_utc.dt.tz_localize(
        None
    )
    with duckdb.connect() as c:
        c.register("contact_details", detail)
        c.register("aged_orders", cf["aged_orders"])
        c.register(
            "matches",
            rf["matches"][
                ["original_customer_id", "qualifying_non_cancelled"]
            ],
        )
        expected = c.execute(verify).df()
    pd.testing.assert_frame_equal(
        summary.drop(columns="reordered_percentage"),
        expected,
        check_dtype=False,
    )
    matches = matching.merge(
        per_customer[["customer_id", "days_contacted"]],
        left_on="original_customer_id",
        right_on="customer_id",
        validate="many_to_one",
    )
    return (
        {
            "summary": summary,
            "customer_results": per_customer,
            "reorder_associations": matches,
        },
        {
            "contact_audit": contact_audit,
            "reorder_audit": rf["summary"]
            .set_index("measure")["count"]
            .to_dict(),
            "independent_verification": (
                "DuckDB independently matches both segment denominators and "
                "returning-customer counts"
            ),
        },
        verify,
    )


def latex_table(summary, start, end, as_of, days, handled_only):
    first = date.fromisoformat(start).strftime("%B %-d, %Y")
    last = (date.fromisoformat(end) - timedelta(days=1)).strftime("%B %-d, %Y")
    rows = []
    for r in summary.itertuples():
        percentage = (
            "N/A"
            if pd.isna(r.reordered_percentage)
            else f"{r.reordered_percentage:.2f}" + r"\%"
        )
        rows.append(
            (
                f"{r.days_contacted} & {r.segment_customers:,} & "
                f"{r.reordered_customers:,} & {percentage}"
            )
            + r" \\"
        )
    handled = (
        r"Require \texttt{HANDLED\_FLAG=TRUE}."
        if handled_only
        else "Include handled, unhandled and unknown-handled inbound attempts."
    )
    return (
        (
            "\n\\subsubsection{Does more frequent contact imply "
            "higher propensity to re-order successfully for the "
            "same pet and part number in 14 "
            "days?}\nTable~\\ref{tab:contact-frequency-same-pet-"
            "part-reorders} applies the contact-day\nfrequency "
            "segments in Table~\\ref{tab:aged-customer-contact-day-"
            "frequency}\nto same-pet, same-product "
            "reorders.\n\n\\begin{table}[!htbp]\n\\centering\n\\capt"
            "ion{Same-pet, same-product-part-number reorders within "
        )
        + str(days)
        + (
            " days after aged cancellation, by customer contact-day "
            "frequency. Original CMPU vet-diet \\texttt{CUSTOMER\\_"
            "UPLOAD} orders were cancelled from "
        )
        + first
        + " through "
        + last
        + (
            ", inclusive, UTC.}\n\\label{tab:contact-frequency-same-"
            "pet-part-reorders}\n\\begin{tabular}{@{}rrrr@{}}\n\\top"
            "rule\nDays contacted & Segment customers & Customers "
            "reordered & Segment reordered (\\%) \\\\\n\\midrule\n"
        )
        + "\n".join(rows)
        + r"""
\bottomrule
\end{tabular}

\begin{minipage}{\linewidth}
\footnotesize
\textit{Notes:} Segments count distinct relative 24-hour contact-day bins from
$-13$ through $+3$, pooled across each customer's qualifying aged orders.
Multiple contacts on the same relative day count as one day. Match inbound
contacts to the original aged order and its customer, across all categories.
"""
        + handled
        + (
            " Reorders must match the customer, non-null "
            "\\texttt{PET\\_ID} and nonblank\n\\texttt{PRODUCT\\_"
            "PART\\_NUMBER}, on a different order placed strictly "
            "after\nits matched aged cancellation through "
        )
        + str(days)
        + r""" days inclusive. Apply the established
non-cancelled-order rules: exclude an entire reorder order if any line has
cancellation evidence or unknown status. Reorders may use any approval channel
or prescription source. Count each customer once in their segment if any
qualifying aged order has a matching reorder in its own follow-up window.
Percentages use all customers in the contact segment, including those missing
matching keys or without reorders; N/A denotes an empty segment. Contact-day
segments include post-cancellation contacts through day $+3$.
Observation cutoff: """
        + as_of
        + r""" 00:00 UTC.
\end{minipage}
\end{table}
"""
    )


def publish_latex(text):
    appendix = artifact_path(ROOT / "src/latex/appendix")
    appendix.mkdir(parents=True, exist_ok=True)
    write_text(appendix / "contact_frequency_reorders.tex", text)
    parent = appendix / "contact_analysis.tex"
    include = r"\input{appendix/contact_frequency_reorders}"
    body = (
        parent.read_text()
        if parent.exists()
        else r"\subsection{Contact Analysis}" + "\n"
    )
    if include not in body:
        write_text(parent, body.rstrip() + "\n\n" + include + "\n")


@click.command()
@click.option("--start-date", default="2026-05-01", show_default=True)
@click.option(
    "--end-date",
    default="2026-08-01",
    show_default=True,
    help="Exclusive UTC aged cancellation end.",
)
@click.option("--as-of-date", default="2026-10-28", show_default=True)
@click.option(
    "--followup-days",
    default=14,
    type=click.IntRange(min=1),
    show_default=True,
)
@click.option("--handled-only", is_flag=True)
@click.option("--write-latex", is_flag=True)
@click.option("--cached", is_flag=True)
@click.option(
    "--print-sql",
    is_flag=True,
    help="Print the two independently executable extraction queries.",
)
def main(
    start_date,
    end_date,
    as_of_date,
    followup_days,
    handled_only,
    write_latex,
    cached,
    print_sql,
):
    params = base.parameters(start_date, end_date)
    if date.fromisoformat(as_of_date) < date.fromisoformat(
        end_date
    ) + timedelta(days=max(followup_days, contacts.MAX_DAY + 1)):
        raise click.ClickException(
            "as-of must allow complete contact and reorder windows"
        )
    sql = queries(start_date, end_date, as_of_date, followup_days)
    if print_sql:
        for name, query in sql.items():
            click.echo(
                f"-- {name}.sql (execute separately)\n{query.rstrip()};\n"
            )
        return
    directory = artifact_path(
        ROOT
        / "data/opportunity/contact-frequency-reorders"
        / f"{start_date}_{end_date}_{followup_days}d_as-of-{as_of_date}"
    )
    directory.mkdir(parents=True, exist_ok=True)
    manifest = directory / "source.json"
    identity = dict(
        version=1,
        **params,
        as_of_date=as_of_date,
        followup_days=followup_days,
        contact_days=[contacts.MIN_DAY, contacts.MAX_DAY],
        sql_sha256={
            name: hashlib.sha256(query.encode()).hexdigest()
            for name, query in sql.items()
        },
    )
    if cached:
        meta = json.loads(manifest.read_text())
        if meta["identity"] != identity or any(
            meta["source_sha256"][n] != base.digest(directory / f"{n}.parquet")
            for n in sql
        ):
            raise click.ClickException(
                "cache fingerprint differs; rerun fresh"
            )
    else:
        manifest.unlink(missing_ok=True)
        engines = {}
        for name, query in sql.items():
            source_dir = directory / name
            source_dir.mkdir(exist_ok=True)
            write_text(source_dir / "query.sql", query + "\n")
            engines[name] = base.extract(
                source_dir / "query.sql",
                directory / f"{name}.parquet",
                source_dir,
            )
        meta = {
            "identity": identity,
            "source_sha256": {
                n: base.digest(directory / f"{n}.parquet") for n in sql
            },
            "extracted_at_utc": datetime.now(UTC).isoformat(),
            "engines": engines,
        }
    write_text(manifest, json.dumps(meta, indent=2) + "\n")
    frames, audit, verify = analyze(
        pd.read_parquet(directory / "contacts.parquet"),
        pd.read_parquet(directory / "reorders.parquet"),
        start_date,
        end_date,
        as_of_date,
        followup_days,
        handled_only,
    )
    mode = directory / ("handled-inbound" if handled_only else "all-inbound")
    mode.mkdir(exist_ok=True)
    for name, frame in frames.items():
        frame.to_parquet(
            mode / (name.replace("_", "-") + ".parquet"), index=False
        )
    write_text(mode / "verification.sql", verify + ";\n")
    write_text(
        mode / "analysis.json",
        json.dumps(
            {
                "source_sha256": meta["source_sha256"],
                "audit": audit,
                "exports": {
                    p.name: base.digest(p) for p in mode.glob("*.parquet")
                },
            },
            indent=2,
        )
        + "\n",
    )
    tables = artifact_path(
        ROOT
        / "outputs/tables/opportunity"
        / f"{start_date}_{date.fromisoformat(end_date) - timedelta(days=1)}"
    )
    tables.mkdir(parents=True, exist_ok=True)
    shown = (
        frames["summary"]
        .rename(
            columns={
                "days_contacted": "Days contacted",
                "segment_customers": "Segment customers",
                "reordered_customers": "Customers reordered",
                "reordered_percentage": "Segment reordered (%)",
            }
        )
        .copy()
    )
    shown["Segment reordered (%)"] = shown["Segment reordered (%)"].map(
        lambda n: "N/A" if pd.isna(n) else f"{n:.2f}%"
    )
    note = (
        f"CMPU vet-diet CUSTOMER_UPLOAD aged cancellations [{start_date}, "
        f"{end_date}) UTC; as of {as_of_date} 00:00 UTC. "
        "Segments use distinct relative 24-hour contact-day bins -13 through "
        "+3 across all aged orders per customer, not contact legs or "
        "sessions. "
        "Require inbound SESSION_INITIAL_DIRECTION, matching contact ORDER_ID "
        "and customer ID, all contact categories. "
        + (
            "HANDLED_FLAG=TRUE only. "
            if handled_only
            else (
                "Handled, unhandled and unknown-handled inbound attempts "
                "included. "
            )
        )
        + (
            "Reorders match exact customer, non-null PET_ID and no"
            "nblank PRODUCT_PART_NUMBER, on a different order plac"
            "ed strictly after its matched aged cancellation throu"
            "gh "
            f"{followup_days}"
            " days inclusive. Exclude an entire reorder order if a"
            "ny line has cancellation evidence or unknown status; "
            "same established follow-up rules, any approval channe"
            "l/source. A customer returns if any qualifying aged o"
            "rder has a matching non-cancelled reorder in its own "
            "window. Count each customer once per segment, pooling"
            " multiple pets/products/orders. Denominator is the en"
            "tire contact-frequency segment, including customers m"
            "issing match keys or without reorders; N/A denotes an"
            " empty segment. Frequency includes contacts through d"
            "ay +3, so these descriptive segments include post-can"
            "cellation information.\n\n"
        )
    )
    suffix = "-handled-only" if handled_only else ""
    write_text(
        tables
        / (
            "contact-frequency-"
            f"{followup_days}"
            "d-same-pet-part-reorders"
            f"{suffix}"
            ".md"
        ),
        "# Same-pet/part reorders by contact-day frequency\n\n"
        + note
        + markdown_table(shown)
        + "\n",
    )
    latex = latex_table(
        frames["summary"],
        start_date,
        end_date,
        as_of_date,
        followup_days,
        handled_only,
    )
    write_text(mode / "reorder-table.tex", latex)
    if write_latex:
        publish_latex(latex)
    click.echo(shown.to_string(index=False))
    click.echo(f"Data and SQL: {directory}")


if __name__ == "__main__":
    main()

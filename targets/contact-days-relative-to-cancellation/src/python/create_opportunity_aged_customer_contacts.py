"""
Distinct aged orders and customers initiating inbound contacts around
cancellation.
"""

import hashlib
import json
from datetime import UTC, date, datetime, timedelta

import click
import pandas as pd

from shared.python import create_opportunity_order_cancellation_summary as base
from shared.python.contact_analysis import (
    DAY_NS,
    MAX_DAY,
    MIN_DAY,
    ORDER_COLUMNS,
    analyze,
    frequency_verification_sql,
    render_sql,
)
from shared.python.markdown_tables import markdown_table, write_text
from shared.python.paths import artifact_path, latex_fragment_path
from shared.python.sql_templates import module_sql

ROOT = base.ROOT


def summary_sql(start, end, handled_only):
    return module_sql(
        __file__,
        "contact_summary.sql.j2",
        **base.parameters(start, end),
        min_day=MIN_DAY,
        end_day=MAX_DAY + 1,
        min_day_offset=1 - MIN_DAY,
        day_count=MAX_DAY - MIN_DAY + 1,
        handled_only=handled_only,
    )


def latex_table(daily, audit, start, end, as_of, handled_only):
    if daily.relative_day.tolist() != list(range(MIN_DAY, MAX_DAY + 1)):
        raise ValueError("contact table must include every day -13 through +3")
    first = date.fromisoformat(start).strftime("%B %-d, %Y")
    last = (date.fromisoformat(end) - timedelta(days=1)).strftime("%B %-d, %Y")
    rows = [
        (
            f"{r.relative_day} & {r.distinct_customers:,} & "
            f"{r.distinct_aged_orders:,}"
        )
        + r" \\"
        for r in daily.itertuples()
    ]
    handled_note = (
        r"Require \texttt{HANDLED\_FLAG=TRUE}."
        if handled_only
        else "Include handled, unhandled and unknown-handled inbound attempts."
    )
    return (
        (
            "\\clearpage\n\\subsection{What is the contact pattern "
            "of CMPU aged order customers?}\\label{subsec:contact-"
            "analysis}\n\\subsubsection{When did the CMPU aged "
            "order customers contact Chewy relative to the "
            "cancellation date?}\nTable~\\ref{tab:aged-customer-"
            "contacts-by-cancellation-day} summarizes "
            "inbound\ncontacts linked to CMPU vet-diet "
            "\\texttt{CUSTOMER\\_UPLOAD} aged orders "
            "cancelled\nfrom "
        )
        + first
        + " through "
        + last
        + r""", inclusive, UTC.
The full cohort contains """
        + (
            f"{audit['aged_customers']:,} customers and "
            f"{audit['aged_orders']:,} aged orders."
        )
        + (
            "\n\n\\begin{table}[!htbp]\n\\centering\n\\caption{Custo"
            "mer-initiated inbound contacts by day relative to aged-"
            "order cancellation: distinct customers contacting and "
            "distinct aged order IDs, from 13 days before through "
            "day 3 after cancellation. A total of "
        )
        + f"{audit['distinct_customers_contacting']:,}"
        + r""" distinct customers contacted across this window.}
\label{tab:aged-customer-contacts-by-cancellation-day}
\begin{tabular}{@{}rrr@{}}
\toprule
Days relative to cancellation & Customers contacting & Aged order IDs \\
\midrule
"""
        + "\n".join(rows)
        + r"""
\bottomrule
\end{tabular}

\begin{minipage}{\linewidth}
\footnotesize
\textit{Notes:} Customer-initiated is defined by
\texttt{SESSION\_INITIAL\_DIRECTION=inbound} in
\texttt{EDLDB.BT\_CUSTOMER\_CARE.FCT\_CONTACTS\_BRD}, across all contact
categories. """
        + handled_note
        + r""" Match the original aged \texttt{ORDER\_ID} and require
the contact's numeric \texttt{CUSTOMER\_ID} to match the order's customer.
Use UTC \texttt{SESSION\_START\_DTTM}. Day $n$ is the elapsed 24-hour interval
$[n,n+1)$ days relative to cancellation: day $-1$ is the preceding 24 hours,
and day $0$ starts exactly at cancellation. These are elapsed bins rather
than calendar-date differences. All seventeen rows from $-13$ through $+3$
are retained, with zero for missing days. Count each customer and aged order
once per day, regardless of repeat contact legs, sessions or qualifying order
lines. Counts may overlap across days and should not be added as global unique
totals. Missing timestamps or customer IDs, mismatching customer IDs, unknown
directions and outbound contacts remain audited and are excluded from this
table. Email contacts with Other ingress are included; inbound direction is
a source proxy and does not establish human initiation.
Original eligibility uses cancellation
dates and all qualifying orders, without a first-order or prescription-creation
restriction. Observation cutoff: """
        + as_of
        + r""" 00:00 UTC, allowing the full positive-day window.
\end{minipage}
\end{table}
"""
    )


def frequency_latex(frequency, audit):
    rows = [
        f"{r.days_contacted} & {r.distinct_customers:,}" + r" \\"
        for r in frequency.itertuples()
    ]
    return (
        (
            "\n\\clearpage\n\\subsubsection{What was the frequency "
            "of contacting Chewy for CMPU aged order "
            "customers?}\nTable~\\ref{tab:aged-customer-contact-day-"
            "frequency} groups customers by the\nnumber of distinct "
            "relative days on which they contacted during the "
            "same\n$-13$ through $+3$ window.\n\\begin{table}[!htbp]"
            "\n\\centering\n\\caption{Frequency of customer contact "
            "days around aged-order cancellation: number of "
            "distinct relative days contacted versus number of "
            "customers. Of "
        )
        + f"{audit['aged_customers']:,}"
        + r""" cohort customers, """
        + f"{audit['distinct_customers_contacting']:,}"
        + r""" contacted on at least one day.}
\label{tab:aged-customer-contact-day-frequency}
\begin{tabular}{@{}rr@{}}
\toprule
Number of days contacted & Number of customers \\
\midrule
"""
        + "\n".join(rows)
        + r"""
\bottomrule
\end{tabular}

\begin{minipage}{\linewidth}
\footnotesize
\textit{Notes:} Same CMPU vet-diet \texttt{CUSTOMER\_UPLOAD} aged cohort,
cancellation dates, observation cutoff and inbound contact rules as
Table~\ref{tab:aged-customer-contacts-by-cancellation-day}.
Count each distinct relative 24-hour day bin from $-13$ through $+3$ once
per customer across all qualifying aged orders. Multiple contacts, sessions,
legs or orders on the same relative day do not increase the day count.
These are relative cancellation-day bins, rather than distinct calendar dates.
Each customer appears in exactly one frequency row; zero includes cohort
customers with no qualifying contact in this window. All frequencies from
0 through 17 are retained, including zero-count rows. Customer counts sum to
the full cohort; positive-day rows sum to the distinct contacting customers.
\end{minipage}
\end{table}
"""
    )


def publish_latex(text):
    if (
        latex_fragment_path(
            "customer_contacts_by_cancellation_reason.tex", root=ROOT
        )
    ).exists():
        anchor = r"\label{subsec:contact-analysis}"
        text = text.replace(
            anchor,
            anchor
            + "\n"
            + r"\input{appendix/customer_contacts_by_cancellation_reason}"
            + "\n"
            + r"\clearpage",
            1,
        )
    for name in [
        "contact_frequency_reorders",
        "contact_window_reorders",
        "reproduction_contacts",
    ]:
        if (latex_fragment_path(name + ".tex", root=ROOT)).exists():
            text = text.rstrip() + "\n\n" + r"\input{appendix/" + name + "}\n"
    write_text(latex_fragment_path("contact_analysis.tex", root=ROOT), text)
    main = ROOT / "targets/report/src/latex" / "assembly-source.tex"
    include = r"\input{appendix/contact_analysis}"
    if main.exists():
        body = main.read_text()
        if include not in body:
            anchor = r"\input{appendix/financial_opportunity}"
            if anchor in body:
                body = body.replace(anchor, anchor + "\n" + include, 1)
            else:
                anchor = r"\input{appendix/study_population_analysis}"
                if anchor not in body:
                    raise ValueError(
                        "cannot find the report appendix insertion point"
                    )
                body = body.replace(anchor, include + "\n" + anchor, 1)
            write_text(main, body)


@click.command()
@click.option("--start-date", default="2026-05-01", show_default=True)
@click.option(
    "--end-date",
    default="2026-08-01",
    show_default=True,
    help="Exclusive UTC aged cancellation end.",
)
@click.option("--as-of-date", default="2026-10-28", show_default=True)
@click.option("--write-latex", is_flag=True)
@click.option(
    "--handled-only",
    is_flag=True,
    help="Require HANDLED_FLAG=TRUE as in the previous contact study.",
)
@click.option("--cached", is_flag=True)
@click.option(
    "--print-sql",
    is_flag=True,
    help="Print standalone Snowflake SQL for the final seventeen-row table.",
)
def main(
    start_date,
    end_date,
    as_of_date,
    write_latex,
    handled_only,
    cached,
    print_sql,
):
    params = base.parameters(start_date, end_date)
    if date.fromisoformat(as_of_date) < date.fromisoformat(
        end_date
    ) + timedelta(days=MAX_DAY + 1):
        raise click.ClickException(
            "as-of must allow all contacts through day +3"
        )
    sql = render_sql(start_date, end_date)
    report_sql = summary_sql(start_date, end_date, handled_only)
    if print_sql:
        click.echo(report_sql)
        return
    directory = artifact_path(
        ROOT
        / "data/opportunity/aged-customer-contacts"
        / f"{start_date}_{end_date}_as-of-{as_of_date}"
    )
    directory.mkdir(parents=True, exist_ok=True)
    source = directory / "source.parquet"
    manifest = directory / "source.json"
    identity = dict(
        version=1,
        **params,
        as_of_date=as_of_date,
        timezone="UTC",
        min_day=MIN_DAY,
        max_day=MAX_DAY,
        sql_sha256=hashlib.sha256(sql.encode()).hexdigest(),
    )
    if cached:
        meta = json.loads(manifest.read_text())
        if meta["identity"] != identity or meta[
            "source_sha256"
        ] != base.digest(source):
            raise click.ClickException(
                "cache fingerprint differs; rerun fresh"
            )
    else:
        manifest.unlink(missing_ok=True)
        write_text(directory / "query.sql", sql)
        engine = base.extract(directory / "query.sql", source, directory)
        meta = dict(
            identity=identity,
            source_sha256=base.digest(source),
            extracted_at_utc=datetime.now(UTC).isoformat(),
            **engine,
        )
    frames, audit, verify = analyze(
        pd.read_parquet(source), start_date, end_date, handled_only
    )
    mode = "handled-inbound" if handled_only else "all-inbound"
    analysis = directory / mode
    analysis.mkdir(parents=True, exist_ok=True)
    for name, frame in frames.items():
        frame.to_parquet(
            analysis / (name.replace("_", "-") + ".parquet"), index=False
        )
    write_text(analysis / "verification.sql", verify + ";\n")
    write_text(analysis / "summary.sql", report_sql)
    write_text(
        analysis / "frequency-verification.sql",
        frequency_verification_sql(handled_only) + ";\n",
    )
    write_text(
        analysis / "analysis.json",
        json.dumps(
            {
                "source_sha256": meta["source_sha256"],
                "audit": audit,
                "exports": {
                    p.name: base.digest(p) for p in analysis.glob("*.parquet")
                },
            },
            indent=2,
        )
        + "\n",
    )
    write_text(manifest, json.dumps(meta, indent=2) + "\n")
    tables = artifact_path(
        ROOT
        / "outputs/tables/opportunity"
        / f"{start_date}_{date.fromisoformat(end_date) - timedelta(days=1)}"
    )
    tables.mkdir(parents=True, exist_ok=True)
    display = frames["daily_summary"].rename(
        columns={
            "relative_day": "Days relative to cancellation",
            "distinct_customers": "Distinct customers contacting",
            "distinct_aged_orders": "Distinct aged order IDs",
        }
    )
    note = (
        f"CMPU vet-diet CUSTOMER_UPLOAD aged cancellations [{start_date}, "
        f"{end_date}) UTC, all qualifying orders and customers, with no "
        f"first-order or prescription-creation restriction. "
        f"{audit['aged_orders']:,} aged orders / {audit['aged_customers']:,} "
        f"customers; as of {as_of_date} 00:00 UTC. "
        "Use EDLDB.BT_CUSTOMER_CARE.FCT_CONTACTS_BRD, joined on original aged "
        "ORDER_ID, requiring contact CUSTOMER_ID to match the aged-order "
        "customer. "
        "Customer-initiated means normalized "
        "SESSION_INITIAL_DIRECTION=inbound, all categories; no WISMO filter. "
        + (
            "Require HANDLED_FLAG=TRUE. "
            if handled_only
            else (
                "Include handled, unhandled and unknown-handled inbound "
                "attempts. "
            )
        )
        + (
            "Time is SESSION_START_DTTM, confirmed UTC in the "
            "previous contact/Sankey study. Day n is the exact 24-"
            "hour interval [cancellation+n days, cancellation+(n+1) "
            "days): negative days are before cancellation, zero "
            "starts at cancellation. Always include all seventeen "
            "day rows -13 through +3, filling absent counts with "
            "zero. Each customer/order counts once per day "
            "regardless of contact legs, sessions or qualifying "
            "order lines; counts can overlap across days and must "
            "not be summed as global unique totals. Missing "
            "timestamps, unknown directions, missing/mismatched "
            "contact customer IDs and outbound contacts remain in "
            "details/audits but are excluded from the table. Source "
            "has no contacts outside the requested dated window, "
            "except undated rows retained for audit.\n\n"
        )
    )
    suffix = "-handled-only" if handled_only else ""
    write_text(
        tables / f"aged-customer-contacts-by-cancellation-day{suffix}.md",
        "# Customer-initiated contacts around aged cancellation\n\n"
        + note
        + markdown_table(display)
        + "\n",
    )
    frequency = frames["contact_day_frequency"].rename(
        columns={
            "days_contacted": "Number of days contacted",
            "distinct_customers": "Number of customers",
        }
    )
    write_text(
        tables / f"aged-customer-contact-day-frequency{suffix}.md",
        "# Customer contact-day frequency\n\n"
        + note
        + (
            "Each customer is assigned to one row by distinct relative day "
            "bins across their aged orders. Zero includes customers with no "
            "qualifying contact; all 0..17 rows are present.\n\n"
        )
        + markdown_table(frequency)
        + "\n",
    )
    latex = latex_table(
        frames["daily_summary"],
        audit,
        start_date,
        end_date,
        as_of_date,
        handled_only,
    ) + frequency_latex(frames["contact_day_frequency"], audit)
    write_text(analysis / "contact-table.tex", latex)
    if write_latex:
        publish_latex(latex)
    click.echo(display.to_string(index=False))
    click.echo(json.dumps(audit, indent=2))
    click.echo(f"Exports and SQL: {analysis}")


if __name__ == "__main__":
    main()

__all__ = [
    "DAY_NS",
    "MAX_DAY",
    "MIN_DAY",
    "ORDER_COLUMNS",
    "analyze",
    "frequency_verification_sql",
    "render_sql",
]

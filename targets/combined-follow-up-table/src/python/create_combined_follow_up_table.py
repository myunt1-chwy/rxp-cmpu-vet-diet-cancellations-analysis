"""Combine existing follow-up report tables without requerying data."""

import pandas as pd

from shared.paths import artifact_path, latex_fragment_path
from shared.python.follow_up_tables import (
    ROOT,
    SOURCES,
    read_table,
)
from shared.python.markdown_tables import markdown_table, write_text


def render_comparison(study="same_part_pet"):
    if study not in {
        "same_part_pet",
        "same_pet_different_part",
        "any_vet_diet",
        "all_chewy",
    }:
        raise ValueError(f"Unknown comparison study: {study}")
    different_product = study == "same_pet_different_part"
    sources = [
        (cohort, filename.replace("same_part_pet", study))
        for cohort, filename in SOURCES
    ]
    stem = (
        "same-pet-different-product"
        if different_product
        else "same-pet-product"
    )
    title = (
        "What percentage of customers come back and place a successful order "
        "for the same pet "
        "but different product after an aged order in the next 70 days?"
        if different_product
        else (
            "What percentage of customers come back and place a "
            "successful vet diet order for the same pet and part "
            "number after an aged order in the next 70 days?"
        )
    )
    caption = (
        "Same-pet, different-product vet-diet follow-up"
        if different_product
        else "Same-pet, same-product follow-up"
    )
    labels = (
        [
            "tab:financial-opportunity-reorder-same-pet-different-part",
            "tab:financial-opportunity-new-upload-same-pet-different-part",
            "tab:financial-opportunity-new-vet-diet-same-pet-different-part",
        ]
        if different_product
        else [
            "tab:financial-opportunity-reorder-windows",
            "tab:financial-opportunity-new-upload-follow-up",
            "tab:financial-opportunity-new-vet-diet-follow-up",
        ]
    )
    matching = (
        r"""Require the same numeric customer ID and non-null \texttt{PET\_ID},
a different nonblank \texttt{PRODUCT\_PART\_NUMBER} from the anchor line,
and a TRUE vet-diet flag on the later line. Use a different order"""
        if different_product
        else (
            "Require the same numeric customer ID, "
            "exact\n\\texttt{PRODUCT\\_PART\\_NUMBER} and non-null "
            "\\texttt{PET\\_ID} on a different order"
        )
    )
    if study == "any_vet_diet":
        stem = "any-vet-diet"
        title = (
            "What percentage of customers place a successful vet diet order "
            "after an aged order in the next 70 days?"
        )
        caption = "Any vet-diet follow-up, for any pet or product"
        labels = [
            "tab:financial-opportunity-reorder-any-vet-diet",
            "tab:financial-opportunity-new-upload-any-vet-diet",
            "tab:financial-opportunity-new-vet-diet-any-vet-diet",
        ]
        matching = (
            "Require the same numeric customer ID and a TRUE "
            "vet-diet flag on the later line; purchases may be "
            "for any pet and any product part number. Use a "
            "different order"
        )
    source_note = (
        "Later orders may use any approval channel or prescription source "
        "within the certified RxP line view."
    )
    cancellation_subject = "any line"
    sales_note = (
        "Net sales sum \\texttt{ORDER\\_LINE\\_NET\\_SALES} "
        "once per matching shipment/line contribution, "
        "preserving zero and negative amounts; missing sales "
        "make totals incomplete."
    )
    precision_note = "Amounts display two decimals; exports retain five."
    if study == "all_chewy":
        sources = [
            (
                cohort,
                filename.replace("follow_up_same_part_pet", "chewy_follow_up"),
            )
            for cohort, filename in SOURCES
        ]
        stem = "all-chewy"
        title = (
            "What percentage of customers place a Chewy order successfully "
            "in the following 70 days after their aged order?"
        )
        caption = "All-Chewy follow-up, across all product categories"
        labels = [
            "tab:financial-opportunity-reorder-all-chewy",
            "tab:financial-opportunity-new-upload-all-chewy",
            "tab:financial-opportunity-new-vet-diet-all-chewy",
        ]
        matching = (
            "Match the same numeric customer ID only; include "
            "all Chewy product categories and any pet or "
            "product. Use a different order"
        )
        source_note = (
            r"Follow-up orders come from \texttt{EDLDB.ECOM.ORDER\_LINE}; "
            "no later prescription, approval-channel, prescription-source, "
            "vet-diet, product or pet restriction applies."
        )
        cancellation_subject = "any line or order"
        sales_note = (
            "Net sales sum \\texttt{NET\\_SALES} on all "
            "qualifying ECOM order lines once per physical "
            "order line, preserving zero and negative amounts. "
            "Exact source duplicates collapse and conflicting "
            "line values fail validation; missing sales make "
            "totals incomplete."
        )
        precision_note = (
            "Amounts display two decimals; ECOM supplies four-decimal "
            "amounts, retained exactly in five-decimal exports."
        )
    tables = [
        read_table(latex_fragment_path(filename, root=ROOT))
        for _, filename in sources
    ]
    days = [row[0] for row in tables[0][0]]
    if any(
        [row[0] for row in table[0]] != days or table[2:] != tables[0][2:]
        for table in tables[1:]
    ):
        raise ValueError(
            "Follow-up days, cancellation periods and cutoffs must agree"
        )
    rows = []
    exports = []
    for index, day in enumerate(days):
        cells = [day]
        for (cohort, _), (source_rows, denominator, _, _) in zip(
            sources, tables
        ):
            values = source_rows[index][1:]
            cells.extend(values)
            exports.append(
                [
                    cohort,
                    denominator,
                    day,
                    *[v.replace(r"\%", "%") for v in values],
                ]
            )
        rows.append(" & ".join(cells) + r" \\")
    first, last = tables[0][2]
    cutoff = tables[0][3]
    all_n, upload_n, vet_n = [table[1] for table in tables]
    text = (
        r"""\begin{landscape}
\subsubsection{"""
        + title
        + r"""}
The three cohorts below compare non-cancelled reorders after CMPU vet-diet
\texttt{CUSTOMER\_UPLOAD} aged cancellations from """
        + first
        + " through "
        + last
        + (
            ", inclusive, UTC.\nThe yellow columns show returning "
            "customers. Each cohort uses its own fixed "
            "denominator.\n\n\\begin{table}[!htbp]\n\\centering\n\\c"
            "aption{"
        )
        + caption
        + (
            ": cumulative customers, cohort percentages, distinct "
            "orders and matching-line net sales across three aged-"
            "customer cohorts.}\n"
        )
        + "\n".join(r"\label{" + label + "}" for label in labels)
        + (
            "\n\\small\n\\setlength{\\tabcolsep}{4pt}\n\\begin{tabul"
            "ar}{@{}r >{\\columncolor{yellow!35}}r rrr "
            ">{\\columncolor{yellow!35}}r rrr "
            ">{\\columncolor{yellow!35}}r rrr@{}}\n\\toprule\n & "
            "\\multicolumn{4}{c}{\\shortstack{All aged "
            "customers\\\\$N = "
        )
        + all_n
        + (
            "$}}\n & \\multicolumn{4}{c}{\\shortstack{First "
            "\\texttt{CUSTOMER\\_UPLOAD}\\\\vet-diet order aged; $N "
            "= "
        )
        + upload_n
        + r"""$}}
 & \multicolumn{4}{c}{\shortstack{First vet-diet order aged\\$N = """
        + vet_n
        + (
            "$}} \\\\\n\\cmidrule(lr){2-5}\\cmidrule(lr){6-"
            "9}\\cmidrule(lr){10-13}\nDays & Customers & Cohort "
            "(\\%) & Orders & Net sales & Customers & Cohort (\\%) "
            "& Orders & Net sales & Customers & Cohort (\\%) & "
            "Orders & Net sales \\\\\n\\midrule\n"
        )
        + "\n".join(rows)
        + (
            "\n\\bottomrule\n\\end{tabular}\n\n\\begin{minipage}{\\l"
            "inewidth}\n\\footnotesize\n\\textit{Cohorts and "
            "anchors:} All aged customers includes every qualifying "
            "aged cancellation,\nwithout a prescription-creation or "
            "first-order restriction. For each first-order "
            "cohort,\nthe customer's first qualifying aged order is "
            "the sole anchor; later aged orders do not reset follow-"
            "up.\nThe first customer-upload cohort uses the "
            "earliest observed vet-diet \\texttt{CUSTOMER\\_"
            "UPLOAD}\norder across historical prescription sources, "
            "using linked prescriptions and ECOM order "
            "history.\nThe first vet-diet cohort uses earliest "
            "observed vet-diet orders across all historical "
            "approval\nchannels and prescription sources, using RxP "
            "vet-diet lines and ECOM order history.\nEach "
            "percentage divides returning customers by its group's "
            "fixed full cohort, including\ncustomers without a "
            "qualifying reorder or with unusable matching keys. The "
            "cohorts overlap;\ndo not add their "
            "counts.\n\n\\textit{Shared follow-up rules:} "
        )
        + matching
        + (
            "\nplaced strictly after the matched cancellation "
            "through the indicated day, inclusive.\n"
        )
        + source_note
        + r"""
Exclude the entire later order if """
        + cancellation_subject
        + (
            " has status X, a recorded cancellation reason,\na "
            "cancellation timestamp or unknown line status. "
            "Statuses and prescription channels reflect\nthe "
            "extraction snapshot. All windows require complete "
            "follow-up through "
        )
        + cutoff
        + (
            ".\nEach customer, order and matching physical line "
            "counts once per window, despite repeated\nanchor "
            "associations. Windows overlap and must not be added. "
        )
        + sales_note
        + (
            "\nSales can be recorded after the placement window and "
            "do not prove recovered revenue.\n"
        )
        + precision_note
        + r""" N/A denotes a zero cohort denominator.
\end{minipage}
\end{table}
\end{landscape}
"""
    )
    destination = artifact_path(ROOT / "src/autogenerated/combined-follow-up")
    destination.mkdir(parents=True, exist_ok=True)
    write_text(destination / f"{stem}.tex", text)
    output = artifact_path(
        ROOT / "outputs/tables/opportunity/combined-follow-up"
    )
    output.mkdir(parents=True, exist_ok=True)
    write_text(
        output / f"{stem}.md",
        "# " + caption + " comparison\n\n"
        "Presentation values from the three existing report tables; no "
        "warehouse refresh.\n\n"
        + markdown_table(
            pd.DataFrame(
                exports,
                columns=[
                    "Cohort",
                    "Cohort customers",
                    "Days",
                    "Customers",
                    "Cohort (%)",
                    "Orders",
                    "Net sales",
                ],
            )
        )
        + "\n",
    )
    print(
        f"Prepared combined {stem} follow-up table from existing report "
        f"fragments."
    )


def main():
    render_comparison()
    render_comparison("same_pet_different_part")
    render_comparison("any_vet_diet")
    render_comparison("all_chewy")


if __name__ == "__main__":
    main()

__all__ = ["ROOT", "SOURCES", "read_table"]

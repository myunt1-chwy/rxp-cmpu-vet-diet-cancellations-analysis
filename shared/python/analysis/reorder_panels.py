"""Shared six-column presentation for validated reorder cohort tables."""


def render_panel(
    rows, denominator, label, narrative, title, eligibility_note=""
):
    """Render values read from an authoritative Org table."""
    values = [[*row] for row in rows]
    for row in values:
        row[2] = row[2].replace(r"\%", "")
    return (
        narrative
        + r"\refstepcounter{table}\label{"
        + label
        + "}\n"
        + r"\par\smallskip\noindent\textbf{Table~\thetable. "
        + title
        + "}\n"
        + r"\par\smallskip\raggedright\footnotesize "
        + r"Shared methodology: "
        + r"Section~\ref{subsec:financial-opportunity-analysis}."
        + ("\n" + r"\par\noindent " + eligibility_note + "\n")
        + r"\par\smallskip\noindent\textbf{Cohort denominator: "
        + denominator
        + "}\n"
        + r"\par\smallskip\centering\footnotesize"
        + "\n"
        + r"\setlength{\tabcolsep}{2pt}"
        + "\n"
        + r"\begin{tabular}{rrrrrr}\toprule"
        + "\n"
        + r"Days & Customers & \shortstack{Cohort\\(\%)} & Orders & "
        + r"\shortstack{Line\\items} & \shortstack{Net sales\\(USD)}"
        + r" \\ \midrule"
        + "\n"
        + "\n".join(" & ".join(row) + r" \\" for row in values)
        + "\n"
        + r"\bottomrule\end{tabular}\par"
        + "\n"
    )

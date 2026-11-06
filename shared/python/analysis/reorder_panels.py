"""Shared six-column presentation for validated reorder cohort tables."""


def render_panel(
    rows, denominator, label, narrative, title, eligibility_note=""
):
    """Render Org values without the legacy numerical summary paragraph."""
    values = [[*row] for row in rows]
    for row in values:
        row[2] = row[2].replace(r"\%", "")
        row[3], row[4] = row[4], row[3]
    return (
        r"\refstepcounter{table}\label{"
        + label
        + "}\n"
        + r"\par\smallskip\noindent"
        + r"\parbox[t][2\baselineskip][t]{\linewidth}{"
        + r"\raggedright\textbf{Table~\thetable. "
        + title
        + "}}\n"
        + r"\par\raggedright\footnotesize "
        + r"Shared methodology: "
        + r"Section~\ref{subsec:medium-term-reorder-behavior}."
        # Reorder types have different caption lengths within a cohort row.
        # Reserve equal space so the table top rules remain aligned.
        + "\n"
        + r"\par\noindent\parbox[t][2\baselineskip][t]{\linewidth}{"
        + r"\raggedright "
        + eligibility_note
        + "}\n"
        + r"\par\noindent\textbf{Cohort denominator: "
        + denominator
        + "}\n"
        + r"\par\centering\footnotesize"
        + "\n"
        + r"\setlength{\tabcolsep}{2pt}"
        + "\n"
        + r"\begin{tabular}{rrrrrr}\toprule"
        + "\n"
        + r"Days & Customers & \shortstack{Cohort\\(\%)} & "
        + r"\shortstack{Line\\items} & Orders & \shortstack{Net sales\\(USD)}"
        + r" \\ \midrule"
        + "\n"
        + "\n".join(" & ".join(row) + r" \\" for row in values)
        + "\n"
        + r"\bottomrule\end{tabular}\par"
        + "\n"
    )

"""
Render migrated target-owned content from retained, verified presentation
data.

This is a migration comparison tool, not a replacement for the target
generators.
It never refreshes or uploads data and does not replace the published PDF.
"""

import argparse
import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path

from graph import load_graph
from jinja2 import Environment, StrictUndefined

ROOT = Path(__file__).resolve().parents[3]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists() or path.read_text() != text:
        path.write_text(text)


def tex_escape(text):
    return "".join(
        {
            "\\": r"\textbackslash{}",
            "_": r"\_",
            "&": r"\&",
            "%": r"\%",
            "#": r"\#",
            "{": r"\{",
            "}": r"\}",
            "$": r"\$",
        }.get(c, c)
        for c in text
    )


def reproduction(directory):
    """
    Include the same authored commands and caveats used to generate HOWTO.
    """
    readme = (directory / "README.org").read_text()
    instructions = readme.split("* Reproduction commands\n", 1)[1].split(
        "\n* ", 1
    )[0]
    lines = [
        r"\par\smallskip\noindent\textbf{Section Reproduction Steps}\par",
        r"\begin{quote}\small",
    ]
    code = False
    for line in instructions.splitlines():
        if line.startswith("#+begin_src"):
            code = True
            lines.append(r"\par")
        elif line.startswith("#+end_src"):
            code = False
        elif code:
            lines.append(r"\noindent\texttt{" + tex_escape(line) + r"}\par")
        elif not line:
            lines.append(r"\par")
        else:
            pieces = re.split(
                r"(?<![\w=])=(\S(?:.*?\S)?)=(?=$|[\s.,;:)])", line
            )

            def inline(piece, index):
                if not index % 2:
                    return tex_escape(piece)
                if "/" in piece and " " not in piece:
                    return r"\path{" + piece + "}"
                return r"\texttt{" + tex_escape(piece) + "}"

            lines.append(
                "".join(
                    inline(piece, index) for index, piece in enumerate(pieces)
                )
            )
    lines.append(r"\end{quote}")
    return "\n".join(lines) + "\n"


def render_visual(directory):
    visual = directory / "src/latex/visual.tex"
    text = visual.read_text()
    if (directory / "src/latex/table-layout.json").exists():
        cache = directory / "data/table.org"
        if not cache.exists():
            raise ValueError(
                f"Missing migration snapshot {cache}; restore its "
                f"retained source before previewing."
            )
        provenance = json.loads(
            (directory / "data/table-provenance.json").read_text()
        )
        if digest(cache) != provenance["sha256"]:
            raise ValueError(
                f"Changed retained table: {directory.name}; reconcile "
                f"before previewing."
            )
        output = directory / "outputs/tables/table.org"
        write(output, cache.read_text())
        lines = [
            line
            for line in output.read_text().splitlines()
            if line.startswith("|")
        ]
        rows = [
            [v.strip() for v in line.strip("|").split("|")]
            for line in lines[2:]
        ]
        layout = json.loads(
            (directory / "src/latex/table-layout.json").read_text()
        )
        if len(rows) != provenance["rows"] or any(
            len(r) != provenance["columns"] for r in rows
        ):
            raise ValueError(
                "Org table dimensions differ from retained snapshot"
            )
        serialized = []
        for row, prefix, length in zip(
            rows, layout["prefixes"], layout["lengths"], strict=True
        ):
            serialized.append(
                prefix + "\n" + " & ".join(row[:length]) + r" \\"
            )
        text = (
            Environment(undefined=StrictUndefined)
            .from_string(text)
            .render(table_rows="\n".join(serialized))
        )
    provenance = directory / "data/provenance.json"
    if provenance.exists():
        for asset in json.loads(provenance.read_text()):
            source = directory / asset["cache"]
            if not source.exists() or digest(source) != asset["sha256"]:
                raise ValueError(
                    f"Missing or changed retained figure: {source}"
                )
            output = directory / asset["output"]
            output.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, output)
    return text


def preview(repro=0, final=0, compile_pdf=True, only=None, live=False):
    targets, ordered = load_graph(ROOT)
    for key in reversed(ordered):
        if key == "report":
            continue
        if only is not None and key not in only:
            continue
        m = targets[key]
        directory = ROOT / "targets" / key
        wide = False
        title = m.get("question") or m["title"]
        body = (directory / "src/latex/body.tex").read_text()
        if m["level"] == "paragraph":
            visual = (
                (directory / "outputs/latex/visual.tex").read_text()
                if live
                else render_visual(directory)
            )
            text = "\\paragraph{" + title + "}\n" + body + "\n" + visual
            if key in {
                "same-pet-product-return-comparison",
                "same-pet-other-product-return-comparison",
                "any-vet-diet-return-comparison",
                "any-chewy-return-comparison",
                "first-order-upload-coverage",
                "no-recorded-cancellation-upload-statuses",
                "aged-line-upload-statuses",
            }:
                wide = True
        else:
            text = "\\" + m["level"] + "{" + title + "}\n" + body
        # Composition order must exactly match the explicit graph.
        actual = re.findall(r"\\AnalysisChild\{([^}]+)\}", body)
        if actual != m["children"]:
            raise ValueError(
                f"LaTeX/metadata child order differs: {key}: {actual}"
            )
        text = re.sub(
            r"\\AnalysisChild\{([^}]+)\}",
            lambda match: (
                "\\input{targets/" + match[1] + "/outputs/latex/content.tex}"
            ),
            text,
        )
        if repro:
            # Parent instructions precede children, matching HOWTO's traversal.
            heading, remainder = text.split("\n", 1)
            text = heading + "\n" + reproduction(directory) + remainder
        if wide:
            text = "\\begin{landscape}\n" + text + "\n\\end{landscape}\n"
        write(directory / "outputs/latex/content.tex", text + "\n")
    if only is not None and "report" not in only:
        return
    report = ROOT / "targets/report"
    write(
        report / "src/autogenerated/report-build-mode.tex",
        "\\reportfinal" + ("true" if final else "false") + "\n",
    )
    text = (report / "src/latex/preamble.tex").read_text()
    if repro:
        text += reproduction(report)
    text += "\n".join(
        "\\input{targets/" + key + "/outputs/latex/content.tex}"
        for key in targets["report"]["children"]
    )
    text += "\n" + (report / "src/latex/backmatter.tex").read_text()
    write(report / "src/autogenerated/main.tex", text)
    if compile_pdf:
        build = ROOT / "build/target-preview"
        build.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            [
                "latexmk",
                "-pdf",
                "-interaction=nonstopmode",
                "-halt-on-error",
                "-file-line-error",
                "-outdir=" + str(build),
                str(report / "src/autogenerated/main.tex"),
            ],
            cwd=ROOT,
            check=True,
        )
        dest = report / "outputs/reports/pdf"
        dest.mkdir(parents=True, exist_ok=True)
        shutil.copy2(
            build / "main.pdf", dest / "phds-cmpu-aged-orders-analysis.pdf"
        )
        print(
            "Report build:" if live else "Migration preview:",
            dest / "phds-cmpu-aged-orders-analysis.pdf",
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repro", type=int, choices=[0, 1], default=0)
    parser.add_argument("--final", type=int, choices=[0, 1], default=0)
    parser.add_argument("--no-pdf", action="store_true")
    args = parser.parse_args()
    preview(args.repro, args.final, not args.no_pdf)

"""Adapt validated generator exports into target-owned Org and LaTeX artifacts.

The legacy renderers still calculate their tables together with their audits.
This adapter captures those newly generated cells, writes the authoritative Org
table, then reads that table back to assemble the paragraph's LaTeX visual.
It never uses the migration's retained presentation snapshots for live builds.
"""

import hashlib
import json
import re
import shutil

from preview import ROOT, write


def flatten(path, visited=None):
    visited = set() if visited is None else visited
    path = path.resolve()
    if path in visited:
        raise ValueError(f"Cyclic LaTeX input: {path}")

    def include(match):
        child = ROOT / "src/latex" / match[1]
        if not child.suffix:
            child = child.with_suffix(".tex")
        return flatten(child, visited | {path})

    return re.sub(r"\\input\{([^}]+)\}", include, path.read_text())


def visual_block(text, reference):
    labels = re.findall(r"\\label\{([^}]+)\}", reference)
    blocks = []
    for match in re.finditer(
        r"\\begin\{(table|longtable)\}(?:\[[^\]]*\])?", text
    ):
        end = text.index("\\end{" + match[1] + "}", match.end()) + len(
            "\\end{" + match[1] + "}"
        )
        block = text[match.start() : end]
        if (labels and "\\label{" + labels[0] + "}" in block) or (
            not labels and match[1] == "longtable"
        ):
            blocks.append(block)
    if len(blocks) != 1:
        raise ValueError(
            f"Expected one current table for {labels}; found {len(blocks)}"
        )
    return blocks[0]


def table_rows(block):
    start = block.index(r"\midrule") + len(r"\midrule")
    end = block.index(r"\bottomrule", start)
    if r"\endhead" in block[start:end]:
        start = block.index(r"\endhead", start) + len(r"\endhead")
    rows, prefixes, pending, pieces = [], [], [], []
    for line in block[start:end].strip().splitlines():
        if line.strip().startswith(
            (r"\midrule", r"\rowcolor", r"\addlinespace")
        ):
            pending.append(line)
            continue
        pieces.append(line)
        if line.rstrip().endswith(chr(92) * 2):
            row = " ".join(p.strip() for p in pieces).rstrip()[:-2].strip()
            cells = re.split(r"(?<!\\)\s*&\s*", row)
            if any("|" in cell or "\n" in cell for cell in cells):
                raise ValueError(
                    "Unsupported Org table delimiter in generated cells"
                )
            rows.append(cells)
            prefixes.append("\n".join(pending))
            pieces, pending = [], []
    if pieces or pending or not rows:
        raise ValueError("Incomplete generated table body")
    return start, end, rows, prefixes


def generate(metadata):
    directory = ROOT / "targets" / metadata["id"]
    reference = (directory / "src/latex/visual.tex").read_text()
    if (directory / "src/latex/table-layout.json").exists():
        source = ROOT / metadata["migration"]["source"]
        block = visual_block(flatten(source), reference)
        start, end, rows, prefixes = table_rows(block)
        widths = [len(row) for row in rows]
        columns = max(widths)
        # The complete multi-row LaTeX header remains alongside the Org cells;
        # column labels are explicit, reviewed metadata rather than guessed.
        headings = metadata["table_columns"]
        if len(headings) != columns:
            raise ValueError(
                f"Column metadata differs from {metadata['id']}: {columns}"
            )
        table = directory / "outputs/tables/table.org"
        content = "#+TITLE: " + metadata["question"] + "\n"
        content += (
            "#+NOTE: Generated from validated results; cell-level LaTeX "
            "formatting is retained.\n\n"
        )
        content += (
            "| "
            + " | ".join(headings)
            + " |\n|"
            + "+".join(["---"] * columns)
            + "|\n"
        )
        content += (
            "\n".join(
                "| " + " | ".join(row + [""] * (columns - len(row))) + " |"
                for row in rows
            )
            + "\n"
        )
        write(table, content)
        # Read back the Org artifact; the final LaTeX cannot bypass its values.
        values = [
            [cell.strip() for cell in line.strip("|").split("|")]
            for line in table.read_text().splitlines()
            if line.startswith("|")
        ][2:]
        if len(values) != len(rows):
            raise ValueError("Org export row count differs")
        body = "\n".join(
            prefix + "\n" + " & ".join(row[:width]) + r" \\"
            for row, prefix, width in zip(
                values, prefixes, widths, strict=True
            )
        )
        reference = block[:start] + "\n" + body + "\n" + block[end:]
        write(
            directory / "outputs/tables/provenance.json",
            json.dumps(
                {
                    "generator_source": str(source.relative_to(ROOT)),
                    "source_sha256": hashlib.sha256(
                        block.encode()
                    ).hexdigest(),
                    "org_sha256": hashlib.sha256(
                        table.read_bytes()
                    ).hexdigest(),
                    "rows": len(rows),
                    "columns": headings,
                },
                indent=2,
            )
            + "\n",
        )
    else:
        # Image source paths are authored metadata, not cached image contents.
        for asset in metadata.get("images", []):
            source = ROOT / asset["source"]
            destination = directory / asset["output"]
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
    write(directory / "outputs/latex/visual.tex", reference)

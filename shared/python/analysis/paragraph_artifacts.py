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
import sys
from pathlib import Path

from preview import ROOT, reorder_wording, write

sys.path.insert(0, str(ROOT))
from shared.python.analysis.reorder_panels import render_panel
from shared.python.paths import artifact_path


def flatten(path, visited=None):
    visited = set() if visited is None else visited
    path = path.resolve()
    if path in visited:
        raise ValueError(f"Cyclic LaTeX input: {path}")

    def include(match):
        name = match[1]
        if not Path(name).suffix:
            name += ".tex"
        if name.startswith("targets/"):
            child = ROOT / name
        else:
            # Retained fragments use the old assembly-relative convention.
            child = artifact_path((ROOT / "src/latex" / name).resolve())
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


def cohort_panel(block, index):
    """Select one cohort without changing the validated comparison cells."""
    if index not in range(3):
        raise ValueError("Expected one of the three return cohorts")
    _, _, rows, _ = table_rows(block)
    denominators = re.findall(r"\$N = ([\d,]+)\$", block)
    labels = re.findall(r"\\label\{([^}]+)\}", block)
    if len(denominators) != 3 or len(labels) != 3:
        raise ValueError("Expected three cohort denominators and labels")
    if any(len(row) != 16 for row in rows):
        raise ValueError("Expected a 16-column reorder comparison")
    selected = [[row[0], *row[1 + 5 * index : 6 + 5 * index]] for row in rows]
    first, last = selected[0], selected[-1]
    denominator = denominators[index]
    narrative = (
        f"Of {denominator} customers, {first[1]} ({first[2]}) reordered "
        f"by day {first[0]} and {last[1]} ({last[2]}) by day {last[0]}. "
        f"At day {last[0]}, reordering customers placed {last[3]} distinct "
        f"qualifying orders and {last[4]} distinct matching line items."
        "\n\n"
    )
    label = labels[index]
    title = (
        "Same-pet, different-product reorders"
        if "different-part" in label
        else "Any vet-diet reorders"
        if "any-vet-diet" in label
        else "Chewy-wide reorders"
        if "all-chewy" in label
        else "Same-pet, same-product reorders"
    )
    eligibility_note = (
        "Vet-diet line items for the same pet and a different part number."
        if "different-part" in label
        else "Vet-diet line items for any pet and any part number."
        if "any-vet-diet" in label
        else "Line items for any pet, product or category."
        if "all-chewy" in label
        else "Line items for the same pet and the same part number."
    )
    return render_panel(
        selected, denominator, label, narrative, title, eligibility_note
    )


def generate(metadata):
    directory = ROOT / "targets" / metadata["id"]
    if metadata.get("generated_visual"):
        if not (directory / "outputs/latex/visual.tex").is_file():
            raise ValueError("Missing generated visual; rebuild the pipeline")
        return
    reference_path = metadata.get("reference_visual")
    reference = (
        ROOT / reference_path
        if reference_path
        else directory / "src/latex/visual.tex"
    ).read_text()
    if (directory / "src/latex/table-layout.json").exists() or (
        "cohort_panel" in metadata
    ):
        source = ROOT / metadata["migration"]["source"]
        block = reorder_wording(visual_block(flatten(source), reference))
        if "cohort_panel" in metadata:
            block = cohort_panel(block, metadata["cohort_panel"])
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
    write(directory / "outputs/latex/visual.tex", reorder_wording(reference))

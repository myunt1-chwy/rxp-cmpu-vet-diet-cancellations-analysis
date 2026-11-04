"""Render reusable prescription-flow Sankeys with transparent backgrounds."""

import csv
import io
import json
import os
import re
import subprocess
import sys
import textwrap
import xml.etree.ElementTree as ET
from pathlib import Path
from tempfile import TemporaryDirectory

from shared.python.markdown_tables import write_text
from shared.runtime import ROOT

RENDERER = ROOT / ".agents/skills/mermaid-diagrams/scripts/render.py"
SVG_RASTERIZER = ROOT / "scripts/render_sankey_svg.cjs"
TEXT_SCALE = 1.2
NODE_FONT_SIZE = 30
STAGE_SPACING = 600
LABEL_WIDTH = 28
NODE_LINE_HEIGHT = 34


def mermaid_source(flows, title=None):
    denominator = int(flows.loc[flows.transition.eq(1)].prescriptions.sum())
    totals = (
        flows.loc[flows.transition.eq(1)]
        .groupby("source")
        .prescriptions.sum()
        .to_dict()
    )
    totals.update(flows.groupby("target").prescriptions.sum().to_dict())
    labels = {
        node: f"{node} ({count:,}; {100 * count / denominator:.2f}%)"
        for node, count in totals.items()
    }
    # Keep category colors consistent between the full and focused diagrams.
    palette = {
        "Channel: CUSTOMER_UPLOAD": "#4E79A7",
        "Channel: VERBAL": "#AF7AA1",
        "Channel: CUSTOMER_EMAIL": "#FF9DA7",
        "Channel: FAX": "#F28E2C",
        "Channel: CLINIC_EMAIL": "#BAB0AB",
        "Channel: PH": "#8CC9EE",
        "Channel: SNAIL_MAIL": "#B6A7D8",
        "Channel: PARTNER": "#E15759",
        "First order: Aged Order": "#AF7AA1",
        "First order: Customer Initiated Cancellation": "#FF9DA7",
        "First order: Customer Request": "#E15759",
        "First order: Not canceled": "#4E79A7",
        "First order: Other cancellation reason": "#BAB0AB",
        "First order: No first order ID": "#AEB9C3",
        "First order line status: X": "#E15759",
        "First order line status: D": "#4E79A7",
        "First order line status: S": "#8CC9EE",
        "First order line status: C": "#AF7AA1",
        "First order line status: R": "#F28E2C",
    }
    palette.update(flows.attrs.get("node_colors", {}))
    node_colors = {
        label: (
            "#8CC9EE"
            if (
                " / No matching upload" in node
                or " / No matching accepted upload" in node
            )
            or node == "Matching upload: No matching upload"
            else "#F28E2C"
            if (
                " / Has matching upload" in node
                or " / Has matching accepted upload" in node
            )
            or node == "Matching upload: Has matching upload"
            else palette.get(node, "#BAB0AB")
        )
        for node, label in labels.items()
    }
    buffer = io.StringIO()
    # Quote every label so commas and embedded quotes remain valid Sankey CSV.
    writer = csv.writer(
        buffer, lineterminator="\n", quoting=csv.QUOTE_NONNUMERIC
    )
    for row in flows.itertuples(index=False):
        writer.writerow(
            [labels[row.source], labels[row.target], row.prescriptions]
        )
    height = int(
        max(
            1200,
            128
            * max(
                flows.groupby("transition").source.nunique().max(),
                flows.groupby("transition").target.nunique().max(),
            ),
        )
    )
    config = {
        "theme": "base",
        "themeVariables": {
            "fontFamily": "Arial",
            "fontSize": f"{18 * TEXT_SCALE:g}px",
        },
        "themeCSS": (
            f".node-labels, .node-labels text {{ font-size: "
            f"{NODE_FONT_SIZE:g}px; font-weight: bold; }} "
            ".links { stroke-opacity: 0.75; } .link { mix-blend-mode: normal "
            "!important; } "
            f'[class$="TitleText"] {{ font-size: {24 * TEXT_SCALE:g}px; '
            "paint-order: stroke; stroke: white; stroke-width: 3px; "
            "stroke-linejoin: round; }"
        ),
        "sankey": {
            "width": STAGE_SPACING * int(flows.transition.max()) + 10,
            "height": height,
            "linkColor": "source",
            "nodeColors": node_colors,
            "nodeAlignment": flows.attrs.get("node_alignment", "justify"),
            "showValues": False,
            "useMaxWidth": False,
            "nodePadding": 112,
            "labelStyle": "outlined",
        },
    }
    heading = "title: " + json.dumps(title) + "\n" if title else ""
    return (
        "---\n"
        + heading
        + "config: "
        + json.dumps(config)
        + "\n---\nsankey-beta\n"
        + buffer.getvalue()
    )


def add_title(svg, title, columns=None, bottom_padding=0):
    """Mermaid's Sankey renderer ignores visible frontmatter titles."""
    namespace = "http://www.w3.org/2000/svg"
    ET.register_namespace("", namespace)
    try:
        diagram = ET.fromstring(svg)
    except ET.ParseError as error:
        raise ValueError("Mermaid produced invalid SVG") from error
    _, _, width, height = map(float, diagram.attrib["viewBox"].split())
    nodes = diagram.findall(f'.//{{{namespace}}}g[@class="node"]')
    node_x = sorted({float(g.attrib["x"]) for g in nodes if "x" in g.attrib})
    if node_x:
        # Mermaid measures the original single-line labels into its viewBox.
        # Reclaim that space after wrapping, reserving a terminal-label column.
        width = max(node_x) + 650
        height = max(
            float(g.attrib.get("y", 0))
            + float(g.find(f"{{{namespace}}}rect").attrib["height"])
            for g in nodes
        )
        diagram.set("viewBox", f"-16 -64 {width} {height + 128}")
        height += 128

    def multiline(element, lines, line_height):
        x = element.attrib.get("x", "0")
        element.text = None
        for i, line in enumerate(lines):
            span = ET.SubElement(
                element,
                f"{{{namespace}}}tspan",
                x=x,
                dy="0" if i == 0 else str(line_height),
            )
            span.text = line

    parts = title.split(" | ", 2)
    heading, subtitle = (
        " | ".join(parts[:2]),
        parts[2] if len(parts) > 2 else "",
    )
    heading_lines = textwrap.wrap(heading, max(20, int((width - 48) / 19)))
    subtitle_lines = textwrap.wrap(subtitle, max(20, int((width - 48) / 12)))
    heading_height = 40 * len(heading_lines)
    subtitle_height = 27 * len(subtitle_lines)
    column_height = 100 if columns else 0
    header_height = 32 + heading_height + subtitle_height + column_height
    wrapper = ET.Element(
        f"{{{namespace}}}svg",
        width=str(width),
        height=str(height + header_height + bottom_padding),
        viewBox=f"0 0 {width} {height + header_height + bottom_padding}",
        role="img",
        attrib={"aria-label": title},
    )
    ET.SubElement(wrapper, f"{{{namespace}}}title").text = title
    for lines, y, size, step, weight in [
        (heading_lines, 36, 28 * TEXT_SCALE, 40, "bold"),
        (subtitle_lines, 36 + heading_height, 18 * TEXT_SCALE, 27, "normal"),
    ]:
        label = ET.SubElement(
            wrapper,
            f"{{{namespace}}}text",
            x=str(width / 2),
            y=str(y),
            attrib={
                "text-anchor": "middle",
                "font-family": "Arial, sans-serif",
                "font-size": f"{size:g}",
                "font-weight": weight,
                "fill": "#222222",
                "stroke": "white",
                "stroke-width": "3",
                "paint-order": "stroke",
                "stroke-linejoin": "round",
            },
        )
        multiline(label, lines, step)
    if columns:
        if len(node_x) != len(columns):
            node_x = [width * i / len(columns) for i in range(len(columns))]
        headings = ET.SubElement(
            wrapper, f"{{{namespace}}}g", attrib={"class": "stage-headings"}
        )
        for (_, heading), x in zip(columns, node_x):
            label = ET.SubElement(
                headings,
                f"{{{namespace}}}text",
                x=str(x + 16),
                y=str(header_height - column_height + 30),
                attrib={
                    "font-family": "Arial, sans-serif",
                    "font-size": "23",
                    "font-weight": "bold",
                    "fill": "#222222",
                    "stroke": "white",
                    "stroke-width": "3",
                    "paint-order": "stroke",
                },
            )
            multiline(label, textwrap.wrap(heading, 23), 28)
    for group in diagram.findall(f'.//{{{namespace}}}g[@class="node-labels"]'):
        group.set("font-size", f"{NODE_FONT_SIZE:g}")
        group.set("font-weight", "bold")
        for label in group:
            original = label.text or ""
            visible = original
            for prefix, _ in columns or []:
                if visible.startswith(prefix):
                    visible = visible.removeprefix(prefix)
                    break
            match = re.fullmatch(r"(.*) (\([\d,]+; [\d.]+%\))", visible)
            category, values = match.groups() if match else (visible, None)
            lines = textwrap.wrap(
                category,
                LABEL_WIDTH,
                break_long_words=True,
                break_on_hyphens=False,
            )
            if values:
                lines.append(values)
            if not lines:
                continue
            # Put terminal labels on the right, away from the preceding stage.
            if label.attrib.get("text-anchor") == "end":
                label.set("x", str(float(label.attrib["x"]) + 22))
                label.set("text-anchor", "start")
            label.attrib.pop("dy", None)
            label.set(
                "y",
                str(
                    float(label.attrib.get("y", 0))
                    - (len(lines) - 1) * NODE_LINE_HEIGHT / 2
                    + 7
                ),
            )
            multiline(label, lines, NODE_LINE_HEIGHT)
            ET.SubElement(label, f"{{{namespace}}}title").text = original
    # Normal blending preserves the blue palette across SVG rasterizers.
    for group in diagram.findall(f'.//{{{namespace}}}g[@class="link"]'):
        group.set("style", "mix-blend-mode: normal;")
    for group in diagram.findall(f'.//{{{namespace}}}g[@class="links"]'):
        group.set("stroke-opacity", "0.75")
    # Mermaid puts labels before links, allowing links to cover text.
    # Keep outlined labels above flows without changing geometry.
    for parent in diagram.iter():
        for child in list(parent):
            if child.attrib.get("class") == "node-labels":
                parent.remove(child)
                parent.append(child)
    diagram.set("x", "0")
    diagram.set("y", str(header_height))
    diagram.set("width", str(width))
    diagram.set("height", str(height))
    wrapper.append(diagram)
    return ET.tostring(wrapper, encoding="unicode")


def render_sankey(flows, source, png, title):
    svg = png.with_suffix(".svg")
    if flows.empty:
        source.unlink(missing_ok=True)
        png.unlink(missing_ok=True)
        svg.unlink(missing_ok=True)
        return "Empty prescription cohort; no Sankey generated."
    write_text(source, mermaid_source(flows, title))
    # Stage both formats so rendering/conversion errors preserve the prior PNG.
    with TemporaryDirectory(prefix=".title-", dir=source.parent) as directory:
        staged_svg, staged_png = (
            Path(directory) / "diagram.svg",
            Path(directory) / "diagram.png",
        )
        subprocess.run(
            [
                sys.executable,
                str(RENDERER),
                str(source),
                "-o",
                str(staged_svg),
            ],
            cwd=ROOT,
            check=True,
        )
        titled_svg = add_title(
            staged_svg.read_text(),
            title,
            flows.attrs.get("columns"),
            flows.attrs.get("bottom_padding", 0),
        )
        write_text(staged_svg, titled_svg)
        subprocess.run(
            [
                "docker",
                "run",
                "--rm",
                "--user",
                f"{os.getuid()}:{os.getgid()}",
                "--env",
                "HOME=/tmp",
                "--env",
                "XDG_CACHE_HOME=/tmp",
                "-v",
                f"{SVG_RASTERIZER.parent}:/scripts:ro",
                "-v",
                f"{Path(directory).resolve()}:/work",
                "--entrypoint",
                "node",
                "minlag/mermaid-cli:latest",
                "/scripts/render_sankey_svg.cjs",
                "/work/diagram.svg",
                "/work/diagram.png",
            ],
            cwd=ROOT,
            check=True,
        )
        if not staged_png.is_file() or staged_png.stat().st_size == 0:
            raise ValueError("browser export did not produce a nonempty PNG")
        staged_svg.replace(svg)
        staged_png.replace(png)
    return (
        f"Diagram: {png.relative_to(ROOT)}. Mermaid source: "
        f"{source.relative_to(ROOT)}."
    )

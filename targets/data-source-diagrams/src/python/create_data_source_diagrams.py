"""
Local-only report join documentation; render with the repository Mermaid
helper.
"""

import subprocess
import sys
from pathlib import Path

import pandas as pd

from shared.python.markdown_tables import markdown_table, write_text
from shared.python.paths import artifact_path, repository_root

ROOT = repository_root()
OUTPUT = artifact_path(ROOT / "outputs/diagrams/data-source-connections")
RENDERER = artifact_path(
    ROOT / ".agents/skills/mermaid-diagrams/scripts/render.py"
)
STYLE = (
    '%%{init: {"theme": "base", "themeVariables": {"fontSize": '
    '"18px", "primaryTextColor": "#172b4d", "lineColor": "#456078", '
    '"edgeLabelBackground": "#f2f5f9"}, "flowchart": {"htmlLabels": '
    'true, "useMaxWidth": false, "nodeSpacing": 25, "rankSpacing": '
    "35}}}%%\nflowchart TB\nclassDef physical "
    "fill:#e3f2fd,stroke:#235789,stroke-width:2px;\nclassDef "
    "derived fill:#fff2d5,stroke:#9b6916,stroke-dasharray:5 3;\n"
)

# Only relationships used by the current main.tex include tree are represented.
# Arrows feed a derived result; LEFT/INNER labels describe the implemented
# join.
DIAGRAM_TARGETS = {
    "overview": "report-source-overview",
    "upload-verification": "upload-verification-joins",
    "prescription-first-order": "prescription-first-order-joins",
    "financial-reorder-contact": "financial-reorder-contact-joins",
    "contact-matching": "contact-matching-rules",
}
DIAGRAMS = {
    name: (
        artifact_path(
            ROOT / "targets" / target / "src/mermaid/connections.mmd"
        )
    ).read_text()
    for name, target in DIAGRAM_TARGETS.items()
}

GRAINS = [
    (
        "HCDM.RXP_UPLOAD_ENTITY",
        "Physical upload row; UPLOAD_ID checked for entity analyses",
        (
            "RX_ID may contain multiple prescriptions; ORDER_ID is a separate "
            "association"
        ),
    ),
    (
        "RXP_NOTIFICATION_SERVICE.UPLOAD_ENTITY",
        "Physical upload row; UPLOAD_ID checked in linked-order analyses",
        (
            "ASSOCIATED_RESOURCE_IDS array/list; context:orderId and "
            "context:orderItemId"
        ),
    ),
    (
        "HCDM.RXP_PRESCRIPTIONS",
        (
            "Prescription RX_ID; uniqueness or repeated-value consistency "
            "checked per analysis"
        ),
        "CUSTOMER_ID and FIRST_ORDER_ID + FIRST_ORDERITEM_ID",
    ),
    (
        "HCDM.ORDER_LINE_COST_MEASURES_RXP",
        (
            "Shipment x physical order line: ORDER_ID + ORDER_LINE_ID + "
            "SHIPMENT_KEY"
        ),
        "RX_ID, CUSTOMER_ID, PET_ID, PRODUCT_PART_NUMBER",
    ),
    (
        "ECOM.ORDERS",
        "Order header ORDER_ID; uniqueness / consistent duplicates checked",
        "CUSTOMER_ID, ORDER_PLACED_DTTM",
    ),
    (
        "ECOM.ORDER_LINE",
        "Physical order line ORDER_ID + ORDER_LINE_ID",
        "CUSTOMER_ID; NET_SALES is the full line amount",
    ),
    (
        "BT_CUSTOMER_CARE.FCT_CONTACTS_BRD",
        "Contact leg/session evidence; repeats possible",
        "ORDER_ID, CUSTOMER_ID, SESSION_ID, LEG_ID, SESSION_START_DTTM",
    ),
]


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    for name, body in DIAGRAMS.items():
        source = artifact_path(OUTPUT / f"{name}.mmd")
        png = source.with_suffix(".png")
        (
            STYLE.replace("flowchart TB", "flowchart LR")
            if name in {"overview", "contact-matching"}
            else STYLE
        )
        definition = body
        if not source.exists() or source.read_text() != definition:
            write_text(source, definition)
        if not png.exists() or png.stat().st_mtime < max(
            source.stat().st_mtime,
            Path(__file__).stat().st_mtime,
            RENDERER.stat().st_mtime,
        ):
            subprocess.run(
                [sys.executable, str(RENDERER), str(source), "-o", str(png)],
                check=True,
            )
    tables = artifact_path(ROOT / "outputs/tables/data-source-connections")
    tables.mkdir(parents=True, exist_ok=True)
    write_text(
        tables / "source-grains.md",
        "# Report source grains\n\n"
        "All sources resolve in EDLDB; HCDM means BT_HCA_HCDM. "
        "These are analytical keys, not asserted database constraints.\n\n"
        + markdown_table(
            pd.DataFrame(
                GRAINS, columns=["Source", "Grain / checks", "Matching fields"]
            )
        )
        + "\n",
    )


if __name__ == "__main__":
    main()

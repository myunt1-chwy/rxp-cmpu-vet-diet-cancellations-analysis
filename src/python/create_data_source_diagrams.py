"""Local-only report join documentation; render with the repository Mermaid helper."""

from pathlib import Path
import subprocess
import sys

import pandas as pd

from src.python.markdown_tables import markdown_table, write_text

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / 'outputs/diagrams/data-source-connections'
RENDERER = ROOT / '.agents/skills/mermaid-diagrams/scripts/render.py'
STYLE = '''%%{init: {"theme": "base", "themeVariables": {"fontSize": "18px", "primaryTextColor": "#172b4d", "lineColor": "#456078", "edgeLabelBackground": "#f2f5f9"}, "flowchart": {"htmlLabels": true, "useMaxWidth": false, "nodeSpacing": 25, "rankSpacing": 35}}}%%
flowchart TB
classDef physical fill:#e3f2fd,stroke:#235789,stroke-width:2px;
classDef derived fill:#fff2d5,stroke:#9b6916,stroke-dasharray:5 3;
'''

# Only relationships used by the current main.tex include tree are represented.
# Arrows feed a derived result; LEFT/INNER labels describe the implemented join.
DIAGRAMS = {
    'contact-matching': '''
subgraph cohort["1. Aged-order cohort - SQL"]
direction TB
P["EDLDB.BT_HCA_HCDM.<br/>RXP_PRESCRIPTIONS p"]:::physical
L["EDLDB.BT_HCA_HCDM.<br/>ORDER_LINE_COST_MEASURES_RXP l"]:::physical
A["Eligible lines<br/>Both vet-diet flags TRUE;<br/>p.PRESCRIPTION_SOURCE = CMPU;<br/>p.APPROVAL_CHANNEL = CUSTOMER_UPLOAD;<br/>LOWER TRIM l.ORDER_CANCEL_REASON = aged order;<br/>ORDER_CANCEL_DTTM in [start_date,end_date)"]:::derived
O["aged_orders a: one row per ORDER_ID<br/>MIN CUSTOMER_ID and ORDER_CANCEL_DTTM;<br/>validate customer / cancellation consistency"]:::derived
P -->|"p.RX_ID = NULLIF TRIM l.RX_ID<br/>AND p.CUSTOMER_ID = l.CUSTOMER_ID"| A
L -->|"INNER JOIN; fetch all shipment rows<br/>for qualifying ORDER_ID + ORDER_LINE_ID"| A
A -->|"GROUP BY ORDER_ID"| O
end
subgraph matching["2. Contact matching - SQL"]
direction TB
C["EDLDB.BT_CUSTOMER_CARE.<br/>FCT_CONTACTS_BRD c<br/>Contact legs / sessions"]:::physical
J["aged_orders a LEFT JOIN contacts c<br/>ON a.ORDER_ID = c.ORDER_ID<br/>AND (SESSION_START_DTTM in<br/>cancellation [-13,+4) days<br/>OR SESSION_START_DTTM IS NULL)"]:::derived
V["Preserve all aged orders;<br/>retain unmatched orders and<br/>NULL-time contacts for auditing.<br/>Customer equality is checked in Python."]:::derived
C -->|"ORDER_ID and time conditions"| J
J --> V
end
subgraph counting["3. Validation and counting - Python"]
direction TB
F["Normalize numeric IDs; validate order equality.<br/>Check known SESSION_ID / LEG_ID conflicts;<br/>collapse exact duplicate rows.<br/>Include only nonmissing matching CUSTOMER_ID,<br/>LOWER TRIM SESSION_INITIAL_DIRECTION = inbound,<br/>and populated SESSION_START_DTTM.<br/>All handled states included by default."]:::derived
D["Daily counts: relative_day = FLOOR elapsed UTC days;<br/>distinct CUSTOMER_ID and ORDER_ID per day -13 to +3.<br/>No leg/session counting."]:::derived
G["Frequency: distinct relative_day per CUSTOMER_ID,<br/>pooled across that customer's aged orders.<br/>LEFT JOIN all aged customers; absent days = 0.<br/>Excluded contacts remain audited."]:::derived
F --> D
F --> G
end
cohort -->|"aged_orders a"| matching
matching -->|"extracted order/contact rows"| counting
''',
    'overview': '''
U["HCDM.RXP_UPLOAD_ENTITY<br/>notification_service.UPLOAD_ENTITY"]:::physical
P["HCDM.RXP_PRESCRIPTIONS"]:::physical
L["HCDM.ORDER_LINE_COST_MEASURES_RXP"]:::physical
O["ECOM.ORDERS / ECOM.ORDER_LINE<br/>BT_CUSTOMER_CARE.FCT_CONTACTS_BRD"]:::physical
V["Upload verification<br/>source entries, RX coverage, order reasons"]:::derived
S["Study population, Sankey, survival,<br/>document upload and approval figures"]:::derived
F["Financial opportunity, reorders,<br/>first observed order cohorts and contacts"]:::derived
U -->|"expanded RX_ID or ASSOCIATED_RESOURCE_IDS;<br/>ORDER_ID or context:orderId"| V
P -->|"RX_ID only for registry verification"| V
O -->|"ORDERS.ORDER_ID = numeric upload order ID"| V
P -->|"FIRST_ORDER_ID; numeric FIRST_ORDERITEM_ID"| S
L -->|"ORDER_ID + ORDER_LINE_ID"| S
U -->|"expanded RX_ID + numeric CUSTOMER_ID"| S
P -->|"RX_ID + CUSTOMER_ID eligibility"| F
L -->|"TRIM RX_ID; physical lines and shipments"| F
O -->|"ORDER_ID for chronology / contacts;<br/>CUSTOMER_ID for Chewy follow-up"| F
''',
    'upload-verification': '''
H["EDLDB.BT_HCA_HCDM.RXP_UPLOAD_ENTITY<br/>RX_ID; ORDER_ID; CREATED_TS_UTC"]:::physical
N["EDLDB.RXP_NOTIFICATION_SERVICE.UPLOAD_ENTITY<br/>ASSOCIATED_RESOURCE_IDS; context; CREATED_AT"]:::physical
I["Distinct source_table + rx_id<br/>TRANSLATE delimiters/quotes, SPLIT, FLATTEN,<br/>TRIM; exclude blank, null and numeric zero"]:::derived
P["EDLDB.BT_HCA_HCDM.RXP_PRESCRIPTIONS<br/>TRIM RX_ID; IS_VET_DIET_FLAG;<br/>APPROVAL_CHANNEL; PRESCRIPTION_SOURCE; RX_STATUS"]:::physical
R["Channel distribution: IDs LEFT JOIN registry<br/>Coverage: eligible registry LEFT JOIN each ID set<br/>Join on rx_id only; no customer check"]:::derived
D["Distinct source_table + numeric order_id<br/>DIET_PRESCRIPTION: ORDER_ID / context:orderId<br/>NULL resource: notification context:orderId only"]:::derived
O["EDLDB.ECOM.ORDERS<br/>ORDER_ID; ORDER_CANCEL_REASON;<br/>ORDER_STATUS_DESCRIPTION; ORDER_STATUS"]:::physical
C["Source-order LEFT JOIN order extract in Python<br/>One count per source / order ID;<br/>unmatched orders and SQL NULL reason separate"]:::derived
H -->|"RX_ID tokens"| I
N -->|"TO_JSON ASSOCIATED_RESOURCE_IDS tokens"| I
I -->|"rx_id = TRIM registry RX_ID"| R
P -->|"vet-diet channel / coverage cohorts"| R
H -->|"digits-only ORDER_ID to TRY_TO_NUMBER"| D
N -->|"digits-only context:orderId to TRY_TO_NUMBER"| D
D -->|"extract INNER: ids.order_id = ORDERS.ORDER_ID"| O
D -->|"LEFT on normalized order_id"| C
O -->|"unique ORDER_ID checked before merge"| C
''',
    'prescription-first-order': '''
P["EDLDB.BT_HCA_HCDM.RXP_PRESCRIPTIONS<br/>RX_ID; CUSTOMER_ID; FIRST_ORDER_ID;<br/>FIRST_ORDERITEM_ID; decision evidence"]:::physical
L["EDLDB.BT_HCA_HCDM.ORDER_LINE_COST_MEASURES_RXP<br/>ORDER_ID; ORDER_LINE_ID; SHIPMENT_KEY;<br/>placement, cancellation and approval times"]:::physical
A["First-order prescription / line associations<br/>digits-only TRIM FIRST_ORDERITEM_ID<br/>to TRY_TO_NUMBER = first_order_line_id"]:::derived
U["EDLDB.BT_HCA_HCDM.RXP_UPLOAD_ENTITY<br/>UPLOAD_ID; RX_ID list; CUSTOMER_ID;<br/>CREATED_TS_UTC; STATE_CHANGED_TS_UTC"]:::physical
E["Expanded upload / prescription matches<br/>SPLIT / FLATTEN RX_ID; TRIM tokens;<br/>digits-only CUSTOMER_ID to TRY_TO_NUMBER"]:::derived
T["Sankey / approval / event-time evidence<br/>ACCEPTED; rank per RX_ID + CUSTOMER_ID<br/>by CREATED_TS_UTC, UPLOAD_ID"]:::derived
G["Document counts / entity figures<br/>all current states; discover then fetch all versions;<br/>validate and count each UPLOAD_ID once"]:::derived
P -->|"LEFT JOIN lines on FIRST_ORDER_ID = ORDER_ID<br/>AND first_order_line_id = ORDER_LINE_ID<br/>decision extract uses INNER JOIN"| A
L -->|"GROUP BY ORDER_ID, ORDER_LINE_ID;<br/>validate shipment attribute consistency"| A
U -->|"UPLOAD_TYPE = DIET_PRESCRIPTION;<br/>discovery by creation window"| E
P -->|"RX_ID = expanded token<br/>AND CUSTOMER_ID = numeric upload CUSTOMER_ID"| E
E -->|"earliest created accepted entity;<br/>use its STATE_CHANGED_TS_UTC"| T
A -->|"LEFT on RX_ID + CUSTOMER_ID;<br/>collapse distinct physical lines downstream"| T
E -->|"match first-order keys; entity grain"| G
A -->|"ORDER_ID + ORDER_LINE_ID;<br/>earliest matched placement per entity"| G
''',
    'financial-reorder-contact': '''
P["EDLDB.BT_HCA_HCDM.RXP_PRESCRIPTIONS"]:::physical
L["EDLDB.BT_HCA_HCDM.ORDER_LINE_COST_MEASURES_RXP"]:::physical
A["Eligible CMPU vet-diet CUSTOMER_UPLOAD lines<br/>baseline: shipped/cancelled reporting window;<br/>aged anchors: cancellation window"]:::derived
O["EDLDB.ECOM.ORDERS"]:::physical
H["First observed vet-diet / CUSTOMER_UPLOAD order<br/>per CUSTOMER_ID: ORDER_PLACED_DTTM, ORDER_ID;<br/>exclude ambiguous earliest-time ties / missing history"]:::derived
R["RxP reorder candidates (LEFT from originals)<br/>same CUSTOMER_ID; different ORDER_ID;<br/>same PET_ID + PRODUCT_PART_NUMBER,<br/>or same pet / different part, or any vet diet"]:::derived
C["EDLDB.BT_CUSTOMER_CARE.FCT_CONTACTS_BRD"]:::physical
J["Aged orders LEFT JOIN contacts on ORDER_ID<br/>SESSION_START_DTTM in cancellation [-13,+4) days;<br/>Python: numeric CUSTOMER_ID equality + inbound"]:::derived
E["EDLDB.ECOM.ORDER_LINE"]:::physical
Q["Any Chewy follow-up (LEFT from originals)<br/>CUSTOMER_ID only; different ORDER_ID;<br/>NET_SALES once per physical line"]:::derived
Z["Customer outcomes and contact segments<br/>each cancellation has its own (0,N] day window;<br/>placement at or before as_of; distinct customer/order counts"]:::derived
P -->|"registry grouped by RX_ID; validate variants"| A
L -->|"TRIM line RX_ID = registry RX_ID;<br/>CUSTOMER_ID equality in SQL or baseline Python"| A
A -->|"anchor CUSTOMER_ID selects customer history"| H
L -->|"history CUSTOMER_ID = anchor CUSTOMER_ID;<br/>vet-diet lines; upload subset via registry"| H
O -->|"ORDER_ID = history ORDER_ID;<br/>also require matching CUSTOMER_ID"| H
A -->|"original CUSTOMER_ID / PET_ID / PRODUCT_PART_NUMBER"| R
L -->|"reorder keys; SUM sales per distinct<br/>ORDER_ID + ORDER_LINE_ID + SHIPMENT_KEY"| R
A -->|"GROUP BY ORDER_ID; cancellation time"| J
C -->|"contact ORDER_ID = aged ORDER_ID;<br/>customer check after extraction"| J
A -->|"original CUSTOMER_ID + cancellation time"| Q
E -->|"reorder CUSTOMER_ID = original CUSTOMER_ID"| Q
H -->|"first-order cohorts restrict original anchors"| Z
R -->|"ORDER_PLACED_DTTM after cancellation;<br/>whole-order cancellation/status exclusions"| Z
Q -->|"same time window; whole-order exclusions"| Z
J -->|"distinct relative days per CUSTOMER_ID;<br/>join reorder outcomes by CUSTOMER_ID"| Z
''',
}

GRAINS = [
    ('HCDM.RXP_UPLOAD_ENTITY', 'Physical upload row; UPLOAD_ID checked for entity analyses', 'RX_ID may contain multiple prescriptions; ORDER_ID is a separate association'),
    ('RXP_NOTIFICATION_SERVICE.UPLOAD_ENTITY', 'Physical upload row; UPLOAD_ID checked in linked-order analyses', 'ASSOCIATED_RESOURCE_IDS array/list; context:orderId and context:orderItemId'),
    ('HCDM.RXP_PRESCRIPTIONS', 'Prescription RX_ID; uniqueness or repeated-value consistency checked per analysis', 'CUSTOMER_ID and FIRST_ORDER_ID + FIRST_ORDERITEM_ID'),
    ('HCDM.ORDER_LINE_COST_MEASURES_RXP', 'Shipment x physical order line: ORDER_ID + ORDER_LINE_ID + SHIPMENT_KEY', 'RX_ID, CUSTOMER_ID, PET_ID, PRODUCT_PART_NUMBER'),
    ('ECOM.ORDERS', 'Order header ORDER_ID; uniqueness / consistent duplicates checked', 'CUSTOMER_ID, ORDER_PLACED_DTTM'),
    ('ECOM.ORDER_LINE', 'Physical order line ORDER_ID + ORDER_LINE_ID', 'CUSTOMER_ID; NET_SALES is the full line amount'),
    ('BT_CUSTOMER_CARE.FCT_CONTACTS_BRD', 'Contact leg/session evidence; repeats possible', 'ORDER_ID, CUSTOMER_ID, SESSION_ID, LEG_ID, SESSION_START_DTTM'),
]


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    for name, body in DIAGRAMS.items():
        source = OUTPUT / f'{name}.mmd'
        png = source.with_suffix('.png')
        style = STYLE.replace('flowchart TB', 'flowchart LR') if name in {'overview', 'contact-matching'} else STYLE
        definition = style + body.strip() + '\n'
        if not source.exists() or source.read_text() != definition:
            write_text(source, definition)
        if not png.exists() or png.stat().st_mtime < max(
            source.stat().st_mtime, Path(__file__).stat().st_mtime, RENDERER.stat().st_mtime
        ):
            subprocess.run([sys.executable, str(RENDERER), str(source), '-o', str(png)], check=True)
    tables = ROOT / 'outputs/tables/data-source-connections'
    tables.mkdir(parents=True, exist_ok=True)
    write_text(tables / 'source-grains.md', '# Report source grains\n\n'
               'All sources resolve in EDLDB; HCDM means BT_HCA_HCDM. '
               'These are analytical keys, not asserted database constraints.\n\n'
               + markdown_table(pd.DataFrame(GRAINS, columns=['Source', 'Grain / checks', 'Matching fields'])) + '\n')


if __name__ == '__main__':
    main()

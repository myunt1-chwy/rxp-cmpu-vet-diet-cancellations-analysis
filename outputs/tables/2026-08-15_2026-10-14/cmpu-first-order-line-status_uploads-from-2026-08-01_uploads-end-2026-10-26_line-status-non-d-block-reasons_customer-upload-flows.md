# Customer-Upload-Flows

Prescription creation 2026-08-15 inclusive to 2026-10-15 exclusive UTC; uploads 2026-08-01 inclusive to 2026-10-26 exclusive UTC. Extracted 2026-10-27T20:35:13.241892+00:00.

Source: EDLDB.BT_HCA_HCDM.ORDER_LINE_COST_MEASURES_RXP. Join FIRST_ORDER_ID = ORDER_ID AND numeric FIRST_ORDERITEM_ID = ORDER_LINE_ID; no RX_ID join to the order-line view. Each matched (ORDER_ID, ORDER_LINE_ID) is counted once, collapsing shipment rows. Prescriptions without usable first-order keys or without a matching line are excluded from the Sankey denominators and reported in the audit. The status stage uses the latest raw ORDER_ORDER_LINE_STATUS codes directly; blank/null statuses are explicit. ORDER_ITEM_BLOCK_REASON is retained in data and tables but omitted from diagrams. Its grouped classification is populated for known non-D statuses, with explicit not-applicable values for D/unknown. Blank/null reasons are labeled [No block reason recorded], which does not independently establish an unblocked item. All figures show line status followed by raw ORDER_CANCEL_REASON; order status is retained only in data. Blank/null cancellation reasons are labeled [No cancellation reason recorded]; this does not establish whether the overall order was canceled. Multiple prescriptions sharing a line are counted once; conflicting classifications fail validation. Upload matching retains the DIET_PRESCRIPTION expanded RX_ID + numeric CUSTOMER_ID rules, without file/association flags, prescription-status/deletion filters or upload-after-creation requirement. A matching entity does not verify file presence. Approval channel → line status → cancellation reason → upload presence is a categorical breakdown, not a chronological journey. Full percentages use all matched distinct lines; focused percentages use matched distinct CUSTOMER_UPLOAD lines. The separate non-D figure uses only known non-D CUSTOMER_UPLOAD lines as its denominator. Upload endpoints separate lines with a recorded cancellation reason from lines without one, each split into has/no matching upload. Blank/null/whitespace reasons mean no recorded reason, not proof of an uncanceled order. All three figures include the explicit line-status column. Column headers identify stages; visible node labels omit repeated stage prefixes. Percentages retain the whole-figure denominator.

| transition | source | target | order_lines | percent_of_cohort |
| --- | --- | --- | --- | --- |
| 1 | Channel: CUSTOMER_UPLOAD | First order line status: C | 56 | 0.05890396549910592 |
| 1 | Channel: CUSTOMER_UPLOAD | First order line status: D | 29929 | 31.481013989691807 |
| 1 | Channel: CUSTOMER_UPLOAD | First order line status: R | 3 | 0.003155569580309246 |
| 1 | Channel: CUSTOMER_UPLOAD | First order line status: S | 29 | 0.03050383927632271 |
| 1 | Channel: CUSTOMER_UPLOAD | First order line status: X | 65053 | 68.42642263595246 |
| 2 | First order line status: C | First order cancel reason: [No cancellation reason recorded] | 56 | 0.05890396549910592 |
| 2 | First order line status: D | First order cancel reason: [No cancellation reason recorded] | 29929 | 31.481013989691807 |
| 2 | First order line status: R | First order cancel reason: [No cancellation reason recorded] | 3 | 0.003155569580309246 |
| 2 | First order line status: S | First order cancel reason: [No cancellation reason recorded] | 29 | 0.03050383927632271 |
| 2 | First order line status: X | First order cancel reason: Aged Order | 26809 | 28.19922162617019 |
| 2 | First order line status: X | First order cancel reason: Customer Initiated Cancellation | 13123 | 13.803513200799411 |
| 2 | First order line status: X | First order cancel reason: Customer Request | 5486 | 5.770484905858841 |
| 2 | First order line status: X | First order cancel reason: Duplicate Order | 64 | 0.06731881771326391 |
| 2 | First order line status: X | First order cancel reason: Fraud | 15 | 0.015777847901546228 |
| 2 | First order line status: X | First order cancel reason: Inventory Issue | 3 | 0.003155569580309246 |
| 2 | First order line status: X | First order cancel reason: No Response | 575 | 0.6048175028926055 |
| 2 | First order line status: X | First order cancel reason: Other | 336 | 0.35342379299463555 |
| 2 | First order line status: X | First order cancel reason: Payment Declined | 2675 | 2.8137162091090775 |
| 2 | First order line status: X | First order cancel reason: Payment Issue | 17 | 0.017881560955085727 |
| 2 | First order line status: X | First order cancel reason: Pharmacy Rejection | 151 | 0.15883033554223203 |
| 2 | First order line status: X | First order cancel reason: Prescription Issue | 4909 | 5.163563689912696 |
| 2 | First order line status: X | First order cancel reason: Reseller | 1 | 0.0010518565267697486 |
| 2 | First order line status: X | First order cancel reason: [No cancellation reason recorded] | 10889 | 11.453665719995792 |
| 3 | First order cancel reason: Aged Order | Matching upload: With cancellation reason / Has matching upload | 791 | 0.8320185126748711 |
| 3 | First order cancel reason: Aged Order | Matching upload: With cancellation reason / No matching upload | 26018 | 27.367203113495318 |
| 3 | First order cancel reason: Customer Initiated Cancellation | Matching upload: With cancellation reason / Has matching upload | 1158 | 1.2180498579993688 |
| 3 | First order cancel reason: Customer Initiated Cancellation | Matching upload: With cancellation reason / No matching upload | 11965 | 12.585463342800042 |
| 3 | First order cancel reason: Customer Request | Matching upload: With cancellation reason / Has matching upload | 1081 | 1.1370569054380983 |
| 3 | First order cancel reason: Customer Request | Matching upload: With cancellation reason / No matching upload | 4405 | 4.633428000420743 |
| 3 | First order cancel reason: Duplicate Order | Matching upload: With cancellation reason / Has matching upload | 14 | 0.01472599137477648 |
| 3 | First order cancel reason: Duplicate Order | Matching upload: With cancellation reason / No matching upload | 50 | 0.05259282633848743 |
| 3 | First order cancel reason: Fraud | Matching upload: With cancellation reason / No matching upload | 15 | 0.015777847901546228 |
| 3 | First order cancel reason: Inventory Issue | Matching upload: With cancellation reason / No matching upload | 3 | 0.003155569580309246 |
| 3 | First order cancel reason: No Response | Matching upload: With cancellation reason / Has matching upload | 9 | 0.009466708740927737 |
| 3 | First order cancel reason: No Response | Matching upload: With cancellation reason / No matching upload | 566 | 0.5953507941516777 |
| 3 | First order cancel reason: Other | Matching upload: With cancellation reason / Has matching upload | 74 | 0.07783738298096139 |
| 3 | First order cancel reason: Other | Matching upload: With cancellation reason / No matching upload | 262 | 0.2755864100136741 |
| 3 | First order cancel reason: Payment Declined | Matching upload: With cancellation reason / Has matching upload | 15 | 0.015777847901546228 |
| 3 | First order cancel reason: Payment Declined | Matching upload: With cancellation reason / No matching upload | 2660 | 2.7979383612075313 |
| 3 | First order cancel reason: Payment Issue | Matching upload: With cancellation reason / Has matching upload | 1 | 0.0010518565267697486 |
| 3 | First order cancel reason: Payment Issue | Matching upload: With cancellation reason / No matching upload | 16 | 0.016829704428315977 |
| 3 | First order cancel reason: Pharmacy Rejection | Matching upload: With cancellation reason / Has matching upload | 14 | 0.01472599137477648 |
| 3 | First order cancel reason: Pharmacy Rejection | Matching upload: With cancellation reason / No matching upload | 137 | 0.14410434416745557 |
| 3 | First order cancel reason: Prescription Issue | Matching upload: With cancellation reason / Has matching upload | 193 | 0.20300830966656147 |
| 3 | First order cancel reason: Prescription Issue | Matching upload: With cancellation reason / No matching upload | 4716 | 4.960555380246134 |
| 3 | First order cancel reason: Reseller | Matching upload: With cancellation reason / No matching upload | 1 | 0.0010518565267697486 |
| 3 | First order cancel reason: [No cancellation reason recorded] | Matching upload: No cancellation reason / Has matching upload | 26270 | 27.632270958241296 |
| 3 | First order cancel reason: [No cancellation reason recorded] | Matching upload: No cancellation reason / No matching upload | 14636 | 15.39497212580204 |

# Non-D-Flows

Prescription creation 2026-08-15 inclusive to 2026-10-15 exclusive UTC; uploads 2026-08-01 inclusive to 2026-10-26 exclusive UTC. Extracted 2026-10-27T20:35:13.241892+00:00.

Source: EDLDB.BT_HCA_HCDM.ORDER_LINE_COST_MEASURES_RXP. Join FIRST_ORDER_ID = ORDER_ID AND numeric FIRST_ORDERITEM_ID = ORDER_LINE_ID; no RX_ID join to the order-line view. Each matched (ORDER_ID, ORDER_LINE_ID) is counted once, collapsing shipment rows. Prescriptions without usable first-order keys or without a matching line are excluded from the Sankey denominators and reported in the audit. The status stage uses the latest raw ORDER_ORDER_LINE_STATUS codes directly; blank/null statuses are explicit. ORDER_ITEM_BLOCK_REASON is retained in data and tables but omitted from diagrams. Its grouped classification is populated for known non-D statuses, with explicit not-applicable values for D/unknown. Blank/null reasons are labeled [No block reason recorded], which does not independently establish an unblocked item. All figures show line status followed by raw ORDER_CANCEL_REASON; order status is retained only in data. Blank/null cancellation reasons are labeled [No cancellation reason recorded]; this does not establish whether the overall order was canceled. Multiple prescriptions sharing a line are counted once; conflicting classifications fail validation. Upload matching retains the DIET_PRESCRIPTION expanded RX_ID + numeric CUSTOMER_ID rules, without file/association flags, prescription-status/deletion filters or upload-after-creation requirement. A matching entity does not verify file presence. Approval channel → line status → cancellation reason → upload presence is a categorical breakdown, not a chronological journey. Full percentages use all matched distinct lines; focused percentages use matched distinct CUSTOMER_UPLOAD lines. The separate non-D figure uses only known non-D CUSTOMER_UPLOAD lines as its denominator. Upload endpoints separate lines with a recorded cancellation reason from lines without one, each split into has/no matching upload. Blank/null/whitespace reasons mean no recorded reason, not proof of an uncanceled order. All three figures include the explicit line-status column. Column headers identify stages; visible node labels omit repeated stage prefixes. Percentages retain the whole-figure denominator.

| transition | source | target | order_lines | percent_of_cohort |
| --- | --- | --- | --- | --- |
| 1 | Channel: CUSTOMER_UPLOAD | First order line status: C | 56 | 0.08596736310464992 |
| 1 | Channel: CUSTOMER_UPLOAD | First order line status: R | 3 | 0.004605394452034817 |
| 1 | Channel: CUSTOMER_UPLOAD | First order line status: S | 29 | 0.04451881303633656 |
| 1 | Channel: CUSTOMER_UPLOAD | First order line status: X | 65053 | 99.86490842940698 |
| 2 | First order line status: C | First order cancel reason: [No cancellation reason recorded] | 56 | 0.08596736310464992 |
| 2 | First order line status: R | First order cancel reason: [No cancellation reason recorded] | 3 | 0.004605394452034817 |
| 2 | First order line status: S | First order cancel reason: [No cancellation reason recorded] | 29 | 0.04451881303633656 |
| 2 | First order line status: X | First order cancel reason: Aged Order | 26809 | 41.15533995486714 |
| 2 | First order line status: X | First order cancel reason: Customer Initiated Cancellation | 13123 | 20.1455304646843 |
| 2 | First order line status: X | First order cancel reason: Customer Request | 5486 | 8.421731321287668 |
| 2 | First order line status: X | First order cancel reason: Duplicate Order | 64 | 0.09824841497674276 |
| 2 | First order line status: X | First order cancel reason: Fraud | 15 | 0.023026972260174083 |
| 2 | First order line status: X | First order cancel reason: Inventory Issue | 3 | 0.004605394452034817 |
| 2 | First order line status: X | First order cancel reason: No Response | 575 | 0.8827006033066732 |
| 2 | First order line status: X | First order cancel reason: Other | 336 | 0.5158041786278995 |
| 2 | First order line status: X | First order cancel reason: Payment Declined | 2675 | 4.106476719731045 |
| 2 | First order line status: X | First order cancel reason: Payment Issue | 17 | 0.026097235228197294 |
| 2 | First order line status: X | First order cancel reason: Pharmacy Rejection | 151 | 0.23180485408575244 |
| 2 | First order line status: X | First order cancel reason: Prescription Issue | 4909 | 7.5359604550129715 |
| 2 | First order line status: X | First order cancel reason: Reseller | 1 | 0.0015351314840116057 |
| 2 | First order line status: X | First order cancel reason: [No cancellation reason recorded] | 10889 | 16.716046729402372 |
| 3 | First order cancel reason: Aged Order | Matching upload: With cancellation reason / Has matching upload | 791 | 1.21428900385318 |
| 3 | First order cancel reason: Aged Order | Matching upload: With cancellation reason / No matching upload | 26018 | 39.941050951013956 |
| 3 | First order cancel reason: Customer Initiated Cancellation | Matching upload: With cancellation reason / Has matching upload | 1158 | 1.7776822584854393 |
| 3 | First order cancel reason: Customer Initiated Cancellation | Matching upload: With cancellation reason / No matching upload | 11965 | 18.36784820619886 |
| 3 | First order cancel reason: Customer Request | Matching upload: With cancellation reason / Has matching upload | 1081 | 1.6594771342165457 |
| 3 | First order cancel reason: Customer Request | Matching upload: With cancellation reason / No matching upload | 4405 | 6.762254187071123 |
| 3 | First order cancel reason: Duplicate Order | Matching upload: With cancellation reason / Has matching upload | 14 | 0.02149184077616248 |
| 3 | First order cancel reason: Duplicate Order | Matching upload: With cancellation reason / No matching upload | 50 | 0.07675657420058028 |
| 3 | First order cancel reason: Fraud | Matching upload: With cancellation reason / No matching upload | 15 | 0.023026972260174083 |
| 3 | First order cancel reason: Inventory Issue | Matching upload: With cancellation reason / No matching upload | 3 | 0.004605394452034817 |
| 3 | First order cancel reason: No Response | Matching upload: With cancellation reason / Has matching upload | 9 | 0.01381618335610445 |
| 3 | First order cancel reason: No Response | Matching upload: With cancellation reason / No matching upload | 566 | 0.8688844199505688 |
| 3 | First order cancel reason: Other | Matching upload: With cancellation reason / Has matching upload | 74 | 0.11359972981685881 |
| 3 | First order cancel reason: Other | Matching upload: With cancellation reason / No matching upload | 262 | 0.40220444881104067 |
| 3 | First order cancel reason: Payment Declined | Matching upload: With cancellation reason / Has matching upload | 15 | 0.023026972260174083 |
| 3 | First order cancel reason: Payment Declined | Matching upload: With cancellation reason / No matching upload | 2660 | 4.083449747470871 |
| 3 | First order cancel reason: Payment Issue | Matching upload: With cancellation reason / Has matching upload | 1 | 0.0015351314840116057 |
| 3 | First order cancel reason: Payment Issue | Matching upload: With cancellation reason / No matching upload | 16 | 0.02456210374418569 |
| 3 | First order cancel reason: Pharmacy Rejection | Matching upload: With cancellation reason / Has matching upload | 14 | 0.02149184077616248 |
| 3 | First order cancel reason: Pharmacy Rejection | Matching upload: With cancellation reason / No matching upload | 137 | 0.21031301330958996 |
| 3 | First order cancel reason: Prescription Issue | Matching upload: With cancellation reason / Has matching upload | 193 | 0.2962803764142399 |
| 3 | First order cancel reason: Prescription Issue | Matching upload: With cancellation reason / No matching upload | 4716 | 7.239680078598732 |
| 3 | First order cancel reason: Reseller | Matching upload: With cancellation reason / No matching upload | 1 | 0.0015351314840116057 |
| 3 | First order cancel reason: [No cancellation reason recorded] | Matching upload: No cancellation reason / Has matching upload | 1321 | 2.027908690379331 |
| 3 | First order cancel reason: [No cancellation reason recorded] | Matching upload: No cancellation reason / No matching upload | 9656 | 14.823229609616064 |

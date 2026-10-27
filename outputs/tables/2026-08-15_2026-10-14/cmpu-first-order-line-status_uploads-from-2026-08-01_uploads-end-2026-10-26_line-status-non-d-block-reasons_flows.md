# Flows

Prescription creation 2026-08-15 inclusive to 2026-10-15 exclusive UTC; uploads 2026-08-01 inclusive to 2026-10-26 exclusive UTC. Extracted 2026-10-27T20:35:13.241892+00:00.

Source: EDLDB.BT_HCA_HCDM.ORDER_LINE_COST_MEASURES_RXP. Join FIRST_ORDER_ID = ORDER_ID AND numeric FIRST_ORDERITEM_ID = ORDER_LINE_ID; no RX_ID join to the order-line view. Each matched (ORDER_ID, ORDER_LINE_ID) is counted once, collapsing shipment rows. Prescriptions without usable first-order keys or without a matching line are excluded from the Sankey denominators and reported in the audit. The status stage uses the latest raw ORDER_ORDER_LINE_STATUS codes directly; blank/null statuses are explicit. ORDER_ITEM_BLOCK_REASON is retained in data and tables but omitted from diagrams. Its grouped classification is populated for known non-D statuses, with explicit not-applicable values for D/unknown. Blank/null reasons are labeled [No block reason recorded], which does not independently establish an unblocked item. All figures show line status followed by raw ORDER_CANCEL_REASON; order status is retained only in data. Blank/null cancellation reasons are labeled [No cancellation reason recorded]; this does not establish whether the overall order was canceled. Multiple prescriptions sharing a line are counted once; conflicting classifications fail validation. Upload matching retains the DIET_PRESCRIPTION expanded RX_ID + numeric CUSTOMER_ID rules, without file/association flags, prescription-status/deletion filters or upload-after-creation requirement. A matching entity does not verify file presence. Approval channel → line status → cancellation reason → upload presence is a categorical breakdown, not a chronological journey. Full percentages use all matched distinct lines; focused percentages use matched distinct CUSTOMER_UPLOAD lines. The separate non-D figure uses only known non-D CUSTOMER_UPLOAD lines as its denominator. Upload endpoints separate lines with a recorded cancellation reason from lines without one, each split into has/no matching upload. Blank/null/whitespace reasons mean no recorded reason, not proof of an uncanceled order. All three figures include the explicit line-status column. Column headers identify stages; visible node labels omit repeated stage prefixes. Percentages retain the whole-figure denominator.

| transition | source | target | order_lines | percent_of_cohort |
| --- | --- | --- | --- | --- |
| 1 | Channel: CLINIC_EMAIL | First order line status: D | 109 | 0.10530078347647155 |
| 1 | Channel: CLINIC_EMAIL | First order line status: X | 53 | 0.05120129838764213 |
| 1 | Channel: CUSTOMER_EMAIL | First order line status: D | 2416 | 2.334006356689498 |
| 1 | Channel: CUSTOMER_EMAIL | First order line status: S | 3 | 0.0028981867011872906 |
| 1 | Channel: CUSTOMER_EMAIL | First order line status: X | 39 | 0.03767642711543478 |
| 1 | Channel: CUSTOMER_UPLOAD | First order line status: C | 56 | 0.054099485088829426 |
| 1 | Channel: CUSTOMER_UPLOAD | First order line status: D | 29929 | 28.913276593278137 |
| 1 | Channel: CUSTOMER_UPLOAD | First order line status: R | 3 | 0.0028981867011872906 |
| 1 | Channel: CUSTOMER_UPLOAD | First order line status: S | 29 | 0.028015804778143808 |
| 1 | Channel: CUSTOMER_UPLOAD | First order line status: X | 65053 | 62.84524649077893 |
| 1 | Channel: FAX | First order line status: D | 573 | 0.5535536599267725 |
| 1 | Channel: FAX | First order line status: X | 102 | 0.09853834784036787 |
| 1 | Channel: PH | First order line status: D | 1 | 0.0009660622337290968 |
| 1 | Channel: PH | First order line status: X | 95 | 0.0917759122042642 |
| 1 | Channel: SNAIL_MAIL | First order line status: D | 129 | 0.12462202815105348 |
| 1 | Channel: SNAIL_MAIL | First order line status: X | 3 | 0.0028981867011872906 |
| 1 | Channel: VERBAL | First order line status: C | 2 | 0.0019321244674581936 |
| 1 | Channel: VERBAL | First order line status: D | 3050 | 2.9464898128737453 |
| 1 | Channel: VERBAL | First order line status: S | 2 | 0.0019321244674581936 |
| 1 | Channel: VERBAL | First order line status: X | 1866 | 1.8026721281384948 |
| 2 | First order line status: C | First order cancel reason: [No cancellation reason recorded] | 58 | 0.056031609556287616 |
| 2 | First order line status: D | First order cancel reason: [No cancellation reason recorded] | 36207 | 34.97821529662941 |
| 2 | First order line status: R | First order cancel reason: [No cancellation reason recorded] | 3 | 0.0028981867011872906 |
| 2 | First order line status: S | First order cancel reason: [No cancellation reason recorded] | 34 | 0.032846115946789295 |
| 2 | First order line status: X | First order cancel reason: Aged Order | 27332 | 26.404412972283673 |
| 2 | First order line status: X | First order cancel reason: Customer Initiated Cancellation | 13748 | 13.281423589307623 |
| 2 | First order line status: X | First order cancel reason: Customer Request | 5857 | 5.65822650295132 |
| 2 | First order line status: X | First order cancel reason: Duplicate Order | 69 | 0.06665829412730769 |
| 2 | First order line status: X | First order cancel reason: Fraud | 28 | 0.027049742544414713 |
| 2 | First order line status: X | First order cancel reason: Inventory Issue | 3 | 0.0028981867011872906 |
| 2 | First order line status: X | First order cancel reason: No Response | 595 | 0.5748070290688126 |
| 2 | First order line status: X | First order cancel reason: Other | 364 | 0.35164665307739124 |
| 2 | First order line status: X | First order cancel reason: Payment Declined | 2747 | 2.653772956053829 |
| 2 | First order line status: X | First order cancel reason: Payment Issue | 18 | 0.017389120207123743 |
| 2 | First order line status: X | First order cancel reason: Pharmacy Rejection | 184 | 0.1777554510061538 |
| 2 | First order line status: X | First order cancel reason: Prescription Issue | 5031 | 4.8602590978910865 |
| 2 | First order line status: X | First order cancel reason: Reseller | 1 | 0.0009660622337290968 |
| 2 | First order line status: X | First order cancel reason: [No cancellation reason recorded] | 11234 | 10.852743133712673 |
| 3 | First order cancel reason: Aged Order | Matching upload: With cancellation reason / Has matching upload | 825 | 0.7970013428265049 |
| 3 | First order cancel reason: Aged Order | Matching upload: With cancellation reason / No matching upload | 26507 | 25.607411629457168 |
| 3 | First order cancel reason: Customer Initiated Cancellation | Matching upload: With cancellation reason / Has matching upload | 1237 | 1.1950189831228928 |
| 3 | First order cancel reason: Customer Initiated Cancellation | Matching upload: With cancellation reason / No matching upload | 12511 | 12.08640460618473 |
| 3 | First order cancel reason: Customer Request | Matching upload: With cancellation reason / Has matching upload | 1149 | 1.1100055065547323 |
| 3 | First order cancel reason: Customer Request | Matching upload: With cancellation reason / No matching upload | 4708 | 4.548220996396588 |
| 3 | First order cancel reason: Duplicate Order | Matching upload: With cancellation reason / Has matching upload | 14 | 0.013524871272207356 |
| 3 | First order cancel reason: Duplicate Order | Matching upload: With cancellation reason / No matching upload | 55 | 0.053133422855100323 |
| 3 | First order cancel reason: Fraud | Matching upload: With cancellation reason / Has matching upload | 2 | 0.0019321244674581936 |
| 3 | First order cancel reason: Fraud | Matching upload: With cancellation reason / No matching upload | 26 | 0.02511761807695652 |
| 3 | First order cancel reason: Inventory Issue | Matching upload: With cancellation reason / No matching upload | 3 | 0.0028981867011872906 |
| 3 | First order cancel reason: No Response | Matching upload: With cancellation reason / Has matching upload | 9 | 0.008694560103561871 |
| 3 | First order cancel reason: No Response | Matching upload: With cancellation reason / No matching upload | 586 | 0.5661124689652507 |
| 3 | First order cancel reason: Other | Matching upload: With cancellation reason / Has matching upload | 78 | 0.07535285423086956 |
| 3 | First order cancel reason: Other | Matching upload: With cancellation reason / No matching upload | 286 | 0.27629379884652167 |
| 3 | First order cancel reason: Payment Declined | Matching upload: With cancellation reason / Has matching upload | 15 | 0.014490933505936452 |
| 3 | First order cancel reason: Payment Declined | Matching upload: With cancellation reason / No matching upload | 2732 | 2.6392820225478926 |
| 3 | First order cancel reason: Payment Issue | Matching upload: With cancellation reason / Has matching upload | 1 | 0.0009660622337290968 |
| 3 | First order cancel reason: Payment Issue | Matching upload: With cancellation reason / No matching upload | 17 | 0.016423057973394647 |
| 3 | First order cancel reason: Pharmacy Rejection | Matching upload: With cancellation reason / Has matching upload | 15 | 0.014490933505936452 |
| 3 | First order cancel reason: Pharmacy Rejection | Matching upload: With cancellation reason / No matching upload | 169 | 0.16326451750021737 |
| 3 | First order cancel reason: Prescription Issue | Matching upload: With cancellation reason / Has matching upload | 207 | 0.19997488238192304 |
| 3 | First order cancel reason: Prescription Issue | Matching upload: With cancellation reason / No matching upload | 4824 | 4.660284215509163 |
| 3 | First order cancel reason: Reseller | Matching upload: With cancellation reason / No matching upload | 1 | 0.0009660622337290968 |
| 3 | First order cancel reason: [No cancellation reason recorded] | Matching upload: No cancellation reason / Has matching upload | 27078 | 26.159033164916483 |
| 3 | First order cancel reason: [No cancellation reason recorded] | Matching upload: No cancellation reason / No matching upload | 20458 | 19.763701177629862 |

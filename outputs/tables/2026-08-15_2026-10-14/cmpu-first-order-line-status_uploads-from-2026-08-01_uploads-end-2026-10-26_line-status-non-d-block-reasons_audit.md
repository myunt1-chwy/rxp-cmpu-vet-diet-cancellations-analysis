# Audit

Prescription creation 2026-08-15 inclusive to 2026-10-15 exclusive UTC; uploads 2026-08-01 inclusive to 2026-10-26 exclusive UTC. Extracted 2026-10-27T20:35:13.241892+00:00.

Source: EDLDB.BT_HCA_HCDM.ORDER_LINE_COST_MEASURES_RXP. Join FIRST_ORDER_ID = ORDER_ID AND numeric FIRST_ORDERITEM_ID = ORDER_LINE_ID; no RX_ID join to the order-line view. Each matched (ORDER_ID, ORDER_LINE_ID) is counted once, collapsing shipment rows. Prescriptions without usable first-order keys or without a matching line are excluded from the Sankey denominators and reported in the audit. The status stage uses the latest raw ORDER_ORDER_LINE_STATUS codes directly; blank/null statuses are explicit. ORDER_ITEM_BLOCK_REASON is retained in data and tables but omitted from diagrams. Its grouped classification is populated for known non-D statuses, with explicit not-applicable values for D/unknown. Blank/null reasons are labeled [No block reason recorded], which does not independently establish an unblocked item. All figures show line status followed by raw ORDER_CANCEL_REASON; order status is retained only in data. Blank/null cancellation reasons are labeled [No cancellation reason recorded]; this does not establish whether the overall order was canceled. Multiple prescriptions sharing a line are counted once; conflicting classifications fail validation. Upload matching retains the DIET_PRESCRIPTION expanded RX_ID + numeric CUSTOMER_ID rules, without file/association flags, prescription-status/deletion filters or upload-after-creation requirement. A matching entity does not verify file presence. Approval channel → line status → cancellation reason → upload presence is a categorical breakdown, not a chronological journey. Full percentages use all matched distinct lines; focused percentages use matched distinct CUSTOMER_UPLOAD lines. The separate non-D figure uses only known non-D CUSTOMER_UPLOAD lines as its denominator. Upload endpoints separate lines with a recorded cancellation reason from lines without one, each split into has/no matching upload. Blank/null/whitespace reasons mean no recorded reason, not proof of an uncanceled order. All three figures include the explicit line-status column. Column headers identify stages; visible node labels omit repeated stage prefixes. Percentages retain the whole-figure denominator.

| measure | count |
| --- | --- |
| prescription_window_upload_rows | 159010 |
| prescription_invalid_upload_source_rows | 0 |
| prescription_uploads_missing_customer | 0 |
| prescription_uploads_invalid_customer | 0 |
| prescription_upload_rows_missing_rx | 0 |
| prescription_upload_rows_malformed_rx | 0 |
| prescription_cohort_prescriptions | 113608 |
| prescription_prescriptions_with_upload | 34446 |
| prescription_prescriptions_matched_only_by_earlier_uploads | 1 |
| prescription_prescriptions_missing_customer | 0 |
| cohort_prescriptions | 113608 |
| matched_prescriptions | 103513 |
| missing_first_order_id | 10095 |
| missing_or_invalid_first_order_item_id | 0 |
| unmatched_first_order_line | 0 |
| distinct_order_lines | 103513 |
| repeated_prescription_line_associations | 0 |
| shipment_source_rows | 103714 |
| extra_shipment_rows_collapsed | 201 |
| order_lines_with_upload | 30630 |
| order_lines_without_recorded_block_reason | 253 |
| canceled_lines_on_uncanceled_orders | 11014 |
| non_d_order_lines | 67306 |
| customer_upload_non_d_order_lines | 65141 |
| d_order_lines | 36207 |
| unknown_line_statuses | 0 |

# Prior shipped prescriptions: audit

CMPU vet-diet CUSTOMER_UPLOAD prescriptions define the aged-order cohort. Each customer is counted once. Reference = earliest qualifying aged cancellation; every qualifying aged-cancelled order is excluded from history, including all tied reference orders and all lines on those orders. Shipment evidence is ORDER_LINE_SHIPPED_DTTM strictly before that cancellation, UTC, on another order. A shipped line is sufficient; delivery, complete-order fulfillment and current status are not required. Historical RX_ID and customer ID must both match; history is not restricted by prescription creation dates, approval channel, product or pet. Shipment rows collapse by order/line/RX_ID before customer aggregation. Inclusive pharmacy means vet diet (IS_VET_DIET_FLAG=TRUE) or MERCH_CLASS2 Pharmacy, Compound, Over the Counter. CMPU vet diet additionally requires PRESCRIPTION_SOURCE=CMPU. All percentages use the full aged-customer denominator. Vet diet is a subset of inclusive pharmacy, and CMPU vet diet is a subset of vet diet; do not add headline counts. Other/unclassified categories remain in evidence/audits, outside those three flags. Available-history dates describe observed candidate shipments for cohort customers, not warehouse retention bounds. Full detail is retained in the matching data/ Parquet files. Extracted 2026-10-27T22:27:53.013563+00:00; source SHA-256 4fb0767b61c2b932625ca3ae729fc639d7028b6ba19dcdd0743303696f14aca6.

| measure | count |
| --- | --- |
| Cohort association: Matched, outside aged population | 68627 |
| Cohort association: Aged order | 26443 |
| Cohort association: Missing order ID | 9237 |
| History: Missing RX_ID | 1511099 |
| History: Eligible | 554877 |
| History: RX/customer mismatch | 220 |
| Aged orders missing customer ID | 0 |
| Collapsed history shipment rows | 99891 |
| Eligible unclassified history records | 0 |
| Vet-diet flag disagrees with merchandise category | 0 |

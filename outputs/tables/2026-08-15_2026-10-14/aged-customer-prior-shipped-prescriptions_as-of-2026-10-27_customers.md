# Prior shipped prescriptions: customers

CMPU vet-diet CUSTOMER_UPLOAD prescriptions define the aged-order cohort. Each customer is counted once. Reference = earliest qualifying aged cancellation; every qualifying aged-cancelled order is excluded from history, including all tied reference orders and all lines on those orders. Shipment evidence is ORDER_LINE_SHIPPED_DTTM strictly before that cancellation, UTC, on another order. A shipped line is sufficient; delivery, complete-order fulfillment and current status are not required. Historical RX_ID and customer ID must both match; history is not restricted by prescription creation dates, approval channel, product or pet. Shipment rows collapse by order/line/RX_ID before customer aggregation. Inclusive pharmacy means vet diet (IS_VET_DIET_FLAG=TRUE) or MERCH_CLASS2 Pharmacy, Compound, Over the Counter. CMPU vet diet additionally requires PRESCRIPTION_SOURCE=CMPU. All percentages use the full aged-customer denominator. Vet diet is a subset of inclusive pharmacy, and CMPU vet diet is a subset of vet diet; do not add headline counts. Other/unclassified categories remain in evidence/audits, outside those three flags. Available-history dates describe observed candidate shipments for cohort customers, not warehouse retention bounds. Full detail is retained in the matching data/ Parquet files. Extracted 2026-10-27T22:27:53.013563+00:00; source SHA-256 4fb0767b61c2b932625ca3ae729fc639d7028b6ba19dcdd0743303696f14aca6.

> **Table preview:** 25 of 20,587 rows shown; the full table exceeds the Markdown size budget. Use the associated data/ exports for complete records.

| customer_id | reference_cancel_time | aged_orders | prior_inclusive_pharmacy | prior_vet_diet | prior_cmpu_vet_diet | history_group |
| --- | --- | --- | --- | --- | --- | --- |
| 11571.0 | 2026-10-15 07:20:54.464000+00:00 | 1 | True | True | False | Vet diet without CMPU vet diet |
| 17467.0 | 2026-09-03 07:18:11.190000+00:00 | 1 | True | True | True | CMPU vet diet |
| 19529.0 | 2026-09-03 07:51:13.421000+00:00 | 2 | True | True | False | Vet diet without CMPU vet diet |
| 29920.0 | 2026-09-02 04:26:10.459000+00:00 | 1 | True | True | False | Vet diet without CMPU vet diet |
| 45460.0 | 2026-09-15 04:34:26.386000+00:00 | 1 | True | True | False | Vet diet without CMPU vet diet |
| 47059.0 | 2026-08-30 05:24:11.581000+00:00 | 2 | False | False | <NA> | No qualifying inclusive-pharmacy history |
| 49434.0 | 2026-10-18 05:10:19.225000+00:00 | 1 | True | True | False | Vet diet without CMPU vet diet |
| 62543.0 | 2026-10-08 04:34:29.813000+00:00 | 1 | True | False | False | Inclusive pharmacy without vet diet |
| 63365.0 | 2026-09-18 05:13:54.588000+00:00 | 1 | True | True | True | CMPU vet diet |
| 72311.0 | 2026-10-02 04:45:00.838000+00:00 | 1 | True | True | False | Vet diet without CMPU vet diet |
| 74440.0 | 2026-09-10 07:17:56.013000+00:00 | 1 | True | True | False | Vet diet without CMPU vet diet |
| 80263.0 | 2026-10-12 06:42:08.490000+00:00 | 1 | False | False | False | No qualifying inclusive-pharmacy history |
| 90125.0 | 2026-10-15 06:56:11.674000+00:00 | 1 | True | True | True | CMPU vet diet |
| 116961.0 | 2026-08-27 05:56:40.526000+00:00 | 3 | True | True | False | Vet diet without CMPU vet diet |
| 136195.0 | 2026-09-27 05:40:34.933000+00:00 | 1 | True | True | True | CMPU vet diet |
| 143435.0 | 2026-10-14 08:16:34.949000+00:00 | 1 | True | True | False | Vet diet without CMPU vet diet |
| 145482.0 | 2026-09-16 05:49:28.092000+00:00 | 2 | True | True | False | Vet diet without CMPU vet diet |
| 159255.0 | 2026-10-19 04:30:16.604000+00:00 | 1 | True | True | True | CMPU vet diet |
| 161263.0 | 2026-09-28 07:45:32.576000+00:00 | 1 | True | True | True | CMPU vet diet |
| 171473.0 | 2026-09-10 07:06:42.836000+00:00 | 3 | True | True | True | CMPU vet diet |
| 173593.0 | 2026-08-27 06:43:37.071000+00:00 | 1 | True | True | True | CMPU vet diet |
| 175936.0 | 2026-09-23 06:32:22.534000+00:00 | 1 | True | True | False | Vet diet without CMPU vet diet |
| 177115.0 | 2026-08-31 07:21:45.606000+00:00 | 1 | True | True | True | CMPU vet diet |
| 178325.0 | 2026-09-13 06:15:00.005000+00:00 | 1 | True | True | True | CMPU vet diet |
| 179684.0 | 2026-09-28 04:37:38.779000+00:00 | 1 | True | True | True | CMPU vet diet |

# Prior shipped prescriptions: reference-orders

CMPU vet-diet CUSTOMER_UPLOAD prescriptions define the aged-order cohort. Each customer is counted once. Reference = earliest qualifying aged cancellation; every qualifying aged-cancelled order is excluded from history, including all tied reference orders and all lines on those orders. Shipment evidence is ORDER_LINE_SHIPPED_DTTM strictly before that cancellation, UTC, on another order. A shipped line is sufficient; delivery, complete-order fulfillment and current status are not required. Historical RX_ID and customer ID must both match; history is not restricted by prescription creation dates, approval channel, product or pet. Shipment rows collapse by order/line/RX_ID before customer aggregation. Inclusive pharmacy means vet diet (IS_VET_DIET_FLAG=TRUE) or MERCH_CLASS2 Pharmacy, Compound, Over the Counter. CMPU vet diet additionally requires PRESCRIPTION_SOURCE=CMPU. All percentages use the full aged-customer denominator. Vet diet is a subset of inclusive pharmacy, and CMPU vet diet is a subset of vet diet; do not add headline counts. Other/unclassified categories remain in evidence/audits, outside those three flags. Available-history dates describe observed candidate shipments for cohort customers, not warehouse retention bounds. Full detail is retained in the matching data/ Parquet files. Extracted 2026-10-27T22:27:53.013563+00:00; source SHA-256 4fb0767b61c2b932625ca3ae729fc639d7028b6ba19dcdd0743303696f14aca6.

> **Table preview:** 25 of 20,587 rows shown; the full table exceeds the Markdown size budget. Use the associated data/ exports for complete records.

| order_id | customer_id | order_cancel_reason | order_cancel_time | reference_cancel_time |
| --- | --- | --- | --- | --- |
| 5216300191.0 | 337887152.0 | aged order | 2026-09-24 05:35:23.278000+00:00 | 2026-09-24 05:35:23.278000+00:00 |
| 5225195435.0 | 11256808.0 | aged order | 2026-10-11 05:29:53.473000+00:00 | 2026-10-11 05:29:53.473000+00:00 |
| 5214494312.0 | 24284177.0 | aged order | 2026-09-11 15:32:38.717000+00:00 | 2026-09-11 15:32:38.717000+00:00 |
| 5224034365.0 | 8281707.0 | aged order | 2026-10-09 06:13:20.101000+00:00 | 2026-10-09 06:13:20.101000+00:00 |
| 5206327971.0 | 307861013.0 | aged order | 2026-09-06 05:29:13.145000+00:00 | 2026-09-06 05:29:13.145000+00:00 |
| 5205039044.0 | 15769843.0 | aged order | 2026-09-03 06:22:03.035000+00:00 | 2026-09-03 06:22:03.035000+00:00 |
| 5213319164.0 | 287253490.0 | aged order | 2026-09-18 05:59:15.364000+00:00 | 2026-09-18 05:59:15.364000+00:00 |
| 5229780343.0 | 970671563.0 | aged order | 2026-10-22 05:56:18.102000+00:00 | 2026-10-22 05:56:18.102000+00:00 |
| 5228858463.0 | 892425425.0 | aged order | 2026-10-19 06:13:55.028000+00:00 | 2026-10-19 06:13:55.028000+00:00 |
| 5215539361.0 | 936381480.0 | aged order | 2026-09-23 04:12:04.149000+00:00 | 2026-09-23 04:12:04.149000+00:00 |
| 5222407196.0 | 340278203.0 | aged order | 2026-10-06 04:44:09.793000+00:00 | 2026-10-06 04:44:09.793000+00:00 |
| 5207537108.0 | 964419115.0 | aged order | 2026-09-09 08:37:16.431000+00:00 | 2026-09-09 08:37:16.431000+00:00 |
| 5211417605.0 | 941979429.0 | aged order | 2026-09-15 07:39:37.280000+00:00 | 2026-09-15 07:39:37.280000+00:00 |
| 5211325853.0 | 54975901.0 | aged order | 2026-09-15 04:55:29.798000+00:00 | 2026-09-15 04:55:29.798000+00:00 |
| 5228144177.0 | 75742762.0 | aged order | 2026-10-18 06:28:57.432000+00:00 | 2026-10-18 06:28:57.432000+00:00 |
| 5206926043.0 | 975723100.0 | aged order | 2026-09-07 06:30:11.658000+00:00 | 2026-09-07 06:30:11.658000+00:00 |
| 5226064850.0 | 926689093.0 | aged order | 2026-10-13 06:42:47.393000+00:00 | 2026-10-13 06:42:47.393000+00:00 |
| 5229670167.0 | 57807334.0 | aged order | 2026-10-22 06:15:49.832000+00:00 | 2026-10-22 06:15:49.832000+00:00 |
| 5208335881.0 | 60541232.0 | aged order | 2026-09-10 06:08:17.826000+00:00 | 2026-09-10 06:08:17.826000+00:00 |
| 5210831145.0 | 958089043.0 | aged order | 2026-09-14 06:10:19.128000+00:00 | 2026-09-14 06:10:19.128000+00:00 |
| 5200556069.0 | 20237266.0 | aged order | 2026-08-25 07:02:26.041000+00:00 | 2026-08-25 07:02:26.041000+00:00 |
| 5230176700.0 | 36069809.0 | aged order | 2026-10-23 06:03:47.507000+00:00 | 2026-10-23 06:03:47.507000+00:00 |
| 5208776242.0 | 130860527.0 | aged order | 2026-09-10 06:42:07.219000+00:00 | 2026-09-10 06:42:07.219000+00:00 |
| 5228667360.0 | 88349910.0 | aged order | 2026-10-19 07:08:35.540000+00:00 | 2026-10-19 07:08:35.540000+00:00 |
| 5203102803.0 | 185568758.0 | aged order | 2026-08-31 04:06:00.867000+00:00 | 2026-08-31 04:06:00.867000+00:00 |

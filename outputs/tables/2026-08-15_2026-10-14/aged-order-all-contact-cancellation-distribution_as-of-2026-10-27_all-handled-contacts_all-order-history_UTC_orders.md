# All aged-order contact timing: orders

CMPU vet-diet CUSTOMER_UPLOAD first-order cohort; every aged order, regardless of reordering. Distinct order/order-line keys collapse shipment rows; orders are counted once across prescriptions and lines. All available HANDLED_FLAG=TRUE contact rows on aged orders, all categories, with no contact-time restriction. Contacts and cancellations are UTC. The as-of cutoff applies to cancellations, not contact history. Lag = contact time minus cancellation; exact nanosecond floor bins [day,day+1). Undated contacts remain in details and totals but are excluded from histogram shares. Counts follow contact source rows (contact legs), not unique sessions. Daily customer/session/order counts can overlap across bins. Full data are in the corresponding data/ Parquet files. Source extracted 2026-10-27T20:26:14.162146+00:00; SHA-256 5001100ecaaac06e0c82ac13cc26031e6168ebfcab923295726b6596d26e657c.

> **Table preview:** 25 of 24,408 rows shown; the full table exceeds the Markdown size budget. Use the associated data/ exports for complete records.

| order_id | customer_id | order_cancel_reason | order_cancel_time | contact_count |
| --- | --- | --- | --- | --- |
| 5221079370.0 | 18154028.0 | aged order | 2026-10-04 04:30:43.896000+00:00 | 1 |
| 5229748049.0 | 927630792.0 | aged order | 2026-10-22 06:07:02.031000+00:00 | 1 |
| 5201234414.0 | 95470855.0 | aged order | 2026-08-27 08:23:14.798000+00:00 | 1 |
| 5230170268.0 | 336868322.0 | aged order | 2026-10-23 05:57:14.376000+00:00 | 1 |
| 5226967344.0 | 285882656.0 | aged order | 2026-10-14 06:04:23.094000+00:00 | 2 |
| 5219542057.0 | 321880490.0 | aged order | 2026-09-30 05:54:56.152000+00:00 | 1 |
| 5222659397.0 | 297445739.0 | aged order | 2026-10-06 04:24:21.101000+00:00 | 1 |
| 5225986562.0 | 57902627.0 | aged order | 2026-10-13 08:49:15.830000+00:00 | 1 |
| 5218625696.0 | 86312752.0 | aged order | 2026-09-29 05:07:24.196000+00:00 | 1 |
| 5217538597.0 | 338054741.0 | aged order | 2026-09-27 05:38:45.169000+00:00 | 1 |
| 5210699246.0 | 23502220.0 | aged order | 2026-09-14 03:03:50.044000+00:00 | 1 |
| 5224254101.0 | 154677493.0 | aged order | 2026-10-09 06:54:19.137000+00:00 | 2 |
| 5215594704.0 | 2156362.0 | aged order | 2026-09-23 05:14:51.018000+00:00 | 3 |
| 5228586628.0 | 317199643.0 | aged order | 2026-10-19 06:15:54.185000+00:00 | 1 |
| 5220184709.0 | 969294795.0 | aged order | 2026-10-02 05:23:13.051000+00:00 | 1 |
| 5222100488.0 | 2792124.0 | aged order | 2026-10-05 05:52:26.221000+00:00 | 1 |
| 5225209320.0 | 340468674.0 | aged order | 2026-10-11 04:21:17.133000+00:00 | 2 |
| 5229056158.0 | 27981785.0 | aged order | 2026-10-21 04:33:16.823000+00:00 | 1 |
| 5214913222.0 | 4018209.0 | aged order | 2026-09-22 07:02:35.147000+00:00 | 1 |
| 5226068599.0 | 930942577.0 | aged order | 2026-10-13 07:03:16.273000+00:00 | 1 |
| 5211362909.0 | 81527578.0 | aged order | 2026-09-15 04:35:31.936000+00:00 | 1 |
| 5204621817.0 | 143646024.0 | aged order | 2026-09-02 05:12:52.971000+00:00 | 2 |
| 5209873071.0 | 130717699.0 | aged order | 2026-09-13 04:56:09.030000+00:00 | 1 |
| 5221645880.0 | 4661617.0 | aged order | 2026-10-05 06:50:49.854000+00:00 | 1 |
| 5211184768.0 | 16055389.0 | aged order | 2026-09-15 04:32:53.270000+00:00 | 1 |

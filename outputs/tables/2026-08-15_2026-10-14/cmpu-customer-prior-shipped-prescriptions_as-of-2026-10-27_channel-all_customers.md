# Shipment history before cohort order placement: customers

All CMPU vet-diet customers in the selected prescription-creation window/channel, regardless of order status, cancellation reason or reordering. One observation per known prescription customer. Reference = earliest cohort first-order placement; every matched cohort ORDER_ID and all its lines are excluded from prior history. All prescription associations must have matched customer/order/placement information to establish the earliest reference. Customers with incomplete references are unknown, not no-history customers. History requires a populated UTC ORDER_LINE_SHIPPED_DTTM strictly BEFORE reference order placement, matching RX_ID and customer ID. Delivery/full-order completion are not required. Inclusive pharmacy = Pharmacy, Compound, Over the Counter or IS_VET_DIET_FLAG=TRUE; vet diet uses that flag; CMPU vet diet also requires PRESCRIPTION_SOURCE=CMPU. Historical channels, products, pets and prescription dates are unrestricted. The three history flags are nested and not additive. Percentages of assessable customers exclude unknown references; percentages of all cohort customers retain them. Dates of observed history do not establish source retention bounds. Missing RX/customer matches remain audited, outside qualifying evidence. Complete records are in data/ Parquet. Cohort 2026-08-15 inclusive to 2026-10-15 exclusive; channel ALL; as-of 2026-10-27 00:00 UTC. Source 81acd3cf15c58bb59e89509654a8b1782e030ca49a62693a1b1994fbc148df0a; extracted 2026-10-27T22:51:45.670782+00:00.

> **Table preview:** 25 of 84,425 rows shown; the full table exceeds the Markdown size budget. Use the associated data/ exports for complete records.

| customer_id | cohort_prescriptions | reference_placed_time | incomplete_references | assessable | prior_inclusive_pharmacy | prior_vet_diet | prior_cmpu_vet_diet | history_group |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 3451 | 2 | NaT | 1 | False | <NA> | <NA> | <NA> | Unknown reference placement |
| 3790 | 1 | 2026-09-04 20:13:20.166000+00:00 | 0 | True | True | True | False | Vet diet without CMPU vet diet |
| 4528 | 1 | 2026-08-31 01:09:29.137000+00:00 | 0 | True | True | False | False | Inclusive pharmacy without vet diet |
| 11571 | 1 | 2026-10-04 12:05:05.449000+00:00 | 0 | True | True | True | False | Vet diet without CMPU vet diet |
| 11681 | 2 | NaT | 1 | False | <NA> | <NA> | <NA> | Unknown reference placement |
| 17467 | 2 | 2026-08-24 04:23:54.905000+00:00 | 0 | True | True | True | True | CMPU vet diet |
| 17635 | 1 | 2026-08-16 23:21:03.044000+00:00 | 0 | True | False | False | <NA> | No qualifying inclusive-pharmacy history |
| 19529 | 3 | 2026-08-24 04:26:12.798000+00:00 | 0 | True | True | True | False | Vet diet without CMPU vet diet |
| 20867 | 2 | 2026-08-22 02:36:33.578000+00:00 | 0 | True | True | True | False | Vet diet without CMPU vet diet |
| 20959 | 1 | 2026-09-17 19:32:31.990000+00:00 | 0 | True | True | True | False | Vet diet without CMPU vet diet |
| 21256 | 1 | 2026-08-31 19:19:53.820000+00:00 | 0 | True | True | True | False | Vet diet without CMPU vet diet |
| 21452 | 1 | NaT | 1 | False | <NA> | <NA> | <NA> | Unknown reference placement |
| 21848 | 2 | 2026-09-02 04:39:59.253000+00:00 | 0 | True | True | True | True | CMPU vet diet |
| 22126 | 1 | 2026-10-11 18:23:10.909000+00:00 | 0 | True | False | False | <NA> | No qualifying inclusive-pharmacy history |
| 26079 | 1 | 2026-09-16 22:30:19.520000+00:00 | 0 | True | True | True | False | Vet diet without CMPU vet diet |
| 26447 | 1 | 2026-09-14 22:01:26.507000+00:00 | 0 | True | True | True | True | CMPU vet diet |
| 26563 | 1 | NaT | 1 | False | <NA> | <NA> | <NA> | Unknown reference placement |
| 27835 | 1 | 2026-08-31 20:43:41.161000+00:00 | 0 | True | True | True | False | Vet diet without CMPU vet diet |
| 28544 | 1 | 2026-08-18 22:58:03.953000+00:00 | 0 | True | True | True | False | Vet diet without CMPU vet diet |
| 29920 | 1 | 2026-08-23 04:47:48.196000+00:00 | 0 | True | True | True | False | Vet diet without CMPU vet diet |
| 33683 | 2 | NaT | 1 | False | <NA> | <NA> | <NA> | Unknown reference placement |
| 34235 | 2 | NaT | 1 | False | <NA> | <NA> | <NA> | Unknown reference placement |
| 35382 | 1 | 2026-09-16 04:49:26.690000+00:00 | 0 | True | True | True | True | CMPU vet diet |
| 35642 | 1 | 2026-09-30 04:54:07.651000+00:00 | 0 | True | True | True | True | CMPU vet diet |
| 41140 | 2 | 2026-10-06 05:16:37.638000+00:00 | 0 | True | True | True | True | CMPU vet diet |

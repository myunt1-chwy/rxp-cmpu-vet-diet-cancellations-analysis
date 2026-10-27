# Shipment history before cohort order placement: orders

All CMPU vet-diet customers in the selected prescription-creation window/channel, regardless of order status, cancellation reason or reordering. One observation per known prescription customer. Reference = earliest cohort first-order placement; every matched cohort ORDER_ID and all its lines are excluded from prior history. All prescription associations must have matched customer/order/placement information to establish the earliest reference. Customers with incomplete references are unknown, not no-history customers. History requires a populated UTC ORDER_LINE_SHIPPED_DTTM strictly BEFORE reference order placement, matching RX_ID and customer ID. Delivery/full-order completion are not required. Inclusive pharmacy = Pharmacy, Compound, Over the Counter or IS_VET_DIET_FLAG=TRUE; vet diet uses that flag; CMPU vet diet also requires PRESCRIPTION_SOURCE=CMPU. Historical channels, products, pets and prescription dates are unrestricted. The three history flags are nested and not additive. Percentages of assessable customers exclude unknown references; percentages of all cohort customers retain them. Dates of observed history do not establish source retention bounds. Missing RX/customer matches remain audited, outside qualifying evidence. Complete records are in data/ Parquet. Cohort 2026-08-15 inclusive to 2026-10-15 exclusive; channel ALL; as-of 2026-10-27 00:00 UTC. Source 81acd3cf15c58bb59e89509654a8b1782e030ca49a62693a1b1994fbc148df0a; extracted 2026-10-27T22:51:45.670782+00:00.

> **Table preview:** 25 of 95,530 rows shown; the full table exceeds the Markdown size budget. Use the associated data/ exports for complete records.

| order_id | customer_id | order_placed_time | matched_order_lines |
| --- | --- | --- | --- |
| 1750058601.0 | 977280904.0 | 2026-08-23 18:49:39.702000+00:00 | 1 |
| 1750058759.0 | 128568456.0 | 2026-08-23 20:17:16.646000+00:00 | 1 |
| 1750058905.0 | 207376312.0 | 2026-08-24 15:13:57.106000+00:00 | 1 |
| 1750059117.0 | 893742084.0 | 2026-08-24 23:04:33.863000+00:00 | 1 |
| 1750059473.0 | 126385447.0 | 2026-08-26 21:47:09.572000+00:00 | 1 |
| 1750060771.0 | 894221853.0 | 2026-08-31 20:20:29.573000+00:00 | 1 |
| 1750061607.0 | 302126089.0 | 2026-09-05 01:02:13.720000+00:00 | 1 |
| 1750061861.0 | 9673268.0 | 2026-09-06 17:24:25.056000+00:00 | 1 |
| 1750062347.0 | 985280773.0 | 2026-09-09 02:04:02.963000+00:00 | 1 |
| 1750062485.0 | 38962744.0 | 2026-09-09 22:56:44.451000+00:00 | 1 |
| 1750063381.0 | 945359417.0 | 2026-09-15 00:07:24.046000+00:00 | 1 |
| 1750063937.0 | 69315885.0 | 2026-09-18 15:43:45.188000+00:00 | 1 |
| 1750064539.0 | 127473727.0 | 2026-09-23 02:34:56.236000+00:00 | 2 |
| 1750064720.0 | 131585732.0 | 2026-08-31 19:11:01.825000+00:00 | 1 |
| 1750065136.0 | 328686097.0 | 2026-09-08 15:45:20.957000+00:00 | 1 |
| 1750065151.0 | 9683013.0 | 2026-09-27 00:13:43.807000+00:00 | 1 |
| 1750065431.0 | 68204545.0 | 2026-09-28 22:37:00.323000+00:00 | 1 |
| 1750065510.0 | 52945735.0 | 2026-09-15 14:15:11.042000+00:00 | 2 |
| 1750066185.0 | 969871803.0 | 2026-10-03 10:42:27.915000+00:00 | 1 |
| 1750066573.0 | 879375656.0 | 2026-10-05 22:05:48.668000+00:00 | 1 |
| 1750066949.0 | 97241852.0 | 2026-10-08 01:31:07.678000+00:00 | 2 |
| 1750067388.0 | 11400132.0 | 2026-10-10 04:06:18.594000+00:00 | 1 |
| 1750067769.0 | 64001545.0 | 2026-10-13 14:26:55.695000+00:00 | 1 |
| 1750067779.0 | 111244754.0 | 2026-10-13 20:43:35.012000+00:00 | 1 |
| 1750068642.0 | 91653685.0 | 2026-10-13 20:11:33.913000+00:00 | 1 |

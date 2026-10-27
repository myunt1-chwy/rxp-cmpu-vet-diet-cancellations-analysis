# Shipment history before cohort order placement: exclusive-groups

All CMPU vet-diet customers in the selected prescription-creation window/channel, regardless of order status, cancellation reason or reordering. One observation per known prescription customer. Reference = earliest cohort first-order placement; every matched cohort ORDER_ID and all its lines are excluded from prior history. All prescription associations must have matched customer/order/placement information to establish the earliest reference. Customers with incomplete references are unknown, not no-history customers. History requires a populated UTC ORDER_LINE_SHIPPED_DTTM strictly BEFORE reference order placement, matching RX_ID and customer ID. Delivery/full-order completion are not required. Inclusive pharmacy = Pharmacy, Compound, Over the Counter or IS_VET_DIET_FLAG=TRUE; vet diet uses that flag; CMPU vet diet also requires PRESCRIPTION_SOURCE=CMPU. Historical channels, products, pets and prescription dates are unrestricted. The three history flags are nested and not additive. Percentages of assessable customers exclude unknown references; percentages of all cohort customers retain them. Dates of observed history do not establish source retention bounds. Missing RX/customer matches remain audited, outside qualifying evidence. Complete records are in data/ Parquet. Cohort 2026-08-15 inclusive to 2026-10-15 exclusive; channel ALL; as-of 2026-10-27 00:00 UTC. Source 81acd3cf15c58bb59e89509654a8b1782e030ca49a62693a1b1994fbc148df0a; extracted 2026-10-27T22:51:45.670782+00:00.

| history_group | customers | percent_of_all_cohort_customers |
| --- | --- | --- |
| CMPU vet diet | 25671 | 30.40687000296121 |
| Inclusive pharmacy without vet diet | 4370 | 5.176191886289606 |
| No qualifying inclusive-pharmacy history | 15999 | 18.950547823511993 |
| Unknown reference placement | 8872 | 10.508735564110157 |
| Vet diet without CMPU vet diet | 29513 | 34.957654723127035 |

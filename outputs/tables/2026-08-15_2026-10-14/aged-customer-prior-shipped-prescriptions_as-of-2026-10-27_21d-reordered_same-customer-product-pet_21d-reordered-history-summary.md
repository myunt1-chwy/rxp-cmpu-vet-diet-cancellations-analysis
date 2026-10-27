# Prior shipment history for 21-day reordered customers

5,382 distinct customers reordered within 21 days among 15,544 customers with complete 21-day follow-up. Reorders match customer/product/pet, strictly after cancellation and at most 21 days later. Cancellation eligibility cutoff: 2026-10-06 00:00 UTC; cohort snapshot: 2026-10-27 00:00 UTC. Prior shipment flags are the REFNUM 35 flags, BEFORE EACH CUSTOMER’S EARLIEST QUALIFYING AGED CANCELLATION, excluding every qualifying aged-cancelled order and all its lines, including tied reference orders; they are not recomputed relative to the selected shortest-delay reorder pair. The three prior-history counts are nested, not additive. Historical RX_ID and customer ID must match. One shipped line is sufficient; no delivery or full-order fulfillment requirement. The detail includes both historical reference and selected reorder-pair cancellation timestamps. Full customer data remain in the matching Parquet export.

| prior_shipped_history | reordered_customers | percent_of_21d_reordered_customers | all_aged_customers | percent_of_all_aged_customers |
| --- | --- | --- | --- | --- |
| Inclusive pharmacy (Pharmacy/Compound/OTC/vet diet) | 4554 | 84.61538461538461 | 17360 | 84.32505950357022 |
| Vet diet | 4355 | 80.91787439613526 | 16589 | 80.57997765580221 |
| CMPU vet diet | 2401 | 44.611668524712 | 7942 | 38.577743236022734 |

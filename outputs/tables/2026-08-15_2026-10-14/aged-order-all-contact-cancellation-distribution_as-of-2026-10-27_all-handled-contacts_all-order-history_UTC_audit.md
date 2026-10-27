# All aged-order contact timing: audit

CMPU vet-diet CUSTOMER_UPLOAD first-order cohort; every aged order, regardless of reordering. Distinct order/order-line keys collapse shipment rows; orders are counted once across prescriptions and lines. All available HANDLED_FLAG=TRUE contact rows on aged orders, all categories, with no contact-time restriction. Contacts and cancellations are UTC. The as-of cutoff applies to cancellations, not contact history. Lag = contact time minus cancellation; exact nanosecond floor bins [day,day+1). Undated contacts remain in details and totals but are excluded from histogram shares. Counts follow contact source rows (contact legs), not unique sessions. Daily customer/session/order counts can overlap across bins. Full data are in the corresponding data/ Parquet files. Source extracted 2026-10-27T20:26:14.162146+00:00; SHA-256 5001100ecaaac06e0c82ac13cc26031e6168ebfcab923295726b6596d26e657c.

| association_state | prescriptions |
| --- | --- |
| Matched, outside aged population | 68627 |
| Aged order | 26443 |
| Missing order ID | 9237 |

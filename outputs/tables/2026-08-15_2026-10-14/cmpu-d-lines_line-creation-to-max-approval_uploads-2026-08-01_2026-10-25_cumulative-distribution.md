# Cumulative distribution

CMPU vet diet · CUSTOMER_UPLOAD · Rx created 2026-08-15–2026-10-14 (UTC)

Has matching upload · Uploads 2026-08-01–2026-10-25 (UTC)

MAX_APPROVED_DATETIME − ORDER_LINE_CREATED_DTTM, hours. Both first-order keys matched; one count per distinct order/order-line pair, current line status D. Shipment rows collapsed using latest populated approval. Require a matching DIET_PRESCRIPTION upload entity by expanded RX_ID and numeric CUSTOMER_ID. No file-presence or upload-before-approval requirement. Both timing endpoints required; no approval-date filter. Negative durations and outliers retained. Bins are [lower, upper); quantiles use unbinned hours with linear interpolation. Association and distinct-line audit counts have separate denominators; missing endpoints are not zero. Extracted at 2026-10-27T20:56:07.178837+00:00.

Exact empirical CDF: share of eligible lines with duration ≤ the listed hours.

> **Table preview:** 25 of 24,943 rows shown; the full table exceeds the Markdown size budget. Use the associated data/ exports for complete records.

| elapsed_hours | order_lines | cumulative_lines | cumulative_fraction |
| --- | --- | --- | --- |
| 0.0036800394444444443 | 1 | 1 | 4.009140841117748e-05 |
| 0.0036860836111111115 | 1 | 2 | 8.018281682235497e-05 |
| 0.0037230469444444448 | 1 | 3 | 0.00012027422523353245 |
| 0.003736606388888889 | 1 | 4 | 0.00016036563364470993 |
| 0.0037426238888888888 | 1 | 5 | 0.00020045704205588741 |
| 0.0037461780555555556 | 1 | 6 | 0.0002405484504670649 |
| 0.003762639722222222 | 1 | 7 | 0.0002806398588782424 |
| 0.003763266111111111 | 1 | 8 | 0.00032073126728941986 |
| 0.0037712569444444447 | 1 | 9 | 0.00036082267570059737 |
| 0.003776368333333333 | 1 | 10 | 0.00040091408411177483 |
| 0.0037807511111111114 | 1 | 11 | 0.00044100549252295234 |
| 0.0037891683333333335 | 1 | 12 | 0.0004810969009341298 |
| 0.0037899108333333334 | 1 | 13 | 0.0005211883093453073 |
| 0.003790092777777778 | 1 | 14 | 0.0005612797177564848 |
| 0.0037919438888888886 | 1 | 15 | 0.0006013711261676623 |
| 0.0037926794444444445 | 1 | 16 | 0.0006414625345788397 |
| 0.0038021272222222226 | 1 | 17 | 0.0006815539429900172 |
| 0.0038041980555555553 | 1 | 18 | 0.0007216453514011947 |
| 0.0038055580555555555 | 1 | 19 | 0.0007617367598123723 |
| 0.003806133611111111 | 1 | 20 | 0.0008018281682235497 |
| 0.0038137958333333334 | 1 | 21 | 0.0008419195766347272 |
| 0.00381578 | 1 | 22 | 0.0008820109850459047 |
| 0.003817478888888889 | 1 | 23 | 0.0009221023934570822 |
| 0.0038204155555555557 | 1 | 24 | 0.0009621938018682596 |
| 0.003823561666666667 | 1 | 25 | 0.0010022852102794372 |

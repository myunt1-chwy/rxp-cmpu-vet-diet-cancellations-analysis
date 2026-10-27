# Cumulative distribution

CMPU vet diet · CUSTOMER_UPLOAD · Rx created 2026-08-15–2026-10-14 (UTC)

Nonnegative durations only · Negative durations excluded

Has matching upload · Uploads 2026-08-01–2026-10-25 (UTC)

Earliest matching upload CREATED_TS_UTC − ORDER_LINE_CREATED_DTTM, hours. Earliest upload is within the stated upload search window. Approval timestamp is not required. Both first-order keys matched; one count per distinct order/order-line pair, current line status D. Shipment rows collapsed to consistent line-creation timestamps. Require a matching DIET_PRESCRIPTION upload entity by expanded RX_ID and numeric CUSTOMER_ID. No file-presence or upload-before-approval requirement. Both timing endpoints required; no approval-date filter. Negative durations excluded from histogram and statistics; retained in details and eligibility audit. All nonnegative outliers retained. Bins are [lower, upper); quantiles use unbinned hours with linear interpolation. Association and distinct-line audit counts have separate denominators; missing endpoints are not zero. Extracted at 2026-10-27T20:58:05.129083+00:00.

Exact empirical CDF: share of eligible lines with duration ≤ the listed hours.

> **Table preview:** 25 of 24,704 rows shown; the full table exceeds the Markdown size budget. Use the associated data/ exports for complete records.

| elapsed_hours | order_lines | cumulative_lines | cumulative_fraction |
| --- | --- | --- | --- |
| 0.002545390833333333 | 1 | 1 | 4.0479274611398965e-05 |
| 0.0026284425 | 1 | 2 | 8.095854922279793e-05 |
| 0.002910554444444444 | 1 | 3 | 0.00012143782383419689 |
| 0.002957401666666667 | 1 | 4 | 0.00016191709844559586 |
| 0.0030612488888888886 | 1 | 5 | 0.0002023963730569948 |
| 0.003182465277777778 | 1 | 6 | 0.00024287564766839378 |
| 0.003197343611111111 | 1 | 7 | 0.0002833549222797927 |
| 0.0032446408333333334 | 1 | 8 | 0.0003238341968911917 |
| 0.00334182 | 1 | 9 | 0.00036431347150259067 |
| 0.0033522863888888893 | 1 | 10 | 0.0004047927461139896 |
| 0.003364506111111111 | 1 | 11 | 0.0004452720207253886 |
| 0.0033754294444444445 | 1 | 12 | 0.00048575129533678756 |
| 0.0034495466666666663 | 1 | 13 | 0.0005262305699481866 |
| 0.0034571280555555552 | 1 | 14 | 0.0005667098445595854 |
| 0.0034800619444444445 | 1 | 15 | 0.0006071891191709844 |
| 0.0035053111111111113 | 1 | 16 | 0.0006476683937823834 |
| 0.0035066219444444447 | 1 | 17 | 0.0006881476683937823 |
| 0.0035232194444444445 | 1 | 18 | 0.0007286269430051813 |
| 0.003527115277777778 | 1 | 19 | 0.0007691062176165803 |
| 0.0035484866666666668 | 1 | 20 | 0.0008095854922279792 |
| 0.0035723894444444444 | 1 | 21 | 0.0008500647668393782 |
| 0.003589439166666667 | 1 | 22 | 0.0008905440414507772 |
| 0.0036009255555555556 | 1 | 23 | 0.0009310233160621761 |
| 0.0036471277777777775 | 1 | 24 | 0.0009715025906735751 |
| 0.0036677608333333333 | 1 | 25 | 0.001011981865284974 |

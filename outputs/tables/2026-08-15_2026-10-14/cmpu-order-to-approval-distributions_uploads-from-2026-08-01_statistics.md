# Statistics

CMPU vet diet · CUSTOMER_UPLOAD · Rx created 2026-08-15–2026-10-14 (UTC)

Uploads: 2026-08-01–2026-10-14 · First order with known status other than X

Duration = FIRST_USAGE_APPROVED_DATETIME − ORDER_PLACED_DTTM, hours. One observation per prescription; both timestamps required. Negative durations and all outliers retained. Bins are [lower, upper), aligned to integer hours. Order status is the current snapshot. No prescription-status/deletion filter or approval-date limit. Uploads match expanded RX_ID and numeric CUSTOMER_ID from DIET_PRESCRIPTION upload entities; this does not verify file presence or require upload before approval. These comparisons do not establish causality. Missing approval is not zero duration. Extracted at 2026-10-27T20:54:41.757574+00:00.

| upload_group | N | minimum | p25 | median | p75 | p95 |
| --- | --- | --- | --- | --- | --- | --- |
| Has matching upload | 24247 | 0.00 | 3.66 | 26.43 | 75.09 | 185.36 |
| No matching upload | 5727 | 0.00 | 0.11 | 12.52 | 50.90 | 182.16 |

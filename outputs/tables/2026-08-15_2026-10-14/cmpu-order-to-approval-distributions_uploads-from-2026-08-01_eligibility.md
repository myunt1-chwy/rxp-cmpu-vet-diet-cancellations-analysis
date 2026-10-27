# Eligibility

CMPU vet diet · CUSTOMER_UPLOAD · Rx created 2026-08-15–2026-10-14 (UTC)

Uploads: 2026-08-01–2026-10-14 · First order with known status other than X

Duration = FIRST_USAGE_APPROVED_DATETIME − ORDER_PLACED_DTTM, hours. One observation per prescription; both timestamps required. Negative durations and all outliers retained. Bins are [lower, upper), aligned to integer hours. Order status is the current snapshot. No prescription-status/deletion filter or approval-date limit. Uploads match expanded RX_ID and numeric CUSTOMER_ID from DIET_PRESCRIPTION upload entities; this does not verify file presence or require upload before approval. These comparisons do not establish causality. Missing approval is not zero duration. Extracted at 2026-10-27T20:54:41.757574+00:00.

| upload_group | cohort | No first order ID | First order not found | Unknown order status | Canceled | Missing both timestamps | Missing order timestamp | Missing approval timestamp | Eligible | negative_durations | over_24h | timezone_pairs_checked | timezone_companion_missing |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Has matching upload | 32229 | 3500 | 0 | 0 | 3289 | 0 | 0 | 1193 | 24247 | 0 | 12823 | 28729 | 0 |
| No matching upload | 72078 | 5737 | 0 | 0 | 51084 | 0 | 0 | 9530 | 5727 | 0 | 2227 | 66341 | 0 |

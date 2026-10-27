# Upload source audit

CMPU vet diet · CUSTOMER_UPLOAD · Rx created 2026-08-15–2026-10-14 (UTC)

Uploads: 2026-08-01–2026-10-14 · First order with known status other than X

Duration = FIRST_USAGE_APPROVED_DATETIME − ORDER_PLACED_DTTM, hours. One observation per prescription; both timestamps required. Negative durations and all outliers retained. Bins are [lower, upper), aligned to integer hours. Order status is the current snapshot. No prescription-status/deletion filter or approval-date limit. Uploads match expanded RX_ID and numeric CUSTOMER_ID from DIET_PRESCRIPTION upload entities; this does not verify file presence or require upload before approval. These comparisons do not establish causality. Missing approval is not zero duration. Extracted at 2026-10-27T20:54:41.757574+00:00.

| measure | count |
| --- | --- |
| window_upload_rows | 132156 |
| invalid_upload_source_rows | 0 |
| uploads_missing_customer | 0 |
| uploads_invalid_customer | 0 |
| upload_rows_missing_rx | 0 |
| upload_rows_malformed_rx | 0 |

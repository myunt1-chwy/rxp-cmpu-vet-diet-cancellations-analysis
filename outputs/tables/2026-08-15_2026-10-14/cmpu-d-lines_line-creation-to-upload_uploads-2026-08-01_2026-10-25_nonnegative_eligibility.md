# Eligibility

CMPU vet diet · CUSTOMER_UPLOAD · Rx created 2026-08-15–2026-10-14 (UTC)

Nonnegative durations only · Negative durations excluded

Has matching upload · Uploads 2026-08-01–2026-10-25 (UTC)

Earliest matching upload CREATED_TS_UTC − ORDER_LINE_CREATED_DTTM, hours. Earliest upload is within the stated upload search window. Approval timestamp is not required. Both first-order keys matched; one count per distinct order/order-line pair, current line status D. Shipment rows collapsed to consistent line-creation timestamps. Require a matching DIET_PRESCRIPTION upload entity by expanded RX_ID and numeric CUSTOMER_ID. No file-presence or upload-before-approval requirement. Both timing endpoints required; no approval-date filter. Negative durations excluded from histogram and statistics; retained in details and eligibility audit. All nonnegative outliers retained. Bins are [lower, upper); quantiles use unbinned hours with linear interpolation. Association and distinct-line audit counts have separate denominators; missing endpoints are not zero. Extracted at 2026-10-27T20:58:05.129083+00:00.

| grain | measure | count |
| --- | --- | --- |
| prescription associations before upload filter | Cohort | 104307 |
| prescription associations before upload filter | No matching upload | 71087 |
| upload source | window_upload_rows | 159010 |
| upload source | invalid_upload_source_rows | 0 |
| upload source | uploads_missing_customer | 0 |
| upload source | uploads_invalid_customer | 0 |
| upload source | upload_rows_missing_rx | 0 |
| upload source | upload_rows_malformed_rx | 0 |
| prescription associations | Cohort | 33220 |
| prescription associations | Missing order ID | 3600 |
| prescription associations | Missing line ID | 0 |
| prescription associations | Invalid line ID | 0 |
| prescription associations | Unmatched line | 0 |
| prescription associations | Non-D status | 4671 |
| prescription associations | Missing both timestamps | 0 |
| prescription associations | Missing creation timestamp | 0 |
| prescription associations | Missing upload timestamp | 0 |
| prescription associations | Negative duration | 245 |
| prescription associations | Eligible | 24704 |
| distinct matched lines | Non-D status | 4671 |
| distinct matched lines | Missing both timestamps | 0 |
| distinct matched lines | Missing creation timestamp | 0 |
| distinct matched lines | Missing upload timestamp | 0 |
| distinct matched lines | Negative duration | 245 |
| distinct matched lines | Eligible | 24704 |
| distinct matched lines | Matched | 29620 |
| distinct matched lines | Shipment rows | 29728 |
| distinct matched lines | Repeated prescription associations | 0 |
| distinct matched lines | UTC/Eastern pairs checked | 29620 |
| distinct matched lines | Missing Eastern companion rows | 0 |
| distinct matched lines | Missing approval shipment rows | 4210 |
| eligible lines | Negative durations | 0 |
| eligible lines | Over 24 hours | 12100 |

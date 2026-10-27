# CMPU first-order-line event times: audit

Prescriptions UTC [2026-08-15, 2026-10-15); uploads UTC [2026-08-01, 2026-10-26).

Distinct order/order-line pairs; all statuses and nullable flags retained. Estimate = creation + round(0.96 × approval/denial elapsed nanoseconds), no intercept. Actual upload takes precedence over estimate; populated cancellation caps either. ORDER_CANCEL_DTTM uses the UTC interpretation checked against its Eastern companion in REFNUM 5; this view has no cancellation Eastern companion. Null and negative durations remain. No survival outcomes or censoring rules assigned.

| grain | measure | count |
| --- | --- | --- |
| associations | Cohort | 104307 |
| associations | Missing order ID | 9237 |
| associations | Missing line ID | 0 |
| associations | Invalid line ID | 0 |
| associations | Unmatched line | 0 |
| associations | Matched | 95070 |
| lines | Distinct matched lines | 95070 |
| lines | Shipment rows | 95202 |
| lines | Repeated associations | 0 |
| lines | UTC/Eastern pairs checked | 95070 |
| event_time_source | actual_upload | 29620 |
| event_time_source | estimated_upload | 63453 |
| event_time_source | order_cancellation | 1978 |
| event_time_source | tie | 0 |
| event_time_source | missing | 19 |
| candidate_upload_source | actual_upload | 29620 |
| candidate_upload_source | estimated_upload | 65429 |
| candidate_upload_source | missing | 21 |
| line_status | X | 65053 |
| line_status | D | 29929 |
| line_status | C | 56 |
| line_status | S | 29 |
| line_status | R | 3 |
| is_deleted | False | 95070 |
| is_refill | False | 94674 |
| is_refill | True | 396 |
| quality | missing_creation | 0 |
| quality | missing_event | 19 |
| quality | missing_estimate | 27 |
| quality | negative_duration | 280 |
| quality | negative_approval_interval | 0 |
| quality | Missing Eastern companion rows | 0 |
| quality | Missing approval shipment rows | 27 |
| quality | Multiple populated approval minima | 0 |
| upload source | window_upload_rows | 159010 |
| upload source | invalid_upload_source_rows | 0 |
| upload source | uploads_missing_customer | 0 |
| upload source | uploads_invalid_customer | 0 |
| upload source | upload_rows_missing_rx | 0 |
| upload source | upload_rows_malformed_rx | 0 |

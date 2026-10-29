-- One row per cohort prescription. Both creation and upload windows are UTC.
WITH prescriptions AS (
    SELECT rx_id, customer_id, rx_creation_datetime, approval_channel, first_order_id, first_usage_approved_datetime,
           COUNT(*) OVER (PARTITION BY rx_id) AS rx_source_rows
    FROM EDLDB.BT_HCA_HCDM.RXP_PRESCRIPTIONS
    WHERE prescription_source = 'CMPU' AND is_vet_diet_flag = TRUE AND approval_channel = 'CUSTOMER_UPLOAD'
      AND rx_creation_datetime >= '{{ start_date }}'::TIMESTAMP_NTZ
      AND rx_creation_datetime < '{{ end_date }}'::TIMESTAMP_NTZ
), orders AS (
    SELECT o.order_id, COUNT(*) AS order_source_rows,
           MIN(o.order_status) AS order_status,
           MIN(o.order_placed_dttm) AS order_placed_at_utc,
           MIN(o.order_placed_dttm_est) AS order_placed_at_eastern,
           MIN(o.order_status_description) AS order_status_description,
           MIN(o.order_cancel_reason) AS order_cancel_reason
    FROM EDLDB.ECOM.ORDERS o
    JOIN (SELECT DISTINCT first_order_id FROM prescriptions WHERE first_order_id IS NOT NULL) p
      ON o.order_id = p.first_order_id
    GROUP BY o.order_id
), upload_source AS (
    SELECT upload_id, customer_id AS raw_customer_id, rx_id AS rx_ids, created_ts_utc, state_name, state_changed_ts_utc,
           CASE WHEN REGEXP_LIKE(TRIM(customer_id), '^[0-9]+$')
                THEN TRY_TO_NUMBER(customer_id) END AS customer_id,
           COUNT(*) OVER (PARTITION BY upload_id) AS upload_source_rows
    FROM EDLDB.BT_HCA_HCDM.RXP_UPLOAD_ENTITY
    WHERE upload_type = 'DIET_PRESCRIPTION'
      AND created_ts_utc >= '{{ upload_start_date }}'::TIMESTAMP_NTZ
      AND created_ts_utc < '{{ end_date }}'::TIMESTAMP_NTZ
), expanded AS (
    SELECT DISTINCT u.upload_id, u.customer_id, u.created_ts_utc, u.state_name, u.state_changed_ts_utc,
           NULLIF(TRIM(t.value::VARCHAR), '') AS rx_id
    FROM upload_source u,
         LATERAL FLATTEN(INPUT => SPLIT(TRIM(COALESCE(u.rx_ids, ''), '{}'), ','), OUTER => TRUE) t
), ranked_uploads AS (
    SELECT *, ROW_NUMBER() OVER (
        PARTITION BY rx_id, customer_id ORDER BY created_ts_utc, upload_id
    ) AS upload_rank
    FROM expanded
    WHERE customer_id IS NOT NULL AND REGEXP_LIKE(rx_id, '^[A-Za-z0-9_-]+$')
      AND state_name = 'ACCEPTED'
), uploads AS (
    SELECT rx_id, customer_id, COUNT(DISTINCT upload_id) AS upload_count,
           COUNT(DISTINCT CASE WHEN created_ts_utc >= '{{ start_date }}'::TIMESTAMP_NTZ
                               THEN upload_id END) AS cohort_window_upload_count,
           MIN(created_ts_utc) AS first_upload_at_utc,
           MAX(IFF(upload_rank=1, upload_id, NULL)) AS selected_upload_id,
           MAX(IFF(upload_rank=1, state_changed_ts_utc, NULL)) AS upload_state_changed_at_utc,
           MIN(state_name) AS selected_upload_state
    FROM ranked_uploads
    GROUP BY rx_id, customer_id
), audit AS (
    SELECT COUNT(*) AS window_upload_rows,
           COUNT_IF(state_name='ACCEPTED') AS accepted_window_upload_rows,
           COUNT_IF(state_name IS NULL OR state_name<>'ACCEPTED') AS excluded_window_upload_rows,
           COALESCE(COUNT_IF(upload_id IS NULL OR upload_source_rows <> 1), 0) AS invalid_upload_source_rows,
           COALESCE(COUNT_IF(NULLIF(TRIM(raw_customer_id), '') IS NULL), 0) AS uploads_missing_customer,
           COALESCE(COUNT_IF(NULLIF(TRIM(raw_customer_id), '') IS NOT NULL AND customer_id IS NULL), 0) AS uploads_invalid_customer,
           (SELECT COUNT(*) FROM expanded WHERE rx_id IS NULL) AS upload_rows_missing_rx,
           (SELECT COUNT(*) FROM expanded WHERE rx_id IS NOT NULL
            AND NOT REGEXP_LIKE(rx_id, '^[A-Za-z0-9_-]+$')) AS upload_rows_malformed_rx
    FROM upload_source
)
SELECT CURRENT_TIMESTAMP::VARCHAR AS extracted_at_session_time,
       CURRENT_WAREHOUSE() AS extraction_warehouse,
       p.*, COALESCE(o.order_source_rows, 0) AS order_source_rows,
       o.order_status, o.order_placed_at_utc, o.order_placed_at_eastern,
       o.order_status_description, o.order_cancel_reason,
       COALESCE(u.upload_count, 0) AS upload_count,
       COALESCE(u.cohort_window_upload_count, 0) AS cohort_window_upload_count,
       u.first_upload_at_utc, u.selected_upload_id, u.selected_upload_state, u.upload_state_changed_at_utc,
       a.*
FROM prescriptions p
LEFT JOIN orders o ON p.first_order_id = o.order_id
LEFT JOIN uploads u ON p.rx_id = u.rx_id AND p.customer_id = u.customer_id
CROSS JOIN audit a

-- Compare FIRST_ORDER_ID against upload-entity and usage-history order IDs.
WITH prescriptions AS (
    SELECT rx_id, customer_id, approval_channel, first_order_id,
           COUNT(*) OVER (PARTITION BY rx_id) AS rx_source_rows
    FROM EDLDB.BT_HCA_HCDM.RXP_PRESCRIPTIONS
    WHERE prescription_source = 'CMPU' AND is_vet_diet_flag = TRUE
      AND rx_creation_datetime >= '{{ start_date }}'::TIMESTAMP_NTZ
      AND rx_creation_datetime < '{{ end_date }}'::TIMESTAMP_NTZ
), usage_records AS (
    SELECT a.rx_id, a.order_id AS raw_order_id,
           CASE WHEN REGEXP_LIKE(TRIM(a.order_id), '^[0-9]+$')
                THEN TRY_TO_NUMBER(a.order_id) END AS order_id
    FROM EDLDB.BT_HCA_HCDM.RXP_RX_USAGE_ACTIONS a
    JOIN prescriptions p ON a.rx_id = p.rx_id
), usage_summary AS (
    SELECT u.rx_id, COUNT(DISTINCT u.order_id) AS usage_order_count,
           COUNT(DISTINCT CASE WHEN u.order_id = p.first_order_id THEN u.order_id END) AS usage_same_order_count,
           COUNT(DISTINCT CASE WHEN p.first_order_id IS NOT NULL AND u.order_id <> p.first_order_id
                               THEN u.order_id END) AS usage_different_order_count,
           MAX(IFF(NULLIF(TRIM(u.raw_order_id), '') IS NULL, 1, 0)) AS usage_missing_order_id,
           MAX(IFF(NULLIF(TRIM(u.raw_order_id), '') IS NOT NULL AND u.order_id IS NULL, 1, 0)) AS usage_invalid_order_id
    FROM usage_records u JOIN prescriptions p ON u.rx_id = p.rx_id
    GROUP BY u.rx_id
), upload_source AS (
    SELECT upload_id, rx_id AS rx_ids,
           CASE WHEN REGEXP_LIKE(TRIM(customer_id), '^[0-9]+$') THEN TRY_TO_NUMBER(customer_id) END AS customer_id,
           order_id AS raw_order_id,
           CASE WHEN REGEXP_LIKE(TRIM(order_id), '^[0-9]+$') THEN TRY_TO_NUMBER(order_id) END AS order_id,
           COUNT(*) OVER (PARTITION BY upload_id) AS upload_source_rows
    FROM EDLDB.BT_HCA_HCDM.RXP_UPLOAD_ENTITY
    WHERE upload_type = 'DIET_PRESCRIPTION'
      AND created_ts_utc >= '{{ upload_start_date }}'::TIMESTAMP_NTZ
      AND created_ts_utc < '{{ end_date }}'::TIMESTAMP_NTZ
), expanded AS (
    SELECT DISTINCT u.*, NULLIF(TRIM(t.value::VARCHAR), '') AS rx_id
    FROM upload_source u,
         LATERAL FLATTEN(INPUT => SPLIT(TRIM(COALESCE(u.rx_ids, ''), '{}'), ','), OUTER => TRUE) t
), upload_summary AS (
    SELECT p.rx_id, COUNT(DISTINCT u.upload_id) AS upload_count,
           COUNT(DISTINCT u.order_id) AS upload_order_count,
           COUNT(DISTINCT CASE WHEN u.order_id = p.first_order_id THEN u.order_id END) AS upload_same_order_count,
           COUNT(DISTINCT CASE WHEN p.first_order_id IS NOT NULL AND u.order_id <> p.first_order_id
                               THEN u.order_id END) AS upload_different_order_count,
           COUNT(DISTINCT CASE WHEN NULLIF(TRIM(u.raw_order_id), '') IS NULL THEN u.upload_id END) AS uploads_missing_order_id,
           COUNT(DISTINCT CASE WHEN NULLIF(TRIM(u.raw_order_id), '') IS NOT NULL AND u.order_id IS NULL
                               THEN u.upload_id END) AS uploads_invalid_order_id,
           MAX(u.upload_source_rows) AS max_upload_source_rows
    FROM prescriptions p JOIN expanded u ON p.rx_id = u.rx_id AND p.customer_id = u.customer_id
    GROUP BY p.rx_id
)
SELECT CURRENT_TIMESTAMP::VARCHAR AS extracted_at_session_time,
       p.*, COALESCE(u.usage_order_count, 0) AS usage_order_count,
       COALESCE(u.usage_same_order_count, 0) AS usage_same_order_count,
       COALESCE(u.usage_different_order_count, 0) AS usage_different_order_count,
       COALESCE(u.usage_missing_order_id, 0) AS usage_missing_order_id,
       COALESCE(u.usage_invalid_order_id, 0) AS usage_invalid_order_id,
       COALESCE(a.upload_count, 0) AS upload_count,
       COALESCE(a.upload_order_count, 0) AS upload_order_count,
       COALESCE(a.upload_same_order_count, 0) AS upload_same_order_count,
       COALESCE(a.upload_different_order_count, 0) AS upload_different_order_count,
       COALESCE(a.uploads_missing_order_id, 0) AS uploads_missing_order_id,
       COALESCE(a.uploads_invalid_order_id, 0) AS uploads_invalid_order_id,
       COALESCE(a.max_upload_source_rows, 0) AS max_upload_source_rows
FROM prescriptions p
LEFT JOIN usage_summary u ON p.rx_id = u.rx_id
LEFT JOIN upload_summary a ON p.rx_id = a.rx_id

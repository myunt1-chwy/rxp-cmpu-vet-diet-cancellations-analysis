-- Same timing cohort and shipment collapse as REFNUM 16, enriched with upload evidence.
WITH timing AS (
{{ timing_sql }}
), upload_source AS (
    SELECT upload_id, customer_id AS raw_customer_id, rx_id AS rx_ids, created_ts_utc,
           CASE WHEN REGEXP_LIKE(TRIM(customer_id), '^[0-9]+$')
                THEN TRY_TO_NUMBER(customer_id) END AS customer_id,
           COUNT(*) OVER (PARTITION BY upload_id) AS upload_source_rows
    FROM EDLDB.BT_HCA_HCDM.RXP_UPLOAD_ENTITY
    WHERE upload_type = 'DIET_PRESCRIPTION'
      AND created_ts_utc >= '{{ upload_start_date }}'::TIMESTAMP_NTZ
      -- Upload evidence may arrive 11 days beyond the prescription window.
      AND created_ts_utc < '{{ upload_end_date }}'::TIMESTAMP_NTZ
), expanded AS (
    SELECT DISTINCT u.upload_id, u.customer_id, u.created_ts_utc,
           NULLIF(TRIM(t.value::VARCHAR), '') AS rx_id
    FROM upload_source u,
         LATERAL FLATTEN(INPUT => SPLIT(TRIM(COALESCE(u.rx_ids, ''), '{}'), ','), OUTER => TRUE) t
), uploads AS (
    SELECT rx_id, customer_id, COUNT(DISTINCT upload_id) AS upload_count,
           MIN(created_ts_utc) AS first_upload_at_utc
    FROM expanded
    WHERE customer_id IS NOT NULL AND REGEXP_LIKE(rx_id, '^[A-Za-z0-9_-]+$')
    GROUP BY rx_id, customer_id
), audit AS (
    SELECT COUNT(*) AS window_upload_rows,
           COALESCE(COUNT_IF(upload_id IS NULL OR upload_source_rows <> 1), 0) AS invalid_upload_source_rows,
           COALESCE(COUNT_IF(NULLIF(TRIM(raw_customer_id), '') IS NULL), 0) AS uploads_missing_customer,
           COALESCE(COUNT_IF(NULLIF(TRIM(raw_customer_id), '') IS NOT NULL AND customer_id IS NULL), 0) AS uploads_invalid_customer,
           (SELECT COUNT(*) FROM expanded WHERE rx_id IS NULL) AS upload_rows_missing_rx,
           (SELECT COUNT(*) FROM expanded WHERE rx_id IS NOT NULL
            AND NOT REGEXP_LIKE(rx_id, '^[A-Za-z0-9_-]+$')) AS upload_rows_malformed_rx
    FROM upload_source
)
SELECT t.*, COALESCE(u.upload_count, 0) AS upload_count, u.first_upload_at_utc, a.*
FROM timing t
JOIN EDLDB.BT_HCA_HCDM.RXP_PRESCRIPTIONS p ON t.rx_id = p.rx_id
LEFT JOIN uploads u ON t.rx_id = u.rx_id AND p.customer_id = u.customer_id
CROSS JOIN audit a

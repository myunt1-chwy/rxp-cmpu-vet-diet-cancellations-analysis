-- REFNUM 16: preserve unmatched prescriptions for eligibility auditing.
-- Timestamps are UTC except the explicit Eastern wall-clock companion.
WITH prescriptions AS (
    SELECT rx_id, rx_creation_datetime, approval_channel, first_order_id, first_orderitem_id,
           CASE WHEN REGEXP_LIKE(TRIM(first_orderitem_id), '^[0-9]+$')
                THEN TRY_TO_NUMBER(first_orderitem_id) END AS first_order_line_id,
           COUNT(*) OVER (PARTITION BY rx_id) AS rx_source_rows
    FROM EDLDB.BT_HCA_HCDM.RXP_PRESCRIPTIONS
    WHERE prescription_source = 'CMPU' AND is_vet_diet_flag = TRUE
      AND approval_channel = 'CUSTOMER_UPLOAD'
      AND rx_creation_datetime >= '{{ start_date }}'::TIMESTAMP_NTZ
      AND rx_creation_datetime < '{{ end_date }}'::TIMESTAMP_NTZ
), lines AS (
    SELECT o.order_id, o.order_line_id, COUNT(*) AS shipment_rows,
           MIN(o.order_order_line_status) AS line_status,
           COUNT(DISTINCT COALESCE(o.order_order_line_status, '[Missing]')) AS status_variants,
           MIN(o.order_line_created_dttm) AS line_created_utc,
           COUNT(DISTINCT o.order_line_created_dttm)
             + CASE WHEN COUNT_IF(o.order_line_created_dttm IS NULL) > 0 THEN 1 ELSE 0 END AS creation_variants,
           MIN(o.order_line_created_dttm_est) AS line_created_eastern,
           COUNT(DISTINCT o.order_line_created_dttm_est) AS eastern_variants,
           COUNT_IF(o.order_line_created_dttm_est IS NULL) AS missing_eastern_rows,
           MAX(o.max_approved_datetime) AS max_approved_datetime,
           COUNT_IF(o.max_approved_datetime IS NULL) AS missing_approval_rows,
           COUNT(DISTINCT o.max_approved_datetime) AS approval_variants
    FROM EDLDB.BT_HCA_HCDM.ORDER_LINE_COST_MEASURES_RXP o
    JOIN (SELECT DISTINCT first_order_id, first_order_line_id FROM prescriptions
          WHERE first_order_id IS NOT NULL AND first_order_line_id IS NOT NULL) p
      ON o.order_id = p.first_order_id AND o.order_line_id = p.first_order_line_id
    GROUP BY o.order_id, o.order_line_id
)
SELECT CURRENT_TIMESTAMP::VARCHAR AS extracted_at_session_time,
       CURRENT_WAREHOUSE() AS extraction_warehouse, p.*,
       l.*
FROM prescriptions p
LEFT JOIN lines l ON p.first_order_id = l.order_id AND p.first_order_line_id = l.order_line_id

-- REFNUM 23 same-pet matching. Seven- and fourteen-day populations in one snapshot. First-order-line cohort; all matching-key windows are UTC.
-- Recorded Aged Order reason establishes cohort membership, not line status alone.
WITH horizons AS (
    SELECT 7 AS followup_days UNION ALL SELECT 14
), prescriptions AS (
    SELECT rx_id, customer_id, product_id, rx_creation_datetime, approval_channel,
           first_order_id, first_orderitem_id,
           CASE WHEN REGEXP_LIKE(TRIM(first_orderitem_id), '^[0-9]+$')
                THEN TRY_TO_NUMBER(first_orderitem_id) END AS first_order_line_id,
           COUNT(*) OVER (PARTITION BY rx_id) AS rx_source_rows
    FROM EDLDB.BT_HCA_HCDM.RXP_PRESCRIPTIONS
    WHERE prescription_source = 'CMPU' AND is_vet_diet_flag = TRUE
      AND approval_channel = 'CUSTOMER_UPLOAD'
      AND rx_creation_datetime >= '{{ start_date }}'::TIMESTAMP_NTZ
      AND rx_creation_datetime < '{{ end_date }}'::TIMESTAMP_NTZ
), catalog_latest AS (
    SELECT part_number, product_id
    FROM EDLDB.PDM.PRODUCT
    QUALIFY DENSE_RANK() OVER (PARTITION BY part_number
                              ORDER BY snapshot_date DESC, last_updated_dttm DESC) = 1
), product_mapping AS (
    SELECT part_number, MIN(product_id) AS product_id,
           COUNT(DISTINCT product_id) AS product_variants
    FROM catalog_latest GROUP BY part_number
), originals AS (
    SELECT l.order_id AS original_order_id, l.order_line_id AS original_line_id,
           MIN(l.customer_id) AS original_customer_id,
           MIN(l.pet_id) AS original_pet_id,
           COUNT(DISTINCT l.pet_id) + IFF(COUNT_IF(l.pet_id IS NULL)>0,1,0) AS original_pet_variants,
           COUNT(DISTINCT l.customer_id) + IFF(COUNT_IF(l.customer_id IS NULL)>0,1,0) AS original_customer_variants,
           MIN(m.product_id) AS original_product_id,
           GREATEST(COUNT(DISTINCT m.product_id), COALESCE(MAX(m.product_variants),0)) AS original_product_variants,
           COUNT(*) AS original_shipment_rows,
           MIN(l.order_order_line_status) AS original_line_status,
           COUNT(DISTINCT l.order_order_line_status) + IFF(COUNT_IF(l.order_order_line_status IS NULL)>0,1,0) AS original_status_variants,
           MIN(l.order_cancel_reason) AS order_cancel_reason,
           COUNT(DISTINCT LOWER(TRIM(l.order_cancel_reason))) + IFF(COUNT_IF(l.order_cancel_reason IS NULL)>0,1,0) AS original_reason_variants,
           MIN(l.order_cancel_dttm) AS order_cancel_time,
           COUNT(DISTINCT l.order_cancel_dttm) AS original_cancel_variants
    FROM EDLDB.BT_HCA_HCDM.ORDER_LINE_COST_MEASURES_RXP l
    JOIN (SELECT DISTINCT first_order_id, first_order_line_id FROM prescriptions
          WHERE first_order_id IS NOT NULL AND first_order_line_id IS NOT NULL) p
      ON l.order_id = p.first_order_id AND l.order_line_id = p.first_order_line_id
    LEFT JOIN product_mapping m ON l.product_part_number = m.part_number
    GROUP BY l.order_id, l.order_line_id
), aged AS (
    SELECT * FROM originals
    WHERE LOWER(TRIM(order_cancel_reason)) = 'aged order'
      AND order_cancel_time IS NOT NULL AND order_cancel_time <= '{{ as_of_date }}'::TIMESTAMP_NTZ
), candidate_keys AS (
    -- Find keys first, then fetch ALL their shipment rows for conflict checks.
    SELECT DISTINCT l.order_id, l.order_line_id
    FROM EDLDB.BT_HCA_HCDM.ORDER_LINE_COST_MEASURES_RXP l
    JOIN product_mapping m ON l.product_part_number = m.part_number
    JOIN aged a ON l.customer_id = a.original_customer_id AND m.product_id = a.original_product_id
               AND l.order_id <> a.original_order_id
               AND l.order_placed_dttm > a.order_cancel_time
               AND l.order_placed_dttm <= DATEADD(day, 14, a.order_cancel_time)
               AND DATEADD(day, 7, a.order_cancel_time) <= '{{ as_of_date }}'::TIMESTAMP_NTZ
               AND l.order_placed_dttm <= '{{ as_of_date }}'::TIMESTAMP_NTZ
), reorders AS (
    SELECT l.order_id AS reorder_order_id, l.order_line_id AS reorder_line_id,
           MIN(l.customer_id) AS reorder_customer_id,
           MIN(l.pet_id) AS reorder_pet_id,
           COUNT(DISTINCT l.pet_id) + IFF(COUNT_IF(l.pet_id IS NULL)>0,1,0) AS reorder_pet_variants,
           COUNT(DISTINCT l.customer_id) + IFF(COUNT_IF(l.customer_id IS NULL)>0,1,0) AS reorder_customer_variants,
           MIN(m.product_id) AS reorder_product_id,
           GREATEST(COUNT(DISTINCT m.product_id),COALESCE(MAX(m.product_variants),0)) AS reorder_product_variants,
           COUNT(*) AS reorder_shipment_rows,
           MIN(l.order_order_line_status) AS reorder_line_status,
           COUNT(DISTINCT l.order_order_line_status) + IFF(COUNT_IF(l.order_order_line_status IS NULL)>0,1,0) AS reorder_status_variants,
           MIN(l.order_placed_dttm) AS reorder_placed_at_utc,
           MIN(l.order_placed_dttm_est) AS reorder_placed_at_eastern,
           COUNT(DISTINCT l.order_placed_dttm) + IFF(COUNT_IF(l.order_placed_dttm IS NULL)>0,1,0) AS reorder_placement_variants,
           MIN(l.order_line_shipped_dttm) AS reorder_shipped_at_utc,
           MIN(l.order_line_shipped_dttm_est) AS reorder_shipped_at_eastern
    FROM EDLDB.BT_HCA_HCDM.ORDER_LINE_COST_MEASURES_RXP l
    JOIN candidate_keys k ON l.order_id=k.order_id AND l.order_line_id=k.order_line_id
    LEFT JOIN product_mapping m ON l.product_part_number=m.part_number
    GROUP BY l.order_id,l.order_line_id
)
SELECT CURRENT_TIMESTAMP::VARCHAR AS extracted_at_session_time,
       CURRENT_WAREHOUSE() AS extraction_warehouse, h.followup_days,
       (SELECT COUNT(*) FROM reorders) AS candidate_reorder_lines,
       (SELECT COALESCE(COUNT_IF(reorder_pet_id IS NULL),0) FROM reorders) AS candidate_missing_pet_lines,
       (SELECT COALESCE(COUNT_IF(reorder_pet_variants>1),0) FROM reorders) AS candidate_ambiguous_pet_lines,
       TO_CHAR(DATEADD(day, h.followup_days, a.order_cancel_time),
               'YYYY-MM-DD HH24:MI:SS.FF9') AS window_end_utc,
       IFF(DATEADD(day, h.followup_days, a.order_cancel_time) <= '{{ as_of_date }}'::TIMESTAMP_NTZ,
           TRUE, FALSE) AS followup_complete,
       p.* REPLACE(TO_CHAR(rx_creation_datetime,'YYYY-MM-DD HH24:MI:SS.FF9') AS rx_creation_datetime),
       a.* REPLACE(TO_CHAR(order_cancel_time,'YYYY-MM-DD HH24:MI:SS.FF9') AS order_cancel_time),
       r.* REPLACE(TO_CHAR(reorder_placed_at_utc,'YYYY-MM-DD HH24:MI:SS.FF9') AS reorder_placed_at_utc,
                   TO_CHAR(reorder_placed_at_eastern,'YYYY-MM-DD HH24:MI:SS.FF9') AS reorder_placed_at_eastern,
                   TO_CHAR(reorder_shipped_at_utc,'YYYY-MM-DD HH24:MI:SS.FF9') AS reorder_shipped_at_utc,
                   TO_CHAR(reorder_shipped_at_eastern,'YYYY-MM-DD HH24:MI:SS.FF9') AS reorder_shipped_at_eastern)
FROM prescriptions p
CROSS JOIN horizons h
LEFT JOIN originals a ON p.first_order_id=a.original_order_id AND p.first_order_line_id=a.original_line_id
LEFT JOIN reorders r ON LOWER(TRIM(a.order_cancel_reason)) = 'aged order'
                   AND a.original_customer_id=r.reorder_customer_id AND a.original_product_id=r.reorder_product_id
                   AND a.original_pet_id IS NOT NULL AND r.reorder_pet_id IS NOT NULL
                   AND a.original_pet_variants=1 AND r.reorder_pet_variants=1
                   AND a.original_pet_id=r.reorder_pet_id
                   AND a.original_order_id<>r.reorder_order_id
                   AND r.reorder_placed_at_utc>a.order_cancel_time
                   AND r.reorder_placed_at_utc<=DATEADD(day,h.followup_days,a.order_cancel_time)
                   AND DATEADD(day,h.followup_days,a.order_cancel_time)<='{{ as_of_date }}'::TIMESTAMP_NTZ
                   AND r.reorder_placed_at_utc<='{{ as_of_date }}'::TIMESTAMP_NTZ

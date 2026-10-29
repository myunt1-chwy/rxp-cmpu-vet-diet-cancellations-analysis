-- REFNUM 54: uploaded-document counts for the report population table. Current entities; discovery uses creation, never state-change time.
WITH prescriptions AS (
    SELECT DISTINCT rx_id, customer_id, rx_creation_datetime, approval_channel, first_order_id, first_orderitem_id,
           CASE WHEN REGEXP_LIKE(TRIM(first_orderitem_id), '^[0-9]+$')
                THEN TRY_TO_NUMBER(first_orderitem_id) END AS first_order_line_id
    FROM EDLDB.BT_HCA_HCDM.RXP_PRESCRIPTIONS
    WHERE prescription_source = 'CMPU' AND is_vet_diet_flag = TRUE
      AND rx_creation_datetime >= '2026-08-15'::TIMESTAMP_NTZ
      AND rx_creation_datetime < '2026-10-15'::TIMESTAMP_NTZ
), upload_source AS (
    SELECT upload_id, customer_id AS raw_customer_id, rx_id AS rx_ids,
           created_ts_utc, state_name, state_changed_ts_utc,
           CASE WHEN REGEXP_LIKE(TRIM(customer_id), '^[0-9]+$')
                THEN TRY_TO_NUMBER(customer_id) END AS upload_customer_id
    FROM EDLDB.BT_HCA_HCDM.RXP_UPLOAD_ENTITY
    WHERE upload_type = 'DIET_PRESCRIPTION'
), expanded AS (
    SELECT u.*, NULLIF(TRIM(t.value::VARCHAR), '') AS upload_rx_id
    FROM upload_source u,
         LATERAL FLATTEN(INPUT => SPLIT(TRIM(COALESCE(u.rx_ids, ''), '{}'), ','), OUTER => TRUE) t
), candidates AS (
    SELECT DISTINCT e.upload_id
    FROM expanded e JOIN prescriptions p
      ON e.upload_rx_id = p.rx_id AND e.upload_customer_id = p.customer_id
    WHERE REGEXP_LIKE(e.upload_rx_id, '^[A-Za-z0-9_-]+$')
      AND ((e.created_ts_utc >= '2026-08-01'::TIMESTAMP_NTZ
        AND e.created_ts_utc < '2026-10-26'::TIMESTAMP_NTZ)
        OR e.created_ts_utc IS NULL)
), lines AS (
    SELECT l.order_id, l.order_line_id, COUNT(*) AS shipment_rows,
           MIN(l.order_placed_dttm) AS order_placed_utc,
           COUNT(DISTINCT l.order_placed_dttm)
             + IFF(COUNT_IF(l.order_placed_dttm IS NULL)>0,1,0) AS placement_variants,
           MIN(l.order_cancel_reason) AS order_cancel_reason,
           COUNT(DISTINCT LOWER(TRIM(l.order_cancel_reason)))
             + IFF(COUNT_IF(l.order_cancel_reason IS NULL)>0,1,0) AS reason_variants,
           MIN(l.order_cancel_dttm) AS order_cancel_time,
           COUNT(DISTINCT l.order_cancel_dttm) AS cancel_variants
    FROM EDLDB.BT_HCA_HCDM.ORDER_LINE_COST_MEASURES_RXP l
    JOIN (SELECT DISTINCT first_order_id, first_order_line_id FROM prescriptions) p
      ON l.order_id = p.first_order_id AND l.order_line_id = p.first_order_line_id
    GROUP BY l.order_id, l.order_line_id
)
-- Fetch ALL source versions for discovered IDs so conflicts cannot be hidden by
-- the window, customer or RX join. Null creation is retained as unknown-window.
SELECT CURRENT_TIMESTAMP::VARCHAR AS extracted_at_session_time,
       CURRENT_WAREHOUSE() AS extraction_warehouse,
       e.upload_id, e.raw_customer_id, e.upload_customer_id, e.rx_ids, e.upload_rx_id,
       e.state_name,
       TO_CHAR(e.created_ts_utc,'YYYY-MM-DD HH24:MI:SS.FF9') AS created_ts_utc,
       TO_CHAR(e.state_changed_ts_utc,'YYYY-MM-DD HH24:MI:SS.FF9') AS state_changed_ts_utc,
       p.rx_id AS matched_rx_id, p.customer_id AS rx_customer_id, p.approval_channel,
       TO_CHAR(p.rx_creation_datetime,'YYYY-MM-DD HH24:MI:SS.FF9') AS rx_creation_datetime,
       p.first_order_id, p.first_orderitem_id, p.first_order_line_id,
       l.order_id AS matched_order_id, l.order_line_id AS matched_order_line_id,
       l.shipment_rows,
       TO_CHAR(l.order_placed_utc,'YYYY-MM-DD HH24:MI:SS.FF9') AS order_placed_utc,
       l.placement_variants, l.order_cancel_reason, l.reason_variants, l.cancel_variants,
       TO_CHAR(l.order_cancel_time,'YYYY-MM-DD HH24:MI:SS.FF9') AS order_cancel_time,
       IFF(LOWER(TRIM(l.order_cancel_reason)) = 'aged order'
           AND l.order_cancel_time <= '2026-10-27'::TIMESTAMP_NTZ, TRUE, FALSE) AS aged_association
FROM expanded e
JOIN candidates c ON e.upload_id IS NOT DISTINCT FROM c.upload_id
LEFT JOIN prescriptions p ON e.upload_rx_id = p.rx_id AND e.upload_customer_id = p.customer_id
                         AND REGEXP_LIKE(e.upload_rx_id, '^[A-Za-z0-9_-]+$')
LEFT JOIN lines l ON p.first_order_id = l.order_id AND p.first_order_line_id = l.order_line_id

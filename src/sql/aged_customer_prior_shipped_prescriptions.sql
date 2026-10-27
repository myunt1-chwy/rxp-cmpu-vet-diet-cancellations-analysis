-- REFNUM 35. Only the two certified prescription/order-line views are used.
-- Prescription creation, order cancellation and shipment timestamps are UTC.
WITH prescriptions AS (
    SELECT rx_id, customer_id AS rx_customer_id, first_order_id, first_orderitem_id,
           CASE WHEN REGEXP_LIKE(TRIM(first_orderitem_id), '^[0-9]+$')
                THEN TRY_TO_NUMBER(first_orderitem_id) END AS first_order_line_id,
           TO_CHAR(rx_creation_datetime,'YYYY-MM-DD HH24:MI:SS.FF9') AS rx_creation_datetime,
           COUNT(*) OVER (PARTITION BY rx_id) AS rx_source_rows
    FROM EDLDB.BT_HCA_HCDM.RXP_PRESCRIPTIONS
    WHERE prescription_source='CMPU' AND is_vet_diet_flag=TRUE AND approval_channel='CUSTOMER_UPLOAD'
      AND rx_creation_datetime >= '{{ start_date }}'::TIMESTAMP_NTZ
      AND rx_creation_datetime < '{{ end_date }}'::TIMESTAMP_NTZ
), lines AS (
    SELECT l.order_id, l.order_line_id, MIN(l.customer_id) AS customer_id,
           COUNT(DISTINCT l.customer_id)+IFF(COUNT_IF(l.customer_id IS NULL)>0,1,0) AS customer_variants,
           MIN(LOWER(TRIM(l.order_cancel_reason))) AS order_cancel_reason,
           COUNT(DISTINCT LOWER(TRIM(l.order_cancel_reason)))
               +IFF(COUNT_IF(l.order_cancel_reason IS NULL)>0,1,0) AS reason_variants,
           MIN(l.order_cancel_dttm) AS order_cancel_time,
           COUNT(DISTINCT l.order_cancel_dttm) AS cancel_variants, COUNT(*) AS shipment_rows
    FROM EDLDB.BT_HCA_HCDM.ORDER_LINE_COST_MEASURES_RXP l
    JOIN (SELECT DISTINCT first_order_id, first_order_line_id FROM prescriptions
          WHERE first_order_id IS NOT NULL AND first_order_line_id IS NOT NULL) p
      ON l.order_id=p.first_order_id AND l.order_line_id=p.first_order_line_id
    GROUP BY l.order_id,l.order_line_id
), associations AS (
    SELECT p.*, l.* REPLACE(TO_CHAR(order_cancel_time,'YYYY-MM-DD HH24:MI:SS.FF9') AS order_cancel_time)
    FROM prescriptions p LEFT JOIN lines l
      ON p.first_order_id=l.order_id AND p.first_order_line_id=l.order_line_id
), customers AS (
    SELECT customer_id, MIN(order_cancel_time) AS reference_cancel_time
    FROM lines
    WHERE order_cancel_reason='aged order' AND order_cancel_time IS NOT NULL
      AND order_cancel_time <= '{{ as_of_date }}'::TIMESTAMP_NTZ AND customer_id IS NOT NULL
    GROUP BY customer_id
), candidate_keys AS (
    -- Candidate discovery is time-bounded; fetch all their shipment rows before collapsing.
    SELECT DISTINCT l.order_id,l.order_line_id
    FROM EDLDB.BT_HCA_HCDM.ORDER_LINE_COST_MEASURES_RXP l
    JOIN customers c ON l.customer_id=c.customer_id
    WHERE l.order_line_shipped_dttm < c.reference_cancel_time
), historical_lines AS (
    SELECT l.order_id,l.order_line_id,l.rx_id,
           MIN(l.customer_id) AS shipment_customer_id,
           COUNT(DISTINCT l.customer_id)+IFF(COUNT_IF(l.customer_id IS NULL)>0,1,0) AS customer_variants,
           MIN(l.order_line_shipped_dttm) AS shipped_at_utc, COUNT(*) AS shipment_rows
    FROM EDLDB.BT_HCA_HCDM.ORDER_LINE_COST_MEASURES_RXP l
    JOIN candidate_keys k ON l.order_id=k.order_id AND l.order_line_id=k.order_line_id
    GROUP BY l.order_id,l.order_line_id,l.rx_id
), historical_prescriptions AS (
    SELECT r.rx_id, MIN(r.customer_id) AS rx_customer_id, COUNT(*) AS rx_source_rows,
           ANY_VALUE(r.is_vet_diet_flag) AS is_vet_diet_flag,
           ANY_VALUE(r.prescription_source) AS prescription_source,
           ANY_VALUE(r.merch_class2) AS merch_class2
    FROM EDLDB.BT_HCA_HCDM.RXP_PRESCRIPTIONS r
    JOIN (SELECT DISTINCT rx_id FROM historical_lines WHERE rx_id IS NOT NULL) h ON r.rx_id=h.rx_id
    GROUP BY r.rx_id
), history AS (
    SELECT h.* REPLACE(TO_CHAR(shipped_at_utc,'YYYY-MM-DD HH24:MI:SS.FF9') AS shipped_at_utc),
           r.rx_customer_id, COALESCE(r.rx_source_rows,0) AS rx_source_rows,
           r.is_vet_diet_flag,r.prescription_source,r.merch_class2
    FROM historical_lines h LEFT JOIN historical_prescriptions r ON h.rx_id=r.rx_id
), records AS (
    SELECT 'association' AS record_type, OBJECT_CONSTRUCT_KEEP_NULL(a.*)::VARCHAR AS payload FROM associations a
    UNION ALL
    SELECT 'shipment', OBJECT_CONSTRUCT_KEEP_NULL(h.*)::VARCHAR FROM history h
)
SELECT CURRENT_TIMESTAMP::VARCHAR AS extracted_at_session_time,
       CURRENT_WAREHOUSE() AS extraction_warehouse, record_type,payload
FROM records

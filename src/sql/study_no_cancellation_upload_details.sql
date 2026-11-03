-- Snapshot statuses for the frozen no-recorded-cancellation-reason RX IDs.
-- Shipment rows are collapsed only after Python validates all variant counts.
WITH requested AS (
    SELECT value::VARCHAR AS rx_id
    FROM TABLE(FLATTEN(INPUT => PARSE_JSON('__RX_IDS_JSON__')))
), prescriptions AS (
    SELECT r.rx_id, p.customer_id, p.first_order_id AS order_id,
           CASE WHEN REGEXP_LIKE(TRIM(p.first_orderitem_id), '^[0-9]+$')
                THEN TRY_TO_NUMBER(p.first_orderitem_id) END AS order_line_id,
           NULLIF(UPPER(TRIM(p.rx_status)), '') AS rx_status,
           COUNT(p.rx_id) OVER (PARTITION BY r.rx_id) AS source_rows
    FROM requested r
    LEFT JOIN EDLDB.BT_HCA_HCDM.RXP_PRESCRIPTIONS p ON r.rx_id = TRIM(p.rx_id)
), normalized_lines AS (
    SELECT l.order_id, l.order_line_id, l.customer_id,
           NULLIF(UPPER(TRIM(l.order_status)), '') AS order_status,
           NULLIF(UPPER(TRIM(l.order_order_line_status)), '') AS line_item_status,
           NULLIF(LOWER(TRIM(l.order_cancel_reason)), '') AS order_cancellation_reason
    FROM EDLDB.BT_HCA_HCDM.ORDER_LINE_COST_MEASURES_RXP l
    JOIN (SELECT DISTINCT order_id, order_line_id FROM prescriptions) p
      ON l.order_id = p.order_id AND l.order_line_id = p.order_line_id
), lines AS (
    SELECT order_id, order_line_id, COUNT(*) AS shipment_rows,
           MIN(customer_id) AS line_customer_id,
           COUNT(DISTINCT customer_id) + IFF(COUNT_IF(customer_id IS NULL)>0,1,0) AS customer_variants,
           MIN(order_status) AS order_status,
           COUNT(DISTINCT order_status) + IFF(COUNT_IF(order_status IS NULL)>0,1,0) AS order_status_variants,
           MIN(line_item_status) AS line_item_status,
           COUNT(DISTINCT line_item_status) + IFF(COUNT_IF(line_item_status IS NULL)>0,1,0) AS line_status_variants,
           MIN(order_cancellation_reason) AS order_cancellation_reason,
           COUNT(DISTINCT order_cancellation_reason) + IFF(COUNT_IF(order_cancellation_reason IS NULL)>0,1,0) AS reason_variants
    FROM normalized_lines
    GROUP BY order_id, order_line_id
)
SELECT p.*, l.shipment_rows, l.line_customer_id, l.customer_variants,
       l.order_status, l.order_status_variants, l.line_item_status,
       l.line_status_variants, l.order_cancellation_reason, l.reason_variants,
       CONVERT_TIMEZONE('UTC', CURRENT_TIMESTAMP())::VARCHAR AS extracted_at_utc
FROM prescriptions p LEFT JOIN lines l
  ON p.order_id = l.order_id AND p.order_line_id = l.order_line_id

-- Shipment evidence is the prescription order line's recorded shipped timestamp.
WITH prescriptions AS (
    SELECT rx_id, rx_creation_datetime,
           COUNT(*) OVER (PARTITION BY rx_id) AS rx_source_rows
    FROM EDLDB.BT_HCA_HCDM.RXP_PRESCRIPTIONS
    WHERE prescription_source = 'CMPU' AND is_vet_diet_flag = TRUE
      AND rx_creation_datetime >= '2026-09-01'::DATE
      AND rx_creation_datetime < '2026-09-16'::DATE
)
SELECT CURRENT_TIMESTAMP::VARCHAR AS extracted_at_session_time,
       p.*, l.order_id, l.order_line_id, l.shipment_key, l.rx_usage_id,
       l.order_status, l.order_status_description,
       l.order_placed_dttm AS order_placed_at_utc,
       l.order_placed_dttm_est AS order_placed_at_eastern,
       l.order_line_shipped_dttm AS shipped_at_utc,
       l.order_line_shipped_dttm_est AS shipped_at_eastern,
       l.order_line_delivery_dttm AS delivered_at_utc,
       l.order_line_shipment_quantity,
       CONVERT_TIMEZONE('UTC', 'America/New_York', l.order_placed_dttm) AS expected_placed_at_eastern,
       CONVERT_TIMEZONE('UTC', 'America/New_York', l.order_line_shipped_dttm) AS expected_shipped_at_eastern
FROM prescriptions p
LEFT JOIN EDLDB.BT_HCA_HCDM.ORDER_LINE_COST_MEASURES_RXP l ON p.rx_id = l.rx_id

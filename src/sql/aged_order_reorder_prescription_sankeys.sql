-- REFNUM 24: current prescription/channel evidence for frozen selected order-line pairs.
WITH requested_keys AS (
    SELECT value[0]::NUMBER(38,0) AS order_id, value[1]::NUMBER(38,0) AS order_line_id
    FROM TABLE(FLATTEN(INPUT => PARSE_JSON('{{ order_line_keys_json }}')))
), line_evidence AS (
    SELECT k.order_id, k.order_line_id,
           NULLIF(TRIM(l.rx_id), '') AS rx_id,
           NULLIF(TRIM(l.rx_usage_id), '') AS rx_usage_id,
           COUNT(l.order_line_id) AS shipment_rows
    FROM requested_keys k
    LEFT JOIN EDLDB.BT_HCA_HCDM.ORDER_LINE_COST_MEASURES_RXP l
      ON k.order_id=l.order_id AND k.order_line_id=l.order_line_id
    GROUP BY k.order_id, k.order_line_id, NULLIF(TRIM(l.rx_id), ''), NULLIF(TRIM(l.rx_usage_id), '')
), registry AS (
    SELECT p.rx_id, p.approval_channel, COUNT(*) OVER (PARTITION BY p.rx_id) AS prescription_rows
    FROM EDLDB.BT_HCA_HCDM.RXP_PRESCRIPTIONS p
    JOIN (SELECT DISTINCT rx_id FROM line_evidence WHERE rx_id IS NOT NULL) r ON p.rx_id=r.rx_id
)
SELECT CURRENT_TIMESTAMP::VARCHAR AS extracted_at_session_time,
       CURRENT_WAREHOUSE() AS extraction_warehouse,
       l.*, p.rx_id AS matched_rx_id, p.approval_channel,
       COALESCE(p.prescription_rows,0) AS prescription_rows
FROM line_evidence l LEFT JOIN registry p ON l.rx_id=p.rx_id

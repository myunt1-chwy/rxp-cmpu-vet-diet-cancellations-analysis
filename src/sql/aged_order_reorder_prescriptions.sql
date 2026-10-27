-- Enrich the frozen REFNUM 22 order/line keys without changing its reorder cohort.
WITH requested_keys AS (
    SELECT value[0]::NUMBER(38,0) AS order_id, value[1]::NUMBER(38,0) AS order_line_id
    FROM TABLE(FLATTEN(INPUT => PARSE_JSON('{{ order_line_keys_json }}')))
)
SELECT CURRENT_TIMESTAMP::VARCHAR AS extracted_at_session_time,
       CURRENT_WAREHOUSE() AS extraction_warehouse,
       k.order_id, k.order_line_id,
       NULLIF(TRIM(l.rx_id), '') AS rx_id,
       NULLIF(TRIM(l.rx_usage_id), '') AS rx_usage_id,
       COUNT(l.order_line_id) AS shipment_rows
FROM requested_keys k
LEFT JOIN EDLDB.BT_HCA_HCDM.ORDER_LINE_COST_MEASURES_RXP l
  ON k.order_id = l.order_id AND k.order_line_id = l.order_line_id
GROUP BY k.order_id, k.order_line_id, NULLIF(TRIM(l.rx_id), ''), NULLIF(TRIM(l.rx_usage_id), '')

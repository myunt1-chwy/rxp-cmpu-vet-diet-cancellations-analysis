-- REFNUM 24 follow-up: entity uploads and approval/denial timestamps for different RX_IDs.
-- Upload matching/cutoff is identical to the established REFNUM 22 upload analysis.
WITH upload_evidence AS (
{{ upload_sql }}
), requested_lines AS (
    SELECT value[0]::VARCHAR AS rx_id, value[1]::NUMBER(38,0) AS customer_id,
           value[2]::NUMBER(38,0) AS order_id, value[3]::NUMBER(38,0) AS order_line_id
    FROM TABLE(FLATTEN(INPUT => PARSE_JSON('{{ requested_lines_json }}')))
), line_evidence AS (
    SELECT k.order_id, k.order_line_id, COUNT(l.order_line_id) AS line_source_rows,
           COUNT(DISTINCT NULLIF(TRIM(l.rx_id),'')) AS line_rx_variants,
           MIN(NULLIF(TRIM(l.rx_id),'')) AS line_rx_id,
           COUNT_IF(l.order_line_id IS NOT NULL AND NULLIF(TRIM(l.rx_id),'') IS NULL) AS missing_line_rx_rows,
           MIN(l.min_approved_denied_datetime) AS min_approved_denied_datetime,
           COUNT(DISTINCT l.min_approved_denied_datetime) AS approval_variants,
           COUNT(l.min_approved_denied_datetime) AS populated_approval_rows
    FROM (SELECT DISTINCT order_id, order_line_id FROM requested_lines) k
    LEFT JOIN EDLDB.BT_HCA_HCDM.ORDER_LINE_COST_MEASURES_RXP l
      ON k.order_id=l.order_id AND k.order_line_id=l.order_line_id
    GROUP BY k.order_id, k.order_line_id
)
SELECT u.*, k.order_id, k.order_line_id,
       l.line_source_rows, l.line_rx_variants, l.line_rx_id, l.missing_line_rx_rows,
       TO_CHAR(l.min_approved_denied_datetime,'YYYY-MM-DD HH24:MI:SS.FF9') AS min_approved_denied_datetime,
       l.approval_variants, l.populated_approval_rows
FROM upload_evidence u
JOIN requested_lines k ON u.rx_id=k.rx_id AND u.customer_id=k.customer_id
JOIN line_evidence l ON k.order_id=l.order_id AND k.order_line_id=l.order_line_id

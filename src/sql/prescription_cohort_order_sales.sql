-- Financial enrichment of the frozen Aug 15-Oct 14 prescription cohort's physical lines.
-- Keys come from the fingerprint-verified all-orders comparison; no new cohort filter.
WITH requested AS (
    SELECT value[0]::NUMBER(38,0) AS order_id,
           value[1]::NUMBER(38,0) AS order_line_id
    FROM TABLE(FLATTEN(INPUT => PARSE_JSON('{{ keys_json }}')))
)
SELECT l.order_id::VARCHAR AS order_id, l.order_line_id::VARCHAR AS order_line_id,
       l.shipment_key::VARCHAR AS shipment_key, l.customer_id::VARCHAR AS customer_id,
       TO_CHAR(l.order_placed_dttm,'YYYY-MM-DD HH24:MI:SS.FF9') AS order_placed_utc,
       l.order_cancel_reason,
       TO_CHAR(l.order_cancel_dttm,'YYYY-MM-DD HH24:MI:SS.FF9') AS order_cancel_utc,
       l.order_line_net_sales::VARCHAR AS order_line_net_sales,
       l.site_key::VARCHAR AS site_key,l.order_line_site_key::VARCHAR AS order_line_site_key,
       l.legal_company_description,l.order_line_transaction_type
FROM EDLDB.BT_HCA_HCDM.ORDER_LINE_COST_MEASURES_RXP l
JOIN requested k ON l.order_id=k.order_id AND l.order_line_id=k.order_line_id

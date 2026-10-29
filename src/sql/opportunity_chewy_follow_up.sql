-- Date-driven CMPU vet-diet CUSTOMER_UPLOAD aged cancellations; UTC follow-up.
-- All-Chewy follow-up uses EDLDB.ECOM.ORDER_LINE and NET_SALES; customer matching only.
WITH registry AS (
 SELECT rx_id,MIN(customer_id) AS customer_id,
 MIN(is_vet_diet_flag) AS is_vet_diet_flag,MIN(approval_channel) AS approval_channel,
 MIN(prescription_source) AS prescription_source,
 GREATEST(COUNT(DISTINCT customer_id)+IFF(COUNT_IF(customer_id IS NULL)>0,1,0),
 COUNT(DISTINCT is_vet_diet_flag)+IFF(COUNT_IF(is_vet_diet_flag IS NULL)>0,1,0),
 COUNT(DISTINCT approval_channel)+IFF(COUNT_IF(approval_channel IS NULL)>0,1,0),
 COUNT(DISTINCT prescription_source)+IFF(COUNT_IF(prescription_source IS NULL)>0,1,0)) AS registry_variants
 FROM EDLDB.BT_HCA_HCDM.RXP_PRESCRIPTIONS GROUP BY rx_id
), aged_keys AS (
 SELECT l.order_id,l.order_line_id,MAX(p.registry_variants) AS registry_variants
 FROM EDLDB.BT_HCA_HCDM.ORDER_LINE_COST_MEASURES_RXP l JOIN registry p
 ON NULLIF(TRIM(l.rx_id),'')=p.rx_id AND l.customer_id=p.customer_id
 WHERE l.is_vet_diet_flag=TRUE AND p.is_vet_diet_flag=TRUE
 AND p.approval_channel='CUSTOMER_UPLOAD' AND p.prescription_source='CMPU'
 AND LOWER(TRIM(l.order_cancel_reason))='aged order'
 AND l.order_cancel_dttm>='{{ start_date }}'::TIMESTAMP_NTZ
 AND l.order_cancel_dttm<'{{ end_date }}'::TIMESTAMP_NTZ
 GROUP BY l.order_id,l.order_line_id
), originals AS (
 SELECT l.order_id AS original_order_id,l.order_line_id AS original_line_id,
 MAX(k.registry_variants) AS registry_variants,
 MIN(l.customer_id) AS original_customer_id,MIN(l.pet_id) AS original_pet_id,
 MIN(l.product_part_number) AS original_product_part_number,
 MIN(l.order_cancel_dttm) AS original_cancel_utc,
 MIN(LOWER(TRIM(l.order_cancel_reason))) AS original_reason,
 COUNT(DISTINCT l.customer_id)+IFF(COUNT_IF(l.customer_id IS NULL)>0,1,0) AS customer_variants,
 COUNT(DISTINCT l.pet_id)+IFF(COUNT_IF(l.pet_id IS NULL)>0,1,0) AS pet_variants,
 COUNT(DISTINCT l.product_part_number)+IFF(COUNT_IF(l.product_part_number IS NULL)>0,1,0) AS part_variants,
 COUNT(DISTINCT l.order_cancel_dttm)+IFF(COUNT_IF(l.order_cancel_dttm IS NULL)>0,1,0) AS cancel_variants,
 COUNT(DISTINCT LOWER(TRIM(l.order_cancel_reason)))+IFF(COUNT_IF(l.order_cancel_reason IS NULL)>0,1,0) AS reason_variants
 FROM EDLDB.BT_HCA_HCDM.ORDER_LINE_COST_MEASURES_RXP l
 JOIN aged_keys k ON l.order_id=k.order_id AND l.order_line_id=k.order_line_id
 GROUP BY l.order_id,l.order_line_id
), candidate_keys AS (
 SELECT DISTINCT l.order_id,l.order_line_id
 FROM EDLDB.ECOM.ORDER_LINE l JOIN originals a ON l.customer_id=a.original_customer_id
 AND l.order_id<>a.original_order_id
 AND l.order_placed_dttm>a.original_cancel_utc
 AND l.order_placed_dttm<=DATEADD(day,{{ followup_days }},a.original_cancel_utc)
 AND l.order_placed_dttm<='{{ as_of_date }}'::TIMESTAMP_NTZ
), candidate_lines AS (
 -- All lines on each candidate order are needed for whole-order exclusion.
 SELECT l.* FROM EDLDB.ECOM.ORDER_LINE l
 JOIN (SELECT DISTINCT order_id FROM candidate_keys) k ON l.order_id=k.order_id
), order_cancellations AS (
 SELECT order_id,MAX(IFF(order_order_line_status='X' OR order_status='X'
 OR NULLIF(TRIM(order_cancel_reason),'') IS NOT NULL OR order_cancel_dttm IS NOT NULL,1,0)) AS order_has_cancellation,
 MAX(IFF(order_order_line_status IS NULL,1,0)) AS order_has_unknown_status
 FROM candidate_lines GROUP BY order_id
), reorders AS (
 -- ECOM.ORDER_LINE is a physical-line view; NET_SALES is the full line amount.
 -- Exact source duplicates collapse. Conflicting line values fail validation.
 SELECT l.order_id AS reorder_order_id,l.order_line_id AS reorder_line_id,
 MIN(l.customer_id) AS reorder_customer_id,
 NULL::NUMBER(38,0) AS reorder_pet_id,NULL::VARCHAR AS reorder_product_part_number,
 MIN(l.order_placed_dttm) AS reorder_placed_utc,
 MIN(l.order_line_shipped_dttm) AS reorder_shipped_utc,
 MIN(l.net_sales)::VARCHAR AS reorder_known_net_sales,
 IFF(COUNT_IF(l.net_sales IS NULL)>0,1,0) AS missing_sales_records,
 COUNT(*) AS ecom_source_rows,
 MIN(l.order_line_currency) AS ecom_currency,
 GREATEST(
 COUNT(DISTINCT l.customer_id)+IFF(COUNT_IF(l.customer_id IS NULL)>0,1,0),
 COUNT(DISTINCT l.order_placed_dttm)+IFF(COUNT_IF(l.order_placed_dttm IS NULL)>0,1,0),
 COUNT(DISTINCT l.net_sales)+IFF(COUNT_IF(l.net_sales IS NULL)>0,1,0),
 COUNT(DISTINCT l.order_line_currency)+IFF(COUNT_IF(l.order_line_currency IS NULL)>0,1,0)) AS source_variants,
 MAX(o.order_has_cancellation) AS reorder_order_has_cancellation,
 MAX(o.order_has_unknown_status) AS reorder_order_has_unknown_status
 FROM candidate_lines l JOIN candidate_keys k ON l.order_id=k.order_id AND l.order_line_id=k.order_line_id
 JOIN order_cancellations o ON l.order_id=o.order_id
 GROUP BY l.order_id,l.order_line_id
)
SELECT a.* REPLACE(TO_CHAR(original_cancel_utc,'YYYY-MM-DD HH24:MI:SS.FF9') AS original_cancel_utc),
 r.* REPLACE(TO_CHAR(reorder_placed_utc,'YYYY-MM-DD HH24:MI:SS.FF9') AS reorder_placed_utc,
 TO_CHAR(reorder_shipped_utc,'YYYY-MM-DD HH24:MI:SS.FF9') AS reorder_shipped_utc),
 (SELECT COUNT_IF(order_line_id IS NULL) FROM candidate_keys) AS candidate_missing_line_keys
FROM originals a LEFT JOIN reorders r ON r.reorder_customer_id=a.original_customer_id
 AND r.reorder_order_id<>a.original_order_id AND r.reorder_placed_utc>a.original_cancel_utc
 AND r.reorder_placed_utc<=DATEADD(day,{{ followup_days }},a.original_cancel_utc)

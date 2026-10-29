-- Date-driven CMPU vet-diet CUSTOMER_UPLOAD aged cancellations; UTC follow-up.
-- Study-specific matching uses CUSTOMER_ID, PRODUCT_PART_NUMBER, PET_ID and vet-diet flags.
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
 FROM EDLDB.BT_HCA_HCDM.ORDER_LINE_COST_MEASURES_RXP l JOIN originals a
 ON l.customer_id=a.original_customer_id
 {% if all_studies %}
 AND (l.is_vet_diet_flag=TRUE OR (l.pet_id=a.original_pet_id
      AND l.product_part_number=a.original_product_part_number))
 {% else %}
 AND l.pet_id=a.original_pet_id AND l.product_part_number=a.original_product_part_number
 {% endif %}
 AND l.order_id<>a.original_order_id
 AND l.order_placed_dttm>a.original_cancel_utc
 AND l.order_placed_dttm<=DATEADD(day,{{ followup_days }},a.original_cancel_utc)
 AND l.order_placed_dttm<='{{ as_of_date }}'::TIMESTAMP_NTZ
), order_cancellations AS (
 -- Inspect every line of candidate orders, including other products.
 SELECT l.order_id,MAX(IFF(l.order_order_line_status='X'
 OR NULLIF(TRIM(l.order_cancel_reason),'') IS NOT NULL
 OR l.order_cancel_dttm IS NOT NULL,1,0)) AS order_has_cancellation,
 MAX(IFF(l.order_order_line_status IS NULL,1,0)) AS order_has_unknown_status
 FROM EDLDB.BT_HCA_HCDM.ORDER_LINE_COST_MEASURES_RXP l
 JOIN (SELECT DISTINCT order_id FROM candidate_keys) k ON l.order_id=k.order_id
 GROUP BY l.order_id
), financial AS (
 SELECT l.order_id,l.order_line_id,l.shipment_key,
 MIN(l.customer_id) AS customer_id,MIN(l.pet_id) AS pet_id,
 MIN(l.product_part_number) AS product_part_number,
 MIN(l.is_vet_diet_flag) AS is_vet_diet_flag,
 MIN(l.order_placed_dttm) AS placed_at_utc,
 MIN(l.order_line_shipped_dttm) AS shipped_at_utc,
 MIN(l.order_line_net_sales) AS net_sales,
 COUNT(DISTINCT l.is_vet_diet_flag)+IFF(COUNT_IF(l.is_vet_diet_flag IS NULL)>0,1,0) AS vet_diet_variants,
 COUNT(DISTINCT l.order_line_net_sales)+IFF(COUNT_IF(l.order_line_net_sales IS NULL)>0,1,0) AS sales_variants,
 COUNT(DISTINCT l.customer_id)+IFF(COUNT_IF(l.customer_id IS NULL)>0,1,0) AS customer_variants,
 COUNT(DISTINCT l.pet_id)+IFF(COUNT_IF(l.pet_id IS NULL)>0,1,0) AS pet_variants,
 COUNT(DISTINCT l.product_part_number)+IFF(COUNT_IF(l.product_part_number IS NULL)>0,1,0) AS part_variants,
 COUNT(DISTINCT l.order_placed_dttm)+IFF(COUNT_IF(l.order_placed_dttm IS NULL)>0,1,0) AS placement_variants
 FROM EDLDB.BT_HCA_HCDM.ORDER_LINE_COST_MEASURES_RXP l JOIN candidate_keys k
 ON l.order_id=k.order_id AND l.order_line_id=k.order_line_id
 GROUP BY l.order_id,l.order_line_id,l.shipment_key
), reorders AS (
 SELECT f.order_id AS reorder_order_id,f.order_line_id AS reorder_line_id,
 MIN(f.customer_id) AS reorder_customer_id,MIN(f.pet_id) AS reorder_pet_id,
 MIN(f.product_part_number) AS reorder_product_part_number,
 MIN(f.is_vet_diet_flag) AS reorder_is_vet_diet,
 MIN(f.placed_at_utc) AS reorder_placed_utc,MIN(f.shipped_at_utc) AS reorder_shipped_utc,
 SUM(f.net_sales)::VARCHAR AS reorder_known_net_sales,
 COUNT_IF(f.net_sales IS NULL) AS missing_sales_records,
 GREATEST(MAX(f.vet_diet_variants),COUNT(DISTINCT f.is_vet_diet_flag)+IFF(COUNT_IF(f.is_vet_diet_flag IS NULL)>0,1,0),MAX(f.sales_variants),MAX(f.customer_variants),MAX(f.pet_variants),MAX(f.part_variants),
 MAX(f.placement_variants),COUNT(DISTINCT f.customer_id)+IFF(COUNT_IF(f.customer_id IS NULL)>0,1,0),COUNT(DISTINCT f.pet_id)+IFF(COUNT_IF(f.pet_id IS NULL)>0,1,0),
 COUNT(DISTINCT f.product_part_number)+IFF(COUNT_IF(f.product_part_number IS NULL)>0,1,0),COUNT(DISTINCT f.placed_at_utc)+IFF(COUNT_IF(f.placed_at_utc IS NULL)>0,1,0)) AS source_variants,
 MAX(o.order_has_cancellation) AS reorder_order_has_cancellation,
 MAX(o.order_has_unknown_status) AS reorder_order_has_unknown_status
 FROM financial f JOIN order_cancellations o ON f.order_id=o.order_id GROUP BY f.order_id,f.order_line_id
)
SELECT a.* REPLACE(TO_CHAR(original_cancel_utc,'YYYY-MM-DD HH24:MI:SS.FF9') AS original_cancel_utc),
 r.* REPLACE(TO_CHAR(reorder_placed_utc,'YYYY-MM-DD HH24:MI:SS.FF9') AS reorder_placed_utc,
 TO_CHAR(reorder_shipped_utc,'YYYY-MM-DD HH24:MI:SS.FF9') AS reorder_shipped_utc)
FROM originals a LEFT JOIN reorders r ON r.reorder_customer_id=a.original_customer_id
 {% if all_studies %}
 AND (r.reorder_is_vet_diet=TRUE OR (r.reorder_pet_id=a.original_pet_id
      AND r.reorder_product_part_number=a.original_product_part_number))
 {% else %}
 AND r.reorder_pet_id=a.original_pet_id AND r.reorder_product_part_number=a.original_product_part_number
 {% endif %}
 AND r.reorder_order_id<>a.original_order_id AND r.reorder_placed_utc>a.original_cancel_utc
 AND r.reorder_placed_utc<=DATEADD(day,{{ followup_days }},a.original_cancel_utc)

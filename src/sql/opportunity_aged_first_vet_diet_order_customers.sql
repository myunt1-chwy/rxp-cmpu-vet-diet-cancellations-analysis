-- CMPU vet-diet CUSTOMER_UPLOAD aged cancellations; exact first observed vet-diet order IDs.
-- Vet-diet membership from RxP lines; chronology from ECOM.ORDERS, all channels/statuses/dates.
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
), aged_lines AS (
 SELECT l.order_id,l.order_line_id,l.customer_id,l.order_placed_dttm AS placed_at_utc,
 l.order_cancel_dttm AS cancelled_at_utc,k.registry_variants
 FROM EDLDB.BT_HCA_HCDM.ORDER_LINE_COST_MEASURES_RXP l
 JOIN aged_keys k ON l.order_id=k.order_id AND l.order_line_id=k.order_line_id
), cohort_customers AS (
 SELECT DISTINCT customer_id FROM aged_lines
), vet_diet_order_keys AS (
 -- Full vet-diet history; no CMPU, channel, RX-ID or date restriction here.
 SELECT DISTINCT l.customer_id,l.order_id
 FROM EDLDB.BT_HCA_HCDM.ORDER_LINE_COST_MEASURES_RXP l
 JOIN cohort_customers c ON l.customer_id=c.customer_id
 WHERE l.is_vet_diet_flag=TRUE
), history_keys AS (
 SELECT DISTINCT order_id FROM vet_diet_order_keys
), history AS (
 SELECT o.order_id,MIN(o.customer_id) AS customer_id,
 MIN(o.order_placed_dttm) AS placed_at_utc,MIN(o.order_first_order_placed_flag) AS first_placed_flag,
 COUNT(*) AS source_rows,
 GREATEST(COUNT(DISTINCT o.customer_id)+IFF(COUNT_IF(o.customer_id IS NULL)>0,1,0),
 COUNT(DISTINCT o.order_placed_dttm)+IFF(COUNT_IF(o.order_placed_dttm IS NULL)>0,1,0),
 COUNT(DISTINCT o.order_first_order_placed_flag)+IFF(COUNT_IF(o.order_first_order_placed_flag IS NULL)>0,1,0)) AS source_variants
 FROM EDLDB.ECOM.ORDERS o JOIN history_keys k ON o.order_id=k.order_id GROUP BY o.order_id
), vet_history_audit AS (
 SELECT v.customer_id,COUNT(DISTINCT IFF(h.order_id IS NULL,v.order_id,NULL)) AS vet_orders_missing_ecom_header
 FROM vet_diet_order_keys v LEFT JOIN history h ON v.order_id=h.order_id AND v.customer_id=h.customer_id
 GROUP BY v.customer_id
), ranked AS (
 SELECT *,MIN(placed_at_utc) OVER (PARTITION BY customer_id) AS earliest_placed_at_utc,
 ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY placed_at_utc NULLS LAST,order_id) AS first_rank
 FROM history
), first_orders AS (
 SELECT customer_id,COUNT(*) AS history_orders,
 COUNT_IF(placed_at_utc IS NULL) AS history_orders_missing_placement,
 MAX(source_variants) AS history_source_variants,
 SUM(source_rows-1) AS history_identical_duplicate_rows,
 MIN(earliest_placed_at_utc) AS first_placed_at_utc,
 COUNT_IF(placed_at_utc=earliest_placed_at_utc) AS earliest_timestamp_ties,
 MAX(IFF(first_rank=1,order_id,NULL)) AS first_order_id,
 COUNT_IF(first_placed_flag=TRUE) AS flagged_first_orders,
 MIN(IFF(first_placed_flag=TRUE,order_id,NULL)) AS flagged_first_order_id
 FROM ranked GROUP BY customer_id
)
SELECT a.*,e.customer_id AS ecom_aged_customer_id,e.placed_at_utc AS ecom_aged_placed_at_utc,
 e.first_placed_flag AS aged_order_first_placed_flag,e.source_variants AS aged_order_source_variants,
 f.history_orders,f.history_orders_missing_placement,f.history_source_variants,f.history_identical_duplicate_rows,
 v.vet_orders_missing_ecom_header,f.first_order_id,f.first_placed_at_utc,f.earliest_timestamp_ties,f.flagged_first_orders,f.flagged_first_order_id
FROM aged_lines a LEFT JOIN history e ON a.order_id=e.order_id
LEFT JOIN first_orders f ON a.customer_id=f.customer_id
LEFT JOIN vet_history_audit v ON a.customer_id=v.customer_id

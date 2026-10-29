-- CMPU vet-diet CUSTOMER_UPLOAD aged cancellations; new-to-Chewy by same UTC day.
-- Compare placed_at_utc::DATE to CDM.CUSTOMER.ORDER_FIRST_PLACED_DTTM::DATE.
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
), customers AS (
 SELECT c.customer_id,MIN(c.order_first_placed_dttm) AS first_order_placed_utc,
 COUNT(*) AS customer_source_rows,
 COUNT(DISTINCT c.order_first_placed_dttm)+IFF(COUNT_IF(c.order_first_placed_dttm IS NULL)>0,1,0) AS first_order_variants
 FROM EDLDB.CDM.CUSTOMER c
 JOIN (SELECT DISTINCT customer_id FROM aged_lines) a ON c.customer_id=a.customer_id
 GROUP BY c.customer_id
)
SELECT a.*,c.first_order_placed_utc,c.customer_source_rows,c.first_order_variants
FROM aged_lines a LEFT JOIN customers c ON a.customer_id=c.customer_id

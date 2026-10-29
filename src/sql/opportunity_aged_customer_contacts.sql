-- Customer-initiated contact counts around CMPU vet-diet CUSTOMER_UPLOAD aged cancellation.
-- Keep every aged order and all direction/handled states for auditing; UTC 24-hour bins [-13,4).
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
), aged_orders AS (
 SELECT order_id,MIN(customer_id) AS customer_id,MIN(cancelled_at_utc) AS cancelled_at_utc,
 MAX(registry_variants) AS registry_variants,COUNT(DISTINCT order_line_id) AS qualifying_lines,
 COUNT(DISTINCT customer_id)+IFF(COUNT_IF(customer_id IS NULL)>0,1,0) AS customer_variants,
 COUNT(DISTINCT cancelled_at_utc)+IFF(COUNT_IF(cancelled_at_utc IS NULL)>0,1,0) AS cancellation_variants
 FROM aged_lines GROUP BY order_id
)
SELECT a.order_id,a.customer_id,
 TO_CHAR(a.cancelled_at_utc,'YYYY-MM-DD HH24:MI:SS.FF9') AS cancelled_at_utc,
 a.registry_variants,a.qualifying_lines,a.customer_variants,a.cancellation_variants,
 c.order_id AS contact_order_id,c.customer_id AS contact_customer_id,
 c.leg_id,c.session_id,c.session_channel,c.session_ingress_point,
 c.session_initial_direction,c.handled_flag,
 TO_CHAR(c.session_start_dttm,'YYYY-MM-DD HH24:MI:SS.FF9') AS contact_at_utc
FROM aged_orders a LEFT JOIN EDLDB.BT_CUSTOMER_CARE.FCT_CONTACTS_BRD c
 ON a.order_id=c.order_id
 AND ((c.session_start_dttm>=DATEADD(day,{{ min_day }},a.cancelled_at_utc)
 AND c.session_start_dttm<DATEADD(day,{{ end_day }},a.cancelled_at_utc)) OR c.session_start_dttm IS NULL)

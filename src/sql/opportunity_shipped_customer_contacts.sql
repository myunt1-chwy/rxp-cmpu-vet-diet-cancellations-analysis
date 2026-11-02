-- CMPU vet-diet CUSTOMER_UPLOAD orders with SQL NULL cancellation reason and
-- qualifying shipment activity in [start_date,end_date), UTC. Contact day 0 is
-- ORDER_PLACED_DTTM; retain days -2..+11 only through the last qualifying shipment.
WITH registry AS (
 SELECT rx_id,MIN(customer_id) AS customer_id,
 MIN(is_vet_diet_flag) AS is_vet_diet_flag,MIN(approval_channel) AS approval_channel,
 MIN(prescription_source) AS prescription_source,
 GREATEST(COUNT(DISTINCT customer_id)+IFF(COUNT_IF(customer_id IS NULL)>0,1,0),
 COUNT(DISTINCT is_vet_diet_flag)+IFF(COUNT_IF(is_vet_diet_flag IS NULL)>0,1,0),
 COUNT(DISTINCT approval_channel)+IFF(COUNT_IF(approval_channel IS NULL)>0,1,0),
 COUNT(DISTINCT prescription_source)+IFF(COUNT_IF(prescription_source IS NULL)>0,1,0)) AS registry_variants
 FROM EDLDB.BT_HCA_HCDM.RXP_PRESCRIPTIONS GROUP BY rx_id
), candidate_orders AS (
 SELECT DISTINCT l.order_id
 FROM EDLDB.BT_HCA_HCDM.ORDER_LINE_COST_MEASURES_RXP l JOIN registry p
 ON NULLIF(TRIM(l.rx_id),'')=p.rx_id AND l.customer_id=p.customer_id
 WHERE l.is_vet_diet_flag=TRUE AND p.is_vet_diet_flag=TRUE
 AND p.approval_channel='CUSTOMER_UPLOAD' AND p.prescription_source='CMPU'
 AND l.order_cancel_reason IS NULL
 AND l.order_line_shipped_dttm>='{{ start_date }}'::TIMESTAMP_NTZ
 AND l.order_line_shipped_dttm<'{{ end_date }}'::TIMESTAMP_NTZ
), qualifying_lines AS (
 -- Retrieve all qualifying shipment rows on candidate orders, including those
 -- outside the reporting window, so split shipments have a complete endpoint.
 SELECT l.*,p.registry_variants
 FROM EDLDB.BT_HCA_HCDM.ORDER_LINE_COST_MEASURES_RXP l JOIN candidate_orders k
 ON l.order_id=k.order_id JOIN registry p
 ON NULLIF(TRIM(l.rx_id),'')=p.rx_id AND l.customer_id=p.customer_id
 WHERE l.is_vet_diet_flag=TRUE AND p.is_vet_diet_flag=TRUE
 AND p.approval_channel='CUSTOMER_UPLOAD' AND p.prescription_source='CMPU'
), shipped_orders AS (
 SELECT order_id,MIN(customer_id) AS customer_id,
 MIN(order_placed_dttm) AS placed_at_utc,
 MAX(order_line_shipped_dttm) AS shipped_at_utc,
 MIN(order_line_shipped_dttm) AS first_shipped_at_utc,
 MAX(registry_variants) AS registry_variants,
 COUNT(DISTINCT order_line_id) AS qualifying_lines,
 COUNT(*) AS shipment_source_rows,
 COUNT(DISTINCT customer_id)+IFF(COUNT_IF(customer_id IS NULL)>0,1,0) AS customer_variants,
 COUNT(DISTINCT order_placed_dttm)+IFF(COUNT_IF(order_placed_dttm IS NULL)>0,1,0) AS placement_variants,
 COUNT_IF(order_cancel_reason IS NOT NULL) AS nonnull_reason_rows,
 COUNT_IF(order_cancel_dttm IS NOT NULL OR order_order_line_status='X') AS cancellation_evidence_rows,
 COUNT_IF(order_line_shipped_dttm IS NULL) AS missing_shipment_time_rows
 FROM qualifying_lines GROUP BY order_id
)
SELECT s.* REPLACE(
 TO_CHAR(placed_at_utc,'YYYY-MM-DD HH24:MI:SS.FF9') AS placed_at_utc,
 TO_CHAR(shipped_at_utc,'YYYY-MM-DD HH24:MI:SS.FF9') AS shipped_at_utc,
 TO_CHAR(first_shipped_at_utc,'YYYY-MM-DD HH24:MI:SS.FF9') AS first_shipped_at_utc),
 c.order_id AS contact_order_id,c.customer_id AS contact_customer_id,
 c.leg_id,c.session_id,c.session_channel,c.session_ingress_point,
 c.session_initial_direction,c.handled_flag,
 TO_CHAR(c.session_start_dttm,'YYYY-MM-DD HH24:MI:SS.FF9') AS contact_at_utc
FROM shipped_orders s LEFT JOIN EDLDB.BT_CUSTOMER_CARE.FCT_CONTACTS_BRD c
 ON s.order_id=c.order_id
 AND ((c.session_start_dttm>=DATEADD(day,{{ min_day }},s.placed_at_utc)
 AND c.session_start_dttm<DATEADD(day,{{ end_day }},s.placed_at_utc)
 AND c.session_start_dttm<=s.shipped_at_utc) OR c.session_start_dttm IS NULL)

-- Opportunity baseline: {{ date_basis }} reporting window [start_date, end_date), UTC.
-- Candidate vet-diet lines include every order, not only FIRST_ORDER_ID.
-- Fetch all shipment rows for candidate physical lines before validation.
WITH window_keys AS (
    SELECT DISTINCT order_id, order_line_id
    FROM EDLDB.BT_HCA_HCDM.ORDER_LINE_COST_MEASURES_RXP
    WHERE is_vet_diet_flag = TRUE
{% if date_basis == 'shipped-or-cancelled' %}
      AND ((order_line_shipped_dttm >= '{{ start_date }}'::TIMESTAMP_NTZ
            AND order_line_shipped_dttm < '{{ end_date }}'::TIMESTAMP_NTZ)
        OR (order_cancel_dttm >= '{{ start_date }}'::TIMESTAMP_NTZ
            AND order_cancel_dttm < '{{ end_date }}'::TIMESTAMP_NTZ))
{% else %}
      AND order_placed_dttm >= '{{ start_date }}'::TIMESTAMP_NTZ
      AND order_placed_dttm < '{{ end_date }}'::TIMESTAMP_NTZ
{% endif %}
), source_lines AS (
    SELECT l.*
    FROM EDLDB.BT_HCA_HCDM.ORDER_LINE_COST_MEASURES_RXP l
    JOIN window_keys k ON l.order_id IS NOT DISTINCT FROM k.order_id
                      AND l.order_line_id IS NOT DISTINCT FROM k.order_line_id
), registry AS (
    SELECT p.rx_id, MIN(p.customer_id) AS rx_customer_id,
           MIN(p.is_vet_diet_flag) AS rx_is_vet_diet_flag,
           MIN(p.approval_channel) AS rx_approval_channel,
           MIN(p.prescription_source) AS prescription_source,
           COUNT(*) AS rx_source_rows,
           COUNT(DISTINCT p.customer_id)
             + IFF(COUNT_IF(p.customer_id IS NULL)>0,1,0) AS rx_customer_variants,
           COUNT(DISTINCT p.is_vet_diet_flag)
             + IFF(COUNT_IF(p.is_vet_diet_flag IS NULL)>0,1,0) AS rx_vet_diet_variants,
           COUNT(DISTINCT p.approval_channel)
             + IFF(COUNT_IF(p.approval_channel IS NULL)>0,1,0) AS rx_channel_variants,
           COUNT(DISTINCT p.prescription_source)
             + IFF(COUNT_IF(p.prescription_source IS NULL)>0,1,0) AS rx_source_variants
    FROM EDLDB.BT_HCA_HCDM.RXP_PRESCRIPTIONS p
    JOIN (SELECT DISTINCT NULLIF(TRIM(rx_id),'') AS rx_id FROM source_lines) k
      ON p.rx_id = k.rx_id
    GROUP BY p.rx_id
)
SELECT CURRENT_TIMESTAMP::VARCHAR AS extracted_at_session_time,
       CURRENT_WAREHOUSE() AS extraction_warehouse,
       l.order_id::VARCHAR AS order_id, l.order_line_id::VARCHAR AS order_line_id,
       l.shipment_key::VARCHAR AS shipment_key, l.customer_id::VARCHAR AS customer_id,
       l.rx_id AS raw_rx_id, NULLIF(TRIM(l.rx_id),'') AS rx_id,
       TO_CHAR(l.order_placed_dttm,'YYYY-MM-DD HH24:MI:SS.FF9') AS order_placed_utc,
{% if date_basis == 'shipped-or-cancelled' %}
       TO_CHAR(l.order_line_shipped_dttm,'YYYY-MM-DD HH24:MI:SS.FF9') AS shipped_at_utc,
       TO_CHAR(l.order_cancel_dttm,'YYYY-MM-DD HH24:MI:SS.FF9') AS cancelled_at_utc,
{% endif %}
       l.is_vet_diet_flag, l.approval_channel AS line_approval_channel,
       l.order_order_line_status AS line_status, l.order_cancel_reason,
       -- Strings preserve NUMBER(28,5) exactly through either extraction engine.
       l.order_line_net_sales::VARCHAR AS order_line_net_sales,
       l.site_key::VARCHAR AS site_key, l.order_line_site_key::VARCHAR AS order_line_site_key,
       l.legal_company_description, l.order_line_transaction_type,
       p.rx_customer_id::VARCHAR AS rx_customer_id, p.rx_is_vet_diet_flag,
       p.rx_approval_channel, p.prescription_source,
       COALESCE(p.rx_source_rows,0) AS rx_source_rows,
       p.rx_customer_variants, p.rx_vet_diet_variants, p.rx_channel_variants, p.rx_source_variants
FROM source_lines l
LEFT JOIN registry p ON NULLIF(TRIM(l.rx_id),'') = p.rx_id

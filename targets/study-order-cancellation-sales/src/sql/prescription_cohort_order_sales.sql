{% set start_date = start_date | default('2026-08-15') %}
{% set end_date = end_date | default('2026-10-15') %}
{% set as_of_date = as_of_date | default('2026-10-27') %}
-- Database-derived cohort; only scalar dates/timezone are inputs.
-- Current source state can differ from retained historical snapshots.
WITH cohort_prescriptions AS (
    SELECT
        rx_id,
        customer_id
    FROM edldb.bt_hca_hcdm.rxp_prescriptions
    WHERE
        prescription_source = 'CMPU' AND is_vet_diet_flag = TRUE
        AND approval_channel = 'CUSTOMER_UPLOAD'
        AND rx_creation_datetime >= '{{ start_date }}'::TIMESTAMP_NTZ
        AND rx_creation_datetime < '{{ end_date }}'::TIMESTAMP_NTZ
),

requested AS (
    SELECT DISTINCT
        l.order_id,
        l.order_line_id
    FROM edldb.bt_hca_hcdm.order_line_cost_measures_rxp AS l
    INNER JOIN
        cohort_prescriptions AS p
        ON TRIM(l.rx_id) = p.rx_id AND l.customer_id = p.customer_id
    WHERE l.is_vet_diet_flag = TRUE
)

SELECT
    l.order_id::VARCHAR AS order_id,
    l.order_line_id::VARCHAR AS order_line_id,
    l.shipment_key::VARCHAR AS shipment_key,
    l.customer_id::VARCHAR AS customer_id,
    l.order_cancel_reason,
    l.order_line_net_sales::VARCHAR AS order_line_net_sales,
    l.site_key::VARCHAR AS site_key,
    l.order_line_site_key::VARCHAR AS order_line_site_key,
    l.legal_company_description,
    l.order_line_transaction_type,
    TO_CHAR(l.order_placed_dttm, 'YYYY-MM-DD HH24:MI:SS.FF9')
        AS order_placed_utc,
    TO_CHAR(l.order_cancel_dttm, 'YYYY-MM-DD HH24:MI:SS.FF9')
        AS order_cancel_utc
FROM edldb.bt_hca_hcdm.order_line_cost_measures_rxp AS l
INNER JOIN
    requested AS k
    ON l.order_id = k.order_id AND l.order_line_id = k.order_line_id

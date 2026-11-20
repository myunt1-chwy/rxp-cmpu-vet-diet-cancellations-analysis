{% set start_date = start_date | default('2026-08-15') %}
{% set end_date = end_date | default('2026-10-15') %}
{% set as_of_date = as_of_date | default('2026-10-27') %}
-- Database-derived cohort; only scalar dates/timezone are inputs.
-- Current source state can differ from retained historical snapshots.
WITH cohort_prescriptions AS (
    SELECT
        rx_id,
        customer_id,
        first_order_id,
        CASE
            WHEN REGEXP_LIKE(TRIM(first_orderitem_id), '^[0-9]+$')
                THEN TRY_TO_NUMBER(first_orderitem_id)
        END AS first_order_line_id
    FROM edldb.bt_hca_hcdm.rxp_prescriptions
    WHERE
        prescription_source = 'CMPU' AND is_vet_diet_flag = TRUE
        AND approval_channel = 'CUSTOMER_UPLOAD'
        AND rx_creation_datetime >= '{{ start_date }}'::TIMESTAMP_NTZ
        AND rx_creation_datetime < '{{ end_date }}'::TIMESTAMP_NTZ
),

linked_orders AS (
    SELECT
        l.order_id,
        l.order_line_id,
        0 AS first_order_line
    FROM edldb.bt_hca_hcdm.order_line_cost_measures_rxp AS l
    INNER JOIN
        cohort_prescriptions AS p
        ON TRIM(l.rx_id) = p.rx_id AND l.customer_id = p.customer_id
    WHERE l.is_vet_diet_flag = TRUE
),

first_orders AS (
    SELECT
        first_order_id AS order_id,
        first_order_line_id AS order_line_id,
        1 AS first_order_line
    FROM cohort_prescriptions
    WHERE first_order_id IS NOT NULL AND first_order_line_id IS NOT NULL
),

requested AS (
    SELECT
        order_id,
        order_line_id,
        MAX(first_order_line) AS first_order_line
    FROM (
        SELECT * FROM linked_orders
        UNION ALL
        SELECT * FROM first_orders
    ) AS linked
    WHERE order_id IS NOT NULL AND order_line_id IS NOT NULL
    GROUP BY order_id, order_line_id
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
    k.first_order_line,
    TO_CHAR(l.order_placed_dttm, 'YYYY-MM-DD HH24:MI:SS.FF9')
        AS order_placed_utc,
    TO_CHAR(l.order_cancel_dttm, 'YYYY-MM-DD HH24:MI:SS.FF9')
        AS order_cancel_utc
FROM edldb.bt_hca_hcdm.order_line_cost_measures_rxp AS l
INNER JOIN
    requested AS k
    ON l.order_id = k.order_id AND l.order_line_id = k.order_line_id

{% set start_date = start_date | default('2026-08-15') %}
{% set end_date = end_date | default('2026-10-15') %}
{% set as_of_date = as_of_date | default('2026-10-27') %}
-- Database-derived cohort; only scalar dates/timezone are inputs.
-- Current source state can differ from retained historical snapshots.
WITH cohort_prescriptions AS (
    SELECT
        customer_id,
        first_order_id,
        TRIM(rx_id) AS rx_id,
        CASE
            WHEN
                REGEXP_LIKE(TRIM(first_orderitem_id), '^[0-9]+$')
                THEN TRY_TO_NUMBER(first_orderitem_id)
        END AS first_order_line_id
    FROM edldb.bt_hca_hcdm.rxp_prescriptions
    WHERE
        prescription_source = 'CMPU' AND is_vet_diet_flag = TRUE
        AND approval_channel = 'CUSTOMER_UPLOAD'
        AND rx_creation_datetime >= '{{ start_date }}'::TIMESTAMP_NTZ
        AND rx_creation_datetime < '{{ end_date }}'::TIMESTAMP_NTZ
),

requested AS (
    SELECT p.rx_id
    FROM cohort_prescriptions AS p
    INNER JOIN edldb.bt_hca_hcdm.order_line_cost_measures_rxp AS l
        ON
            p.first_order_id = l.order_id
            AND p.first_order_line_id = l.order_line_id
            AND p.customer_id = l.customer_id
    GROUP BY p.rx_id
    HAVING COUNT_IF(NULLIF(TRIM(l.order_cancel_reason), '') IS NOT NULL) = 0
),

prescriptions AS (
    SELECT
        r.rx_id,
        p.customer_id,
        p.first_order_id AS order_id,
        CASE
            WHEN REGEXP_LIKE(TRIM(p.first_orderitem_id), '^[0-9]+$')
                THEN TRY_TO_NUMBER(p.first_orderitem_id)
        END AS order_line_id,
        NULLIF(UPPER(TRIM(p.rx_status)), '') AS rx_status,
        COUNT(p.rx_id) OVER (PARTITION BY r.rx_id) AS source_rows
    FROM requested AS r
    LEFT JOIN
        edldb.bt_hca_hcdm.rxp_prescriptions AS p
        ON r.rx_id = TRIM(p.rx_id)
),

prescription_lines AS (
    SELECT DISTINCT
        order_id,
        order_line_id
    FROM prescriptions
),

normalized_lines AS (
    SELECT
        l.order_id,
        l.order_line_id,
        l.customer_id,
        NULLIF(UPPER(TRIM(l.order_status)), '') AS order_status,
        NULLIF(UPPER(TRIM(l.order_order_line_status)), '') AS line_item_status,
        NULLIF(LOWER(TRIM(l.order_cancel_reason)), '')
            AS order_cancellation_reason
    FROM edldb.bt_hca_hcdm.order_line_cost_measures_rxp AS l
    INNER JOIN prescription_lines AS p
        ON l.order_id = p.order_id AND l.order_line_id = p.order_line_id
),

lines AS (
    SELECT
        order_id,
        order_line_id,
        COUNT(*) AS shipment_rows,
        MIN(customer_id) AS line_customer_id,
        COUNT(DISTINCT customer_id)
        + IFF(COUNT_IF(customer_id IS NULL) > 0, 1, 0) AS customer_variants,
        MIN(order_status) AS order_status,
        COUNT(DISTINCT order_status)
        + IFF(COUNT_IF(order_status IS NULL) > 0, 1, 0)
            AS order_status_variants,
        MIN(line_item_status) AS line_item_status,
        COUNT(DISTINCT line_item_status)
        + IFF(COUNT_IF(line_item_status IS NULL) > 0, 1, 0)
            AS line_status_variants,
        MIN(order_cancellation_reason) AS order_cancellation_reason,
        COUNT(DISTINCT order_cancellation_reason)
        + IFF(COUNT_IF(order_cancellation_reason IS NULL) > 0, 1, 0)
            AS reason_variants
    FROM normalized_lines
    GROUP BY order_id, order_line_id
)

SELECT
    p.*,
    l.shipment_rows,
    l.line_customer_id,
    l.customer_variants,
    l.order_status,
    l.order_status_variants,
    l.line_item_status,
    l.line_status_variants,
    l.order_cancellation_reason,
    l.reason_variants,
    CONVERT_TIMEZONE('UTC', CURRENT_TIMESTAMP())::VARCHAR AS extracted_at_utc
FROM prescriptions AS p LEFT JOIN lines AS l
    ON p.order_id = l.order_id AND p.order_line_id = l.order_line_id

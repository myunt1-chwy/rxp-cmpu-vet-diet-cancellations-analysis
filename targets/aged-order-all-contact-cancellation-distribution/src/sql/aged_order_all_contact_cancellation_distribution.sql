-- REFNUM 32: no reorder requirement. All handled contact history on aged
-- orders.
-- RX_CREATION_DATETIME, ORDER_CANCEL_DTTM and SESSION_START_DTTM are UTC.
-- Cancellation interpretation follows the UTC/Eastern validation established in
-- REFNUM 5.
WITH prescriptions AS (
    SELECT
        rx_id,
        customer_id AS rx_customer_id,
        first_order_id,
        first_orderitem_id,
        CASE
            WHEN REGEXP_LIKE(TRIM(first_orderitem_id), '^[0-9]+$')
                THEN TRY_TO_NUMBER(first_orderitem_id)
        END AS first_order_line_id,
        TO_CHAR(rx_creation_datetime, 'YYYY-MM-DD HH24:MI:SS.FF9')
            AS rx_creation_datetime,
        COUNT(*) OVER (PARTITION BY rx_id) AS rx_source_rows
    FROM edldb.bt_hca_hcdm.rxp_prescriptions
    WHERE
        prescription_source = 'CMPU' AND is_vet_diet_flag = TRUE
        AND approval_channel = 'CUSTOMER_UPLOAD'
        AND rx_creation_datetime >= '{{ start_date }}'::TIMESTAMP_NTZ
        AND rx_creation_datetime < '{{ end_date }}'::TIMESTAMP_NTZ
),

lines_keys AS (
    SELECT DISTINCT
        first_order_id,
        first_order_line_id
    FROM prescriptions
    WHERE first_order_id IS NOT NULL AND first_order_line_id IS NOT NULL
),

lines AS (
    SELECT
        l.order_id,
        l.order_line_id,
        MIN(l.customer_id) AS customer_id,
        COUNT(DISTINCT l.customer_id)
        + IFF(COUNT_IF(l.customer_id IS NULL) > 0, 1, 0) AS customer_variants,
        MIN(LOWER(TRIM(l.order_cancel_reason))) AS order_cancel_reason,
        COUNT(DISTINCT LOWER(TRIM(l.order_cancel_reason)))
        + IFF(COUNT_IF(l.order_cancel_reason IS NULL) > 0, 1, 0)
            AS reason_variants,
        MIN(l.order_cancel_dttm) AS order_cancel_time,
        COUNT(DISTINCT l.order_cancel_dttm) AS cancel_variants,
        COUNT(*) AS shipment_rows
    FROM edldb.bt_hca_hcdm.order_line_cost_measures_rxp AS l
    INNER JOIN lines_keys AS p
        ON
            l.order_id = p.first_order_id
            AND l.order_line_id = p.first_order_line_id
    GROUP BY l.order_id, l.order_line_id
),

associations AS (
    SELECT
        p.*,
        l.order_id,
        l.order_line_id,
        l.customer_id,
        l.customer_variants,
        l.order_cancel_reason,
        l.reason_variants,
        l.cancel_variants,
        l.shipment_rows,
        TO_CHAR(l.order_cancel_time, 'YYYY-MM-DD HH24:MI:SS.FF9'
        ) AS order_cancel_time
    FROM prescriptions AS p LEFT JOIN lines AS l
        ON
            p.first_order_id = l.order_id
            AND p.first_order_line_id = l.order_line_id
),

aged_orders AS (
    SELECT DISTINCT order_id FROM lines
    WHERE
        order_cancel_reason = 'aged order' AND order_cancel_time IS NOT NULL
        AND order_cancel_time <= '{{ as_of_date }}'::TIMESTAMP_NTZ
),

contacts AS (
    SELECT
        c.order_id,
        c.leg_id,
        c.session_id,
        c.session_channel,
        c.category_wismo_flag,
        c.handled_flag,
        TO_CHAR(c.session_start_dttm, 'YYYY-MM-DD HH24:MI:SS.FF9')
            AS contact_at_utc
    FROM edldb.bt_customer_care.fct_contacts_brd AS c
    INNER JOIN aged_orders AS a ON c.order_id = a.order_id
    WHERE c.handled_flag = TRUE
),

records AS (
    SELECT
        'association' AS record_type,
        OBJECT_CONSTRUCT_KEEP_NULL(a.*)::VARCHAR AS payload
    FROM associations AS a
    UNION ALL
    SELECT
        'contact' AS record_type,
        OBJECT_CONSTRUCT_KEEP_NULL(c.*)::VARCHAR AS payload
    FROM contacts AS c
)

SELECT
    record_type,
    payload,
    CURRENT_TIMESTAMP::VARCHAR AS extracted_at_session_time,
    CURRENT_WAREHOUSE() AS extraction_warehouse
FROM records

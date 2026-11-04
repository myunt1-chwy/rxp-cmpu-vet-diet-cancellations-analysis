-- REFNUM 55: prescription decision evidence for the three matched-first-order
-- populations.
-- Current prescription snapshot; creation window and aged cancellation cutoff
-- are UTC.
WITH prescriptions AS (
    SELECT DISTINCT
        rx_id,
        customer_id,
        rx_creation_datetime,
        approval_channel,
        first_order_id,
        first_orderitem_id,
        approved_numerator,
        approved_denominator,
        rx_status,
        rx_lifecycle_state,
        state_change_reason,
        min_approved_datetime,
        min_denied_datetime,
        CASE
            WHEN REGEXP_LIKE(TRIM(first_orderitem_id), '^[0-9]+$')
                THEN TRY_TO_NUMBER(first_orderitem_id)
        END AS first_order_line_id
    FROM edldb.bt_hca_hcdm.rxp_prescriptions
    WHERE
        prescription_source = 'CMPU' AND is_vet_diet_flag = TRUE
        AND rx_creation_datetime >= '2026-08-15'::TIMESTAMP_NTZ
        AND rx_creation_datetime < '2026-10-15'::TIMESTAMP_NTZ
),

p AS (
    SELECT DISTINCT
        first_order_id,
        first_order_line_id
    FROM prescriptions
),

lines AS (
    SELECT
        l.order_id,
        l.order_line_id,
        COUNT(*) AS shipment_rows,
        MIN(l.prescription_approved) AS prescription_approved,
        COUNT(DISTINCT l.prescription_approved)
        + IFF(COUNT_IF(l.prescription_approved IS NULL) > 0, 1, 0)
            AS approval_flag_variants,
        MIN(LOWER(TRIM(l.order_cancel_reason))) AS cancel_reason,
        COUNT(DISTINCT LOWER(TRIM(l.order_cancel_reason)))
        + IFF(COUNT_IF(l.order_cancel_reason IS NULL) > 0, 1, 0)
            AS reason_variants,
        MIN(l.order_cancel_dttm) AS cancel_time,
        COUNT(DISTINCT l.order_cancel_dttm) AS cancel_variants,
        MAX(l.max_denied_datetime) AS line_last_denied_datetime
    FROM edldb.bt_hca_hcdm.order_line_cost_measures_rxp AS l
    INNER JOIN
        p
        ON
            l.order_id = p.first_order_id
            AND l.order_line_id = p.first_order_line_id
    GROUP BY l.order_id, l.order_line_id
)

SELECT
    p.rx_id,
    p.customer_id,
    p.approval_channel,
    p.first_order_id,
    p.first_orderitem_id,
    p.first_order_line_id,
    p.approved_numerator,
    p.approved_denominator,
    p.rx_status,
    p.rx_lifecycle_state,
    p.state_change_reason,
    l.order_id,
    l.order_line_id,
    l.shipment_rows,
    l.prescription_approved,
    l.approval_flag_variants,
    l.cancel_reason,
    l.reason_variants,
    l.cancel_variants,
    CURRENT_TIMESTAMP::VARCHAR AS extracted_at_session_time,
    TO_CHAR(p.rx_creation_datetime, 'YYYY-MM-DD HH24:MI:SS.FF9')
        AS rx_creation_datetime,
    TO_CHAR(p.min_approved_datetime, 'YYYY-MM-DD HH24:MI:SS.FF9')
        AS rx_first_approved_datetime,
    TO_CHAR(p.min_denied_datetime, 'YYYY-MM-DD HH24:MI:SS.FF9')
        AS rx_first_denied_datetime,
    TO_CHAR(l.cancel_time, 'YYYY-MM-DD HH24:MI:SS.FF9') AS cancel_time,
    TO_CHAR(l.line_last_denied_datetime, 'YYYY-MM-DD HH24:MI:SS.FF9')
        AS line_last_denied_datetime
FROM prescriptions AS p INNER JOIN lines AS l
    ON p.first_order_id = l.order_id AND p.first_order_line_id = l.order_line_id

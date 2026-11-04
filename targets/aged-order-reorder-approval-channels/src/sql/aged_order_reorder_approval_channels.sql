{% set start_date = start_date | default('2026-08-15') %}
{% set end_date = end_date | default('2026-10-15') %}
{% set as_of_date = as_of_date | default('2026-10-27') %}
-- Database-derived cohort; only scalar dates/timezone are inputs.
-- Current source state can differ from retained historical snapshots.
WITH cohort_evidence AS (
    WITH prescriptions AS (
        SELECT
            rx_id,
            customer_id,
            product_id,
            rx_creation_datetime,
            approval_channel,
            first_order_id,
            first_orderitem_id,
            CASE
                WHEN REGEXP_LIKE(TRIM(first_orderitem_id), '^[0-9]+$')
                    THEN TRY_TO_NUMBER(first_orderitem_id)
            END AS first_order_line_id,
            COUNT(*) OVER (PARTITION BY rx_id) AS rx_source_rows
        FROM edldb.bt_hca_hcdm.rxp_prescriptions
        WHERE
            prescription_source = 'CMPU' AND is_vet_diet_flag = TRUE
            AND approval_channel = 'CUSTOMER_UPLOAD'
            AND rx_creation_datetime >= '{{ start_date }}'::TIMESTAMP_NTZ
            AND rx_creation_datetime < '{{ end_date }}'::TIMESTAMP_NTZ
    ),

    catalog_latest AS (
        SELECT
            part_number,
            product_id
        FROM edldb.pdm.product
        QUALIFY DENSE_RANK() OVER (
            PARTITION BY part_number
            ORDER BY snapshot_date DESC, last_updated_dttm DESC
        ) = 1
    ),

    product_mapping AS (
        SELECT
            part_number,
            MIN(product_id) AS product_id,
            COUNT(DISTINCT product_id) AS product_variants
        FROM catalog_latest
        GROUP BY part_number
    ),

    originals AS (
        SELECT
            l.order_id AS original_order_id,
            l.order_line_id AS original_line_id,
            MIN(l.customer_id) AS original_customer_id,
            COUNT(DISTINCT l.customer_id)
            + IFF(COUNT_IF(l.customer_id IS NULL) > 0, 1, 0)
                AS original_customer_variants,
            MIN(m.product_id) AS original_product_id,
            GREATEST(
                COUNT(DISTINCT m.product_id),
                COALESCE(MAX(m.product_variants), 0)
            ) AS original_product_variants,
            COUNT(*) AS original_shipment_rows,
            MIN(l.order_order_line_status) AS original_line_status,
            COUNT(DISTINCT l.order_order_line_status)
            + IFF(COUNT_IF(l.order_order_line_status IS NULL) > 0, 1, 0)
                AS original_status_variants,
            MIN(l.order_cancel_reason) AS order_cancel_reason,
            COUNT(DISTINCT LOWER(TRIM(l.order_cancel_reason)))
            + IFF(COUNT_IF(l.order_cancel_reason IS NULL) > 0, 1, 0)
                AS original_reason_variants,
            MIN(l.order_cancel_dttm) AS order_cancel_time,
            COUNT(DISTINCT l.order_cancel_dttm) AS original_cancel_variants
        FROM edldb.bt_hca_hcdm.order_line_cost_measures_rxp AS l
        INNER JOIN (
            SELECT DISTINCT
                first_order_id,
                first_order_line_id
            FROM prescriptions
            WHERE first_order_id IS NOT NULL AND first_order_line_id IS NOT NULL
        ) AS p
            ON
                l.order_id = p.first_order_id
                AND l.order_line_id = p.first_order_line_id
        LEFT JOIN product_mapping AS m ON l.product_part_number = m.part_number
        GROUP BY l.order_id, l.order_line_id
    ),

    aged AS (
        SELECT * FROM originals
        WHERE
            LOWER(TRIM(order_cancel_reason)) = 'aged order'
            AND order_cancel_time IS NOT NULL
            AND order_cancel_time <= '{{ as_of_date }}'::TIMESTAMP_NTZ
    ),

    candidate_keys AS (
    -- Find keys first, then fetch ALL their shipment rows for conflict checks.
        SELECT DISTINCT
            l.order_id,
            l.order_line_id
        FROM edldb.bt_hca_hcdm.order_line_cost_measures_rxp AS l
        INNER JOIN product_mapping AS m ON l.product_part_number = m.part_number
        INNER JOIN
            aged
                AS a
            ON
                l.customer_id = a.original_customer_id
                AND m.product_id = a.original_product_id
                AND l.order_id <> a.original_order_id
                AND l.order_placed_dttm > a.order_cancel_time
                AND l.order_placed_dttm
                <= DATEADD(HOUR, 168, a.order_cancel_time)
                AND l.order_placed_dttm <= '{{ as_of_date }}'::TIMESTAMP_NTZ
    ),

    reorders AS (
        SELECT
            l.order_id AS reorder_order_id,
            l.order_line_id AS reorder_line_id,
            MIN(l.customer_id) AS reorder_customer_id,
            COUNT(DISTINCT l.customer_id)
            + IFF(COUNT_IF(l.customer_id IS NULL) > 0, 1, 0)
                AS reorder_customer_variants,
            MIN(m.product_id) AS reorder_product_id,
            GREATEST(
                COUNT(DISTINCT m.product_id),
                COALESCE(MAX(m.product_variants), 0)
            ) AS reorder_product_variants,
            COUNT(*) AS reorder_shipment_rows,
            MIN(l.order_order_line_status) AS reorder_line_status,
            COUNT(DISTINCT l.order_order_line_status)
            + IFF(COUNT_IF(l.order_order_line_status IS NULL) > 0, 1, 0)
                AS reorder_status_variants,
            MIN(l.order_placed_dttm) AS reorder_placed_at_utc,
            MIN(l.order_placed_dttm_est) AS reorder_placed_at_eastern,
            COUNT(DISTINCT l.order_placed_dttm)
            + IFF(COUNT_IF(l.order_placed_dttm IS NULL) > 0, 1, 0)
                AS reorder_placement_variants,
            MIN(l.order_line_shipped_dttm) AS reorder_shipped_at_utc,
            MIN(l.order_line_shipped_dttm_est) AS reorder_shipped_at_eastern
        FROM edldb.bt_hca_hcdm.order_line_cost_measures_rxp AS l
        INNER JOIN
            candidate_keys AS k
            ON l.order_id = k.order_id AND l.order_line_id = k.order_line_id
        LEFT JOIN product_mapping AS m ON l.product_part_number = m.part_number
        GROUP BY l.order_id, l.order_line_id
    )

    SELECT
        p.rx_id,
        p.customer_id,
        p.product_id,
        p.approval_channel,
        p.first_order_id,
        p.first_orderitem_id,
        p.first_order_line_id,
        p.rx_source_rows,
        a.original_order_id,
        a.original_line_id,
        a.original_customer_id,
        a.original_customer_variants,
        a.original_product_id,
        a.original_product_variants,
        a.original_shipment_rows,
        a.original_line_status,
        a.original_status_variants,
        a.order_cancel_reason,
        a.original_reason_variants,
        a.original_cancel_variants,
        r.reorder_order_id,
        r.reorder_line_id,
        r.reorder_customer_id,
        r.reorder_customer_variants,
        r.reorder_product_id,
        r.reorder_product_variants,
        r.reorder_shipment_rows,
        r.reorder_line_status,
        r.reorder_status_variants,
        r.reorder_placement_variants,
        TO_CHAR(p.p.rx_creation_datetime, 'YYYY-MM-DD HH24:MI:SS.FF9'
        ) AS rx_creation_datetime,
        TO_CHAR(a.a.order_cancel_time, 'YYYY-MM-DD HH24:MI:SS.FF9'
        ) AS order_cancel_time,
        TO_CHAR(r.r.reorder_placed_at_utc, 'YYYY-MM-DD HH24:MI:SS.FF9'
        ) AS reorder_placed_at_utc,
        TO_CHAR(r.r.reorder_placed_at_eastern, 'YYYY-MM-DD HH24:MI:SS.FF9'
        ) AS reorder_placed_at_eastern,
        TO_CHAR(r.r.reorder_shipped_at_utc, 'YYYY-MM-DD HH24:MI:SS.FF9'
        ) AS reorder_shipped_at_utc,
        TO_CHAR(r.r.reorder_shipped_at_eastern, 'YYYY-MM-DD HH24:MI:SS.FF9'
        ) AS reorder_shipped_at_eastern,
        CURRENT_TIMESTAMP::VARCHAR AS extracted_at_session_time,
        CURRENT_WAREHOUSE() AS extraction_warehouse
    FROM prescriptions AS p
    LEFT JOIN
        originals AS a
        ON
            p.first_order_id = a.original_order_id
            AND p.first_order_line_id = a.original_line_id
    LEFT JOIN reorders
        AS r ON LOWER(TRIM(a.order_cancel_reason)) = 'aged order'
    AND a.original_customer_id = r.reorder_customer_id
    AND a.original_product_id = r.reorder_product_id
    AND a.original_order_id <> r.reorder_order_id
    AND a.order_cancel_time < r.reorder_placed_at_utc
    AND r.reorder_placed_at_utc <= DATEADD(HOUR, 168, a.order_cancel_time)
    AND r.reorder_placed_at_utc <= '{{ as_of_date }}'::TIMESTAMP_NTZ
),

eligible_reorder_pairs AS (
    SELECT DISTINCT
        7 AS followup_days,
        original_customer_id,
        original_order_id,
        original_line_id,
        reorder_order_id,
        reorder_line_id,
        order_cancel_time::TIMESTAMP_NTZ AS order_cancel_time,
        reorder_placed_at_utc::TIMESTAMP_NTZ AS reorder_placed_at_utc
    FROM cohort_evidence
    WHERE
        LOWER(TRIM(order_cancel_reason)) = 'aged order'
        AND original_customer_id IS NOT NULL AND original_product_id IS NOT NULL
        AND reorder_order_id IS NOT NULL
        AND DATEADD(DAY, 7, order_cancel_time::TIMESTAMP_NTZ)
        <= '{{ as_of_date }}'::TIMESTAMP_NTZ
        AND (customer_id IS NULL OR customer_id = original_customer_id)
        AND (product_id IS NULL OR product_id = original_product_id)
        AND rx_source_rows = 1
        AND original_customer_variants = 1 AND original_status_variants = 1
        AND original_reason_variants = 1 AND original_cancel_variants <= 1
        AND original_product_variants <= 1
        AND reorder_customer_variants = 1 AND reorder_status_variants = 1
        AND reorder_placement_variants = 1 AND reorder_product_variants <= 1
),

requested_prescriptions AS (
    SELECT DISTINCT NULLIF(TRIM(l.rx_id), '') AS rx_id
    FROM eligible_reorder_pairs AS p
    INNER JOIN edldb.bt_hca_hcdm.order_line_cost_measures_rxp AS l
        ON
            p.reorder_order_id = l.order_id
            AND p.reorder_line_id = l.order_line_id
    WHERE NULLIF(TRIM(l.rx_id), '') IS NOT NULL
)

SELECT
    k.rx_id,
    p.rx_id AS matched_rx_id,
    p.approval_channel,
    CURRENT_TIMESTAMP::VARCHAR AS extracted_at_session_time,
    CURRENT_WAREHOUSE() AS extraction_warehouse,
    COUNT(p.rx_id) OVER (PARTITION BY k.rx_id) AS prescription_rows
FROM requested_prescriptions AS k
LEFT JOIN edldb.bt_hca_hcdm.rxp_prescriptions AS p ON k.rx_id = p.rx_id

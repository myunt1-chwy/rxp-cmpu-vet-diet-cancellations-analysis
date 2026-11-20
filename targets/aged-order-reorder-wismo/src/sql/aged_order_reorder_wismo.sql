{% set start_date = start_date | default('2026-08-15') %}
{% set end_date = end_date | default('2026-10-15') %}
{% set as_of_date = as_of_date | default('2026-10-27') %}
{% set contact_timezone = contact_timezone | default('UTC') %}
-- Database-derived cohort; only scalar dates/timezone are inputs.
-- Current source state can differ from retained historical snapshots.
WITH cohort_evidence AS (
    WITH horizons AS (
        SELECT 7 AS followup_days
        UNION ALL
        SELECT 14
        UNION ALL
        SELECT 21
    ),

    prescriptions AS (
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
            MIN(l.pet_id) AS original_pet_id,
            COUNT(DISTINCT l.pet_id)
            + IFF(COUNT_IF(l.pet_id IS NULL) > 0, 1, 0)
                AS original_pet_variants,
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
                <= DATEADD(DAY, 21, a.order_cancel_time)
                AND DATEADD(DAY, 7, a.order_cancel_time)
                <= '{{ as_of_date }}'::TIMESTAMP_NTZ
                AND l.order_placed_dttm <= '{{ as_of_date }}'::TIMESTAMP_NTZ
    ),

    reorders AS (
        SELECT
            l.order_id AS reorder_order_id,
            l.order_line_id AS reorder_line_id,
            MIN(l.customer_id) AS reorder_customer_id,
            MIN(l.pet_id) AS reorder_pet_id,
            COUNT(DISTINCT l.pet_id)
            + IFF(COUNT_IF(l.pet_id IS NULL) > 0, 1, 0) AS reorder_pet_variants,
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
        TO_CHAR(p.p.rx_creation_datetime, 'YYYY-MM-DD HH24:MI:SS.FF9'
        ) AS rx_creation_datetime,
        p.approval_channel,
        p.first_order_id,
        p.first_orderitem_id,
        p.first_order_line_id,
        p.rx_source_rows,
        a.original_order_id,
        a.original_line_id,
        a.original_customer_id,
        a.original_pet_id,
        a.original_pet_variants,
        a.original_customer_variants,
        a.original_product_id,
        a.original_product_variants,
        a.original_shipment_rows,
        a.original_line_status,
        a.original_status_variants,
        a.order_cancel_reason,
        a.original_reason_variants,
        TO_CHAR(a.a.order_cancel_time, 'YYYY-MM-DD HH24:MI:SS.FF9'
        ) AS order_cancel_time,
        a.original_cancel_variants,
        r.reorder_order_id,
        r.reorder_line_id,
        r.reorder_customer_id,
        r.reorder_pet_id,
        r.reorder_pet_variants,
        r.reorder_customer_variants,
        r.reorder_product_id,
        r.reorder_product_variants,
        r.reorder_shipment_rows,
        r.reorder_line_status,
        r.reorder_status_variants,
        TO_CHAR(r.r.reorder_placed_at_utc, 'YYYY-MM-DD HH24:MI:SS.FF9'
        ) AS reorder_placed_at_utc,
        TO_CHAR(r.r.reorder_placed_at_eastern, 'YYYY-MM-DD HH24:MI:SS.FF9'
        ) AS reorder_placed_at_eastern,
        r.reorder_placement_variants,
        TO_CHAR(r.r.reorder_shipped_at_utc, 'YYYY-MM-DD HH24:MI:SS.FF9'
        ) AS reorder_shipped_at_utc,
        TO_CHAR(r.r.reorder_shipped_at_eastern, 'YYYY-MM-DD HH24:MI:SS.FF9'
        ) AS reorder_shipped_at_eastern,
        h.followup_days,
        CURRENT_TIMESTAMP::VARCHAR AS extracted_at_session_time,
        CURRENT_WAREHOUSE() AS extraction_warehouse,
        (SELECT COUNT(*) FROM reorders) AS candidate_reorder_lines,
        (
            SELECT COALESCE(COUNT_IF(reorders.reorder_pet_id IS NULL), 0)
            FROM reorders
        ) AS candidate_missing_pet_lines,
        (
            SELECT COALESCE(COUNT_IF(reorders.reorder_pet_variants > 1), 0)
            FROM reorders
        ) AS candidate_ambiguous_pet_lines,
        TO_CHAR(
            DATEADD(DAY, h.followup_days, a.order_cancel_time),
            'YYYY-MM-DD HH24:MI:SS.FF9'
        ) AS window_end_utc,
        IFF(
            DATEADD(DAY, h.followup_days, a.order_cancel_time)
            <= '{{ as_of_date }}'::TIMESTAMP_NTZ,
            TRUE, FALSE
        ) AS followup_complete
    FROM prescriptions AS p
    CROSS JOIN horizons AS h
    LEFT JOIN
        originals AS a
        ON
            p.first_order_id = a.original_order_id
            AND p.first_order_line_id = a.original_line_id
    LEFT JOIN reorders
        AS r ON LOWER(TRIM(a.order_cancel_reason)) = 'aged order'
    AND a.original_customer_id = r.reorder_customer_id
    AND a.original_product_id = r.reorder_product_id
    AND a.original_pet_id IS NOT NULL AND r.reorder_pet_id IS NOT NULL
    AND a.original_pet_variants = 1 AND r.reorder_pet_variants = 1
    AND a.original_pet_id = r.reorder_pet_id
    AND a.original_order_id <> r.reorder_order_id
    AND a.order_cancel_time < r.reorder_placed_at_utc
    AND r.reorder_placed_at_utc
    <= DATEADD(DAY, h.followup_days, a.order_cancel_time)
    AND DATEADD(DAY, h.followup_days, a.order_cancel_time)
    <= '{{ as_of_date }}'::TIMESTAMP_NTZ
    AND r.reorder_placed_at_utc <= '{{ as_of_date }}'::TIMESTAMP_NTZ
),

eligible_reorder_pairs AS (
    SELECT DISTINCT
        followup_days,
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
        AND DATEADD(DAY, followup_days, order_cancel_time::TIMESTAMP_NTZ)
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

selected_reorder_pairs AS (
-- Preserve the Python selection: shortest delay per customer and horizon,
-- Break ties by reorder time, reorder IDs, then original IDs.
    SELECT * FROM eligible_reorder_pairs
    QUALIFY ROW_NUMBER() OVER (
        PARTITION BY followup_days, original_customer_id
        ORDER BY
            DATEDIFF(NANOSECOND, order_cancel_time, reorder_placed_at_utc),
            reorder_placed_at_utc, reorder_order_id, reorder_line_id,
            original_order_id, original_line_id
    ) = 1
),

selected_intervals AS (
    SELECT DISTINCT
        original_order_id,
        order_cancel_time,
        reorder_placed_at_utc
    FROM selected_reorder_pairs
),

requested AS (
    SELECT
        original_order_id,
        order_cancel_time,
        reorder_placed_at_utc,
        ROW_NUMBER()
            OVER (
                ORDER BY
                    original_order_id, order_cancel_time, reorder_placed_at_utc
            )
            AS request_id
    FROM selected_intervals
),

requested_orders AS (
    SELECT DISTINCT original_order_id FROM requested
),

contacts AS (
    SELECT
        c.order_id,
        c.leg_id,
        c.session_id,
        c.session_channel,
        c.session_start_dttm AS session_start_dttm_raw,
        c.category_wismo_flag,
        c.handled_flag,
        CONVERT_TIMEZONE('{{ contact_timezone }}', 'UTC', c.session_start_dttm)
            AS contact_at_utc
    FROM edldb.bt_customer_care.fct_contacts_brd AS c
    INNER JOIN
        requested_orders AS d
        ON c.order_id = d.original_order_id
    WHERE c.category_wismo_flag = TRUE AND c.handled_flag = TRUE
),

order_audit AS (
    SELECT
        order_id,
        COUNT(*) AS all_handled_wismo_order_rows,
        COUNT_IF(contact_at_utc IS NULL) AS missing_session_time_rows
    FROM contacts
    GROUP BY order_id
),

wismo_contacts AS (
    SELECT
        d.request_id,
        COUNT(*) AS wismo_contact_count,
        COUNT(DISTINCT c.session_id) AS distinct_wismo_sessions,
        MIN(c.contact_at_utc) AS first_wismo_dttm,
        MAX(c.contact_at_utc) AS last_wismo_dttm,
        LISTAGG(DISTINCT c.session_channel, ', ') WITHIN GROUP (
            ORDER BY c.session_channel
        ) AS wismo_channels,
        ARRAY_AGG(OBJECT_CONSTRUCT_KEEP_NULL(
            'order_id',
            c.order_id,
            'leg_id',
            c.leg_id,
            'session_id',
            c.session_id,
            'session_channel', c.session_channel,
            'session_start_dttm_raw',
            TO_CHAR(c.session_start_dttm_raw, 'YYYY-MM-DD HH24:MI:SS.FF9'),
            'contact_at_utc',
            TO_CHAR(c.contact_at_utc, 'YYYY-MM-DD HH24:MI:SS.FF9'),
            'category_wismo_flag',
            c.category_wismo_flag,
            'handled_flag',
            c.handled_flag
        ))::VARCHAR AS matched_contacts_json
    FROM requested AS d
    INNER JOIN contacts AS c
        ON
            d.original_order_id = c.order_id
            AND d.order_cancel_time < c.contact_at_utc
            AND d.reorder_placed_at_utc > c.contact_at_utc
    GROUP BY d.request_id
)

SELECT
    d.request_id,
    d.original_order_id,
    CURRENT_TIMESTAMP::VARCHAR AS extracted_at_session_time,
    CURRENT_WAREHOUSE() AS extraction_warehouse,
    TO_CHAR(d.order_cancel_time, 'YYYY-MM-DD HH24:MI:SS.FF9')
        AS order_cancel_time,
    TO_CHAR(d.reorder_placed_at_utc, 'YYYY-MM-DD HH24:MI:SS.FF9')
        AS reorder_placed_at_utc,
    COALESCE(w.wismo_contact_count, 0) AS wismo_contact_count,
    COALESCE(w.distinct_wismo_sessions, 0) AS distinct_wismo_sessions,
    TO_CHAR(w.first_wismo_dttm, 'YYYY-MM-DD HH24:MI:SS.FF9')
        AS first_wismo_dttm,
    TO_CHAR(w.last_wismo_dttm, 'YYYY-MM-DD HH24:MI:SS.FF9') AS last_wismo_dttm,
    COALESCE(w.wismo_channels, '') AS wismo_channels,
    COALESCE(w.matched_contacts_json, '[]') AS matched_contacts_json,
    COALESCE(a.all_handled_wismo_order_rows, 0) AS all_handled_wismo_order_rows,
    COALESCE(a.missing_session_time_rows, 0) AS missing_session_time_rows
FROM requested AS d
LEFT JOIN wismo_contacts AS w ON d.request_id = w.request_id
LEFT JOIN order_audit AS a ON d.original_order_id = a.order_id

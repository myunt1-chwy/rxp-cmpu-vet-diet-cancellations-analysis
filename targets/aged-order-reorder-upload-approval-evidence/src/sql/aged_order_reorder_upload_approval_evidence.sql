{% set start_date = start_date | default('2026-08-15') %}
{% set end_date = end_date | default('2026-10-15') %}
{% set as_of_date = as_of_date | default('2026-10-27') %}
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
        p.rx_customer_id,
        p.rx_created_at_utc,
        p.prescription_rows,
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

requested_keys AS (
    SELECT
        original_order_id AS order_id,
        original_line_id AS order_line_id
    FROM selected_reorder_pairs
    UNION DISTINCT
    SELECT
        reorder_order_id AS order_id,
        reorder_line_id AS order_line_id
    FROM selected_reorder_pairs
),

line_prescription_identity AS (
    SELECT
        k.order_id,
        k.order_line_id,
        MIN(NULLIF(TRIM(l.rx_id), '')) AS rx_id,
        COUNT(DISTINCT NULLIF(TRIM(l.rx_id), '')) AS rx_variants,
        COUNT_IF(NULLIF(TRIM(l.rx_id), '') IS NULL) AS missing_rx_rows
    FROM requested_keys AS k
    LEFT JOIN edldb.bt_hca_hcdm.order_line_cost_measures_rxp AS l
        ON k.order_id = l.order_id AND k.order_line_id = l.order_line_id
    GROUP BY k.order_id, k.order_line_id
),

different_prescription_lines AS (
    SELECT DISTINCT
        r.rx_id,
        p.original_customer_id AS customer_id,
        p.reorder_order_id AS order_id,
        p.reorder_line_id AS order_line_id
    FROM selected_reorder_pairs AS p
    INNER JOIN
        line_prescription_identity AS o
        ON
            p.original_order_id = o.order_id
            AND p.original_line_id = o.order_line_id
    INNER JOIN
        line_prescription_identity AS r
        ON
            p.reorder_order_id = r.order_id
            AND p.reorder_line_id = r.order_line_id
    WHERE
        o.rx_variants = 1 AND r.rx_variants = 1
        AND o.missing_rx_rows = 0
        AND r.missing_rx_rows = 0
        AND o.rx_id <> r.rx_id
),

requested AS (
    SELECT DISTINCT
        rx_id,
        customer_id
    FROM different_prescription_lines
),

prescriptions AS (
    SELECT
        p.rx_id,
        MIN(p.customer_id) AS rx_customer_id,
        MIN(p.rx_creation_datetime) AS rx_created_at_utc,
        COUNT(*) AS prescription_rows
    FROM edldb.bt_hca_hcdm.rxp_prescriptions AS p
    INNER JOIN requested AS k ON p.rx_id = k.rx_id
    GROUP BY p.rx_id
),

upload_source AS (
    SELECT
        upload_id,
        customer_id AS raw_customer_id,
        rx_id AS rx_ids,
        created_ts_utc,
        has_uploaded_file::VARCHAR AS uploaded_file_flag,
        COUNT(*) OVER (PARTITION BY upload_id) AS upload_source_rows
    FROM edldb.bt_hca_hcdm.rxp_upload_entity
    WHERE
        upload_type = 'DIET_PRESCRIPTION'
        AND (
            created_ts_utc <= '{{ as_of_date }}'::TIMESTAMP_NTZ
            OR created_ts_utc IS NULL
        )
),

expanded AS (
    SELECT DISTINCT
        u.upload_id,
        u.raw_customer_id,
        u.created_ts_utc,
        u.uploaded_file_flag,
        u.upload_source_rows,
        NULLIF(TRIM(t.value::VARCHAR), '') AS rx_id,
        CASE
            WHEN REGEXP_LIKE(TRIM(u.raw_customer_id), '^[0-9]+$')
                THEN TRY_TO_NUMBER(u.raw_customer_id)
        END AS upload_customer_id
    FROM upload_source AS u,
        LATERAL FLATTEN(
            INPUT => SPLIT(TRIM(COALESCE(u.rx_ids, ''), '{}'), ','),
            OUTER => TRUE
        ) AS t
),

relevant AS (
    SELECT e.* FROM expanded AS e INNER JOIN requested AS k ON e.rx_id = k.rx_id
),

audit AS (
    SELECT
        k.rx_id,
        COUNT_IF(e.upload_id IS NULL OR e.upload_source_rows <> 1)
            AS invalid_related_upload_rows,
        COUNT_IF(e.upload_customer_id IS NULL) AS invalid_related_customer_rows,
        COUNT(
            DISTINCT IFF(
                e.upload_customer_id <> k.customer_id, e.upload_id, NULL
            )
        ) AS other_customer_uploads
    FROM relevant AS e INNER JOIN requested AS k ON e.rx_id = k.rx_id
    GROUP BY k.rx_id
),

upload_evidence AS (
    SELECT
        k.rx_id,
        k.customer_id,
        p.rx_customer_id,
        e.upload_id,
        e.upload_customer_id,
        e.upload_source_rows,
        e.uploaded_file_flag,
        CURRENT_TIMESTAMP::VARCHAR AS extracted_at_session_time,
        CURRENT_WAREHOUSE() AS extraction_warehouse,
        COALESCE(p.prescription_rows, 0) AS prescription_rows,
        TO_CHAR(p.rx_created_at_utc, 'YYYY-MM-DD HH24:MI:SS.FF9')
            AS rx_created_at_utc,
        TO_CHAR(e.created_ts_utc, 'YYYY-MM-DD HH24:MI:SS.FF9')
            AS uploaded_at_utc,
        COALESCE(a.invalid_related_upload_rows, 0)
            AS invalid_related_upload_rows,
        COALESCE(a.invalid_related_customer_rows, 0)
            AS invalid_related_customer_rows,
        COALESCE(a.other_customer_uploads, 0) AS other_customer_uploads
    FROM requested AS k
    LEFT JOIN prescriptions AS p ON k.rx_id = p.rx_id
    LEFT JOIN
        relevant AS e
        ON k.rx_id = e.rx_id AND k.customer_id = e.upload_customer_id
    LEFT JOIN audit AS a ON k.rx_id = a.rx_id

),

requested_lines AS (
    SELECT
        rx_id,
        customer_id,
        order_id,
        order_line_id
    FROM different_prescription_lines
),

line_evidence AS (
    SELECT
        k.order_id,
        k.order_line_id,
        COUNT(l.order_line_id) AS line_source_rows,
        COUNT(DISTINCT NULLIF(TRIM(l.rx_id), '')) AS line_rx_variants,
        MIN(NULLIF(TRIM(l.rx_id), '')) AS line_rx_id,
        COUNT_IF(
            l.order_line_id IS NOT NULL AND NULLIF(TRIM(l.rx_id), '') IS NULL
        ) AS missing_line_rx_rows,
        MIN(l.min_approved_denied_datetime) AS min_approved_denied_datetime,
        COUNT(DISTINCT l.min_approved_denied_datetime) AS approval_variants,
        COUNT(l.min_approved_denied_datetime) AS populated_approval_rows
    FROM (SELECT DISTINCT
        order_id,
        order_line_id
    FROM requested_lines) AS k
    LEFT JOIN edldb.bt_hca_hcdm.order_line_cost_measures_rxp AS l
        ON k.order_id = l.order_id AND k.order_line_id = l.order_line_id
    GROUP BY k.order_id, k.order_line_id
)

SELECT
    u.*,
    k.order_id,
    k.order_line_id,
    l.line_source_rows,
    l.line_rx_variants,
    l.line_rx_id,
    l.missing_line_rx_rows,
    l.approval_variants,
    l.populated_approval_rows,
    TO_CHAR(l.min_approved_denied_datetime, 'YYYY-MM-DD HH24:MI:SS.FF9')
        AS min_approved_denied_datetime
FROM upload_evidence AS u
INNER JOIN
    requested_lines AS k
    ON u.rx_id = k.rx_id AND u.customer_id = k.customer_id
INNER JOIN
    line_evidence AS l
    ON k.order_id = l.order_id AND k.order_line_id = l.order_line_id

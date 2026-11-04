-- Same timing cohort and shipment collapse as REFNUM 16, enriched with upload
-- evidence.
WITH timing AS (
-- REFNUM 16: preserve unmatched prescriptions for eligibility auditing.
-- Timestamps are UTC except the explicit Eastern wall-clock companion.
    WITH prescriptions AS (
        SELECT
            rx_id,
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

    lines AS (
        SELECT
            o.order_id,
            o.order_line_id,
            COUNT(*) AS shipment_rows,
            MIN(o.order_order_line_status) AS line_status,
            COUNT(DISTINCT COALESCE(o.order_order_line_status, '[Missing]'))
                AS status_variants,
            MIN(o.order_line_created_dttm) AS line_created_utc,
            MIN(o.order_line_created_dttm_est) AS line_created_eastern,
            MIN(o.order_placed_dttm) AS order_placed_utc,
            COUNT(DISTINCT o.order_placed_dttm)
            + CASE
                WHEN COUNT_IF(o.order_placed_dttm IS NULL) > 0 THEN 1 ELSE 0
            END AS placement_variants,
            MIN(o.order_placed_dttm_est) AS order_placed_eastern,
            COUNT(DISTINCT o.order_placed_dttm_est) AS eastern_variants,
            COUNT_IF(o.order_placed_dttm_est IS NULL) AS missing_eastern_rows,
            MAX(o.max_approved_datetime) AS max_approved_datetime,
            COUNT_IF(o.max_approved_datetime IS NULL) AS missing_approval_rows,
            COUNT(DISTINCT o.max_approved_datetime) AS approval_variants
        FROM edldb.bt_hca_hcdm.order_line_cost_measures_rxp AS o
        INNER JOIN (
            SELECT DISTINCT
                first_order_id,
                first_order_line_id
            FROM prescriptions
            WHERE first_order_id IS NOT NULL AND first_order_line_id IS NOT NULL
        ) AS p
            ON
                o.order_id = p.first_order_id
                AND o.order_line_id = p.first_order_line_id
        GROUP BY o.order_id, o.order_line_id
    )

    SELECT
        p.*,
        l.*,
        CURRENT_TIMESTAMP::VARCHAR AS extracted_at_session_time,
        CURRENT_WAREHOUSE() AS extraction_warehouse
    FROM prescriptions AS p
    LEFT JOIN
        lines AS l
        ON
            p.first_order_id = l.order_id
            AND p.first_order_line_id = l.order_line_id
),

upload_source AS (
    SELECT
        upload_id,
        customer_id AS raw_customer_id,
        rx_id AS rx_ids,
        created_ts_utc,
        state_name,
        state_changed_ts_utc,
        CASE
            WHEN REGEXP_LIKE(TRIM(customer_id), '^[0-9]+$')
                THEN TRY_TO_NUMBER(customer_id)
        END AS customer_id,
        COUNT(*) OVER (PARTITION BY upload_id) AS upload_source_rows
    FROM edldb.bt_hca_hcdm.rxp_upload_entity
    WHERE
        upload_type = 'DIET_PRESCRIPTION'
        AND created_ts_utc >= '{{ upload_start_date }}'::TIMESTAMP_NTZ
        -- Upload evidence may arrive 11 days beyond the prescription window.
        AND created_ts_utc < '{{ upload_end_date }}'::TIMESTAMP_NTZ
),

expanded AS (
    SELECT DISTINCT
        u.upload_id,
        u.customer_id,
        u.created_ts_utc,
        u.state_name,
        u.state_changed_ts_utc,
        NULLIF(TRIM(t.value::VARCHAR), '') AS rx_id
    FROM upload_source AS u,
        LATERAL FLATTEN(
            INPUT => SPLIT(TRIM(COALESCE(u.rx_ids, ''), '{}'), ','),
            OUTER => TRUE
        ) AS t
),

ranked_uploads AS (
    SELECT
        *,
        ROW_NUMBER() OVER (
            PARTITION BY rx_id, customer_id ORDER BY created_ts_utc, upload_id
        ) AS upload_rank
    FROM expanded
    WHERE
        customer_id IS NOT NULL AND REGEXP_LIKE(rx_id, '^[A-Za-z0-9_-]+$')
        AND state_name = 'ACCEPTED'
),

uploads AS (
    SELECT
        rx_id,
        customer_id,
        COUNT(DISTINCT upload_id) AS upload_count,
        MIN(created_ts_utc) AS first_upload_at_utc,
        MAX(IFF(upload_rank = 1, upload_id, NULL)) AS selected_upload_id,
        MAX(IFF(upload_rank = 1, state_changed_ts_utc, NULL))
            AS upload_state_changed_at_utc,
        MIN(state_name) AS selected_upload_state
    FROM ranked_uploads
    GROUP BY rx_id, customer_id
),

audit AS (
    SELECT
        COUNT(*) AS window_upload_rows,
        COUNT_IF(state_name = 'ACCEPTED') AS accepted_window_upload_rows,
        COUNT_IF(state_name IS NULL OR state_name <> 'ACCEPTED')
            AS excluded_window_upload_rows,
        COALESCE(COUNT_IF(upload_id IS NULL OR upload_source_rows <> 1), 0)
            AS invalid_upload_source_rows,
        COALESCE(COUNT_IF(NULLIF(TRIM(raw_customer_id), '') IS NULL), 0)
            AS uploads_missing_customer,
        COALESCE(
            COUNT_IF(
                NULLIF(TRIM(raw_customer_id), '') IS NOT NULL
                AND customer_id IS NULL
            ),
            0
        ) AS uploads_invalid_customer,
        (
            SELECT COUNT(*) FROM expanded
            WHERE expanded.rx_id IS NULL)
            AS upload_rows_missing_rx,
        (
            SELECT COUNT(*)
            FROM expanded
            WHERE
                expanded.rx_id IS NOT NULL
                AND NOT REGEXP_LIKE(expanded.rx_id, '^[A-Za-z0-9_-]+$')
        ) AS upload_rows_malformed_rx
    FROM upload_source
)

SELECT
    t.*,
    a.*,
    u.first_upload_at_utc,
    u.selected_upload_id,
    u.selected_upload_state,
    u.upload_state_changed_at_utc,
    COALESCE(u.upload_count, 0) AS upload_count
FROM timing AS t
INNER JOIN edldb.bt_hca_hcdm.rxp_prescriptions AS p ON t.rx_id = p.rx_id
LEFT JOIN uploads AS u ON t.rx_id = u.rx_id AND p.customer_id = u.customer_id
CROSS JOIN audit AS a

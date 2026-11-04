-- All available physical rows; no date, upload-type or study-cohort filters.
-- Total counts are separate scans, not sums of the grouped results.
-- Both ID fields can contain brace-delimited/comma-separated lists; the
-- notification-service field is a JSON array. Count an entry once if any
-- normalized token is populated and is not a numeric zero or JSON null.
WITH hcdm AS (
    SELECT
        associated_resource_type,
        ARRAY_SIZE(FILTER(
            SPLIT(TRANSLATE(COALESCE(rx_id, ''), '{}[]"', ''), ','),
            token -> LOWER(TRIM(token::VARCHAR)) NOT IN ('', 'null')
            AND COALESCE(TRY_TO_DOUBLE(TRIM(token::VARCHAR)), 1) <> 0
        )) > 0 AS has_nonzero_rx_id
    FROM edldb.bt_hca_hcdm.rxp_upload_entity
),

notification AS (
    SELECT
        associated_resource_type,
        ARRAY_SIZE(FILTER(
            SPLIT(
                TRANSLATE(
                    COALESCE(TO_JSON(associated_resource_ids), ''), '{}[]"', ''
                ),
                ','
            ),
            token -> LOWER(TRIM(token::VARCHAR)) NOT IN ('', 'null')
            AND COALESCE(TRY_TO_DOUBLE(TRIM(token::VARCHAR)), 1) <> 0
        )) > 0 AS has_nonzero_rx_id
    FROM edldb.rxp_notification_service.upload_entity
),

counts AS (
    SELECT
        'EDLDB.BT_HCA_HCDM.rxp_upload_entity' AS source_table,
        associated_resource_type::VARCHAR AS associated_resource_type,
        COUNT(*) AS entry_count,
        COALESCE(COUNT_IF(has_nonzero_rx_id), 0) AS entries_with_nonzero_rx_id,
        FALSE AS is_total
    FROM hcdm
    GROUP BY associated_resource_type
    UNION ALL
    SELECT
        'EDLDB.BT_HCA_HCDM.rxp_upload_entity' AS source_table,
        NULL AS associated_resource_type,
        COUNT(*) AS entry_count,
        COALESCE(COUNT_IF(has_nonzero_rx_id), 0) AS entries_with_nonzero_rx_id,
        TRUE AS is_total
    FROM hcdm
    UNION ALL
    SELECT
        'EDLDB.rxp_notification_service.upload_entity' AS source_table,
        associated_resource_type::VARCHAR,
        COUNT(*) AS entry_count,
        COALESCE(COUNT_IF(has_nonzero_rx_id), 0) AS entries_with_nonzero_rx_id,
        FALSE AS is_total
    FROM notification
    GROUP BY associated_resource_type
    UNION ALL
    SELECT
        'EDLDB.rxp_notification_service.upload_entity' AS source_table,
        NULL AS associated_resource_type,
        COUNT(*) AS entry_count,
        COALESCE(COUNT_IF(has_nonzero_rx_id), 0) AS entries_with_nonzero_rx_id,
        TRUE AS is_total
    FROM notification
)

SELECT
    source_table,
    associated_resource_type,
    entry_count,
    entries_with_nonzero_rx_id,
    is_total,
    TO_CHAR(
        CONVERT_TIMEZONE('UTC', CURRENT_TIMESTAMP()),
        'YYYY-MM-DD HH24:MI:SS'
    ) AS extracted_at_utc
FROM counts
ORDER BY is_total, associated_resource_type NULLS LAST, source_table

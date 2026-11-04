-- Creation-time coverage of all current source entries, without date or ID
-- filters.
WITH entries AS (
    SELECT
        'EDLDB.BT_HCA_HCDM.rxp_upload_entity' AS source_table,
        associated_resource_type,
        created_ts_utc AS created_utc_ts
    FROM edldb.bt_hca_hcdm.rxp_upload_entity
    UNION ALL
    SELECT
        'EDLDB.rxp_notification_service.upload_entity' AS source_table,
        associated_resource_type,
        CONVERT_TIMEZONE('UTC', created_at)::TIMESTAMP_NTZ AS created_utc_ts
    FROM edldb.rxp_notification_service.upload_entity
)

SELECT
    source_table,
    associated_resource_type,
    GROUPING(associated_resource_type) = 1 AS is_overall,
    COUNT(*) AS entry_count,
    COUNT(created_utc_ts) AS timestamp_count,
    TO_CHAR(MIN(created_utc_ts), 'YYYY-MM-DD HH24:MI:SS.FF9')
        AS min_created_utc_ts,
    TO_CHAR(MAX(created_utc_ts), 'YYYY-MM-DD HH24:MI:SS.FF9')
        AS max_created_utc_ts,
    TO_CHAR(
        CONVERT_TIMEZONE('UTC', CURRENT_TIMESTAMP()),
        'YYYY-MM-DD HH24:MI:SS'
    ) AS extracted_at_utc
FROM entries
GROUP BY
    GROUPING SETS (
        (source_table, associated_resource_type),
        (source_table)
    )
ORDER BY is_overall, associated_resource_type NULLS LAST, source_table

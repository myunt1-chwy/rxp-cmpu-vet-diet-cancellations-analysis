-- All available physical rows; no date, upload-type or study-cohort filters.
-- Total counts are separate scans, not sums of the grouped results.
WITH counts AS (
    SELECT 'EDLDB.BT_HCA_HCDM.rxp_upload_entity' AS source_table,
           associated_resource_type::VARCHAR AS associated_resource_type,
           COUNT(*) AS entry_count, FALSE AS is_total
    FROM EDLDB.BT_HCA_HCDM.rxp_upload_entity
    GROUP BY associated_resource_type
    UNION ALL
    SELECT 'EDLDB.BT_HCA_HCDM.rxp_upload_entity', NULL, COUNT(*), TRUE
    FROM EDLDB.BT_HCA_HCDM.rxp_upload_entity
    UNION ALL
    SELECT 'EDLDB.rxp_notification_service.upload_entity',
           associated_resource_type::VARCHAR, COUNT(*), FALSE
    FROM EDLDB.rxp_notification_service.upload_entity
    GROUP BY associated_resource_type
    UNION ALL
    SELECT 'EDLDB.rxp_notification_service.upload_entity', NULL, COUNT(*), TRUE
    FROM EDLDB.rxp_notification_service.upload_entity
)
SELECT source_table, associated_resource_type, entry_count, is_total,
       TO_CHAR(CONVERT_TIMEZONE('UTC', CURRENT_TIMESTAMP()),
               'YYYY-MM-DD HH24:MI:SS') AS extracted_at_utc
FROM counts
ORDER BY is_total, associated_resource_type NULLS LAST, source_table

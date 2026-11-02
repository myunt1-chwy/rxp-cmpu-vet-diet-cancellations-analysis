-- Independent FLATTEN-based numerator check. Distinct-upload counts also
-- establish whether upload_id can identify a physical source row here.
WITH raw AS (
    SELECT 'EDLDB.BT_HCA_HCDM.rxp_upload_entity' AS source_table,
           associated_resource_type, upload_id,
           COALESCE(rx_id, '') AS rx_id_list
    FROM EDLDB.BT_HCA_HCDM.rxp_upload_entity
    UNION ALL
    SELECT 'EDLDB.rxp_notification_service.upload_entity',
           associated_resource_type, upload_id,
           COALESCE(TO_JSON(associated_resource_ids), '')
    FROM EDLDB.rxp_notification_service.upload_entity
), expanded AS (
    SELECT r.*, TRIM(f.value::VARCHAR) AS rx_token
    FROM raw r,
         LATERAL FLATTEN(INPUT => SPLIT(TRANSLATE(r.rx_id_list, '{}[]"', ''), ','), OUTER => TRUE) f
)
SELECT source_table, associated_resource_type,
       COUNT(DISTINCT upload_id) AS distinct_uploads,
       COUNT(DISTINCT CASE
           WHEN LOWER(rx_token) NOT IN ('', 'null')
            AND COALESCE(TRY_TO_DOUBLE(rx_token), 1) <> 0
           THEN upload_id END) AS entries_with_nonzero_rx_id
FROM expanded
GROUP BY source_table, associated_resource_type

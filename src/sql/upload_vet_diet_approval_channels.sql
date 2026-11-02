-- All normalized source prescription IDs, joined to the prescription registry.
-- No date, CMPU, approval-channel, approval-status or upload-resource-type filters.
WITH upload_ids AS (
    SELECT DISTINCT 'EDLDB.BT_HCA_HCDM.rxp_upload_entity' AS source_table,
           TRIM(f.value::VARCHAR) AS rx_id
    FROM EDLDB.BT_HCA_HCDM.RXP_UPLOAD_ENTITY u,
         LATERAL FLATTEN(INPUT => SPLIT(TRANSLATE(COALESCE(u.rx_id, ''), '{}[]"', ''), ',')) f
    WHERE LOWER(TRIM(f.value::VARCHAR)) NOT IN ('', 'null')
      AND COALESCE(TRY_TO_DOUBLE(TRIM(f.value::VARCHAR)), 1) <> 0
    UNION
    SELECT 'EDLDB.rxp_notification_service.upload_entity',
           TRIM(f.value::VARCHAR)
    FROM EDLDB.RXP_NOTIFICATION_SERVICE.UPLOAD_ENTITY u,
         LATERAL FLATTEN(INPUT => SPLIT(
             TRANSLATE(COALESCE(TO_JSON(u.associated_resource_ids), ''), '{}[]"', ''), ','
         )) f
    WHERE LOWER(TRIM(f.value::VARCHAR)) NOT IN ('', 'null')
      AND COALESCE(TRY_TO_DOUBLE(TRIM(f.value::VARCHAR)), 1) <> 0
)
SELECT TO_CHAR(CONVERT_TIMEZONE('UTC', CURRENT_TIMESTAMP()),
               'YYYY-MM-DD HH24:MI:SS') AS extracted_at_utc,
       u.source_table, u.rx_id,
       p.rx_id AS matched_rx_id,
       p.is_vet_diet_flag, p.approval_channel
FROM upload_ids u
LEFT JOIN EDLDB.BT_HCA_HCDM.RXP_PRESCRIPTIONS p ON u.rx_id = TRIM(p.rx_id)

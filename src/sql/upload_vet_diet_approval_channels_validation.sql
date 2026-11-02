-- Independent warehouse counts by registry match/category and approval channel.
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
SELECT u.source_table,
       CASE WHEN p.rx_id IS NULL THEN 'Unmatched RX_ID'
            WHEN p.is_vet_diet_flag = TRUE THEN 'Vet diet'
            WHEN p.is_vet_diet_flag = FALSE THEN 'Non-vet diet'
            ELSE 'Unknown vet-diet flag' END AS match_category,
       CASE WHEN p.is_vet_diet_flag = TRUE THEN p.approval_channel END AS approval_channel,
       COUNT(*) AS joined_rows,
       COUNT(DISTINCT u.rx_id) AS prescriptions
FROM upload_ids u
LEFT JOIN EDLDB.BT_HCA_HCDM.RXP_PRESCRIPTIONS p ON u.rx_id = TRIM(p.rx_id)
GROUP BY u.source_table, match_category,
         CASE WHEN p.is_vet_diet_flag = TRUE THEN p.approval_channel END

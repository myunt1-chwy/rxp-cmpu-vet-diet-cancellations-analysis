-- All normalized source prescription IDs, joined to the prescription registry.
-- No date, CMPU, approval-channel, approval-status or upload-resource-type
-- filters.
WITH upload_ids AS (
    SELECT DISTINCT
        'EDLDB.BT_HCA_HCDM.rxp_upload_entity' AS source_table,
        TRIM(f.value::VARCHAR) AS rx_id
    FROM edldb.bt_hca_hcdm.rxp_upload_entity AS u,
        LATERAL FLATTEN(
            INPUT => SPLIT(TRANSLATE(COALESCE(u.rx_id, ''), '{}[]"', ''), ',')
        ) AS f
    WHERE
        LOWER(TRIM(f.value::VARCHAR)) NOT IN ('', 'null')
        AND COALESCE(TRY_TO_DOUBLE(TRIM(f.value::VARCHAR)), 1) <> 0
    UNION DISTINCT
    SELECT
        'EDLDB.rxp_notification_service.upload_entity' AS source_table,
        TRIM(f.value::VARCHAR) AS rx_id
    FROM edldb.rxp_notification_service.upload_entity AS u,
        LATERAL FLATTEN(INPUT => SPLIT(
            TRANSLATE(
                COALESCE(TO_JSON(u.associated_resource_ids), ''), '{}[]"', ''
            ),
            ','
        )) AS f
    WHERE
        LOWER(TRIM(f.value::VARCHAR)) NOT IN ('', 'null')
        AND COALESCE(TRY_TO_DOUBLE(TRIM(f.value::VARCHAR)), 1) <> 0
)

SELECT
    u.source_table,
    u.rx_id,
    p.rx_id AS matched_rx_id,
    p.is_vet_diet_flag,
    p.approval_channel,
    TO_CHAR(
        CONVERT_TIMEZONE('UTC', CURRENT_TIMESTAMP()),
        'YYYY-MM-DD HH24:MI:SS'
    ) AS extracted_at_utc
FROM upload_ids AS u
LEFT JOIN edldb.bt_hca_hcdm.rxp_prescriptions AS p ON u.rx_id = TRIM(p.rx_id)

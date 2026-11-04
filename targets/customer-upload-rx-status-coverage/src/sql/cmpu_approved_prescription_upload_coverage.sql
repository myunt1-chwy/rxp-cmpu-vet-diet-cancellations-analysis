-- One record per qualifying vet-diet prescription, retaining every current
-- RX_STATUS.
-- July 30, 2026 is inclusive at 00:00 UTC; there is no upper creation-date
-- bound.
WITH prescriptions AS (
    SELECT
        rx_creation_datetime,
        rx_status,
        prescription_source,
        TRIM(rx_id) AS rx_id,
        COUNT(*) OVER (PARTITION BY TRIM(rx_id)) AS prescription_source_rows
    FROM edldb.bt_hca_hcdm.rxp_prescriptions
    WHERE
        approval_channel = 'CUSTOMER_UPLOAD'
        AND is_vet_diet_flag = TRUE
        AND rx_creation_datetime >= '2026-07-30 00:00:00'::TIMESTAMP_NTZ
),

hcdm_ids AS (
    SELECT DISTINCT TRIM(f.value::VARCHAR) AS rx_id
    FROM edldb.bt_hca_hcdm.rxp_upload_entity AS u,
        LATERAL FLATTEN(
            INPUT => SPLIT(TRANSLATE(COALESCE(u.rx_id, ''), '{}[]"', ''), ',')
        ) AS f
    WHERE
        LOWER(TRIM(f.value::VARCHAR)) NOT IN ('', 'null')
        AND COALESCE(TRY_TO_DOUBLE(TRIM(f.value::VARCHAR)), 1) <> 0
),

notification_ids AS (
    SELECT DISTINCT TRIM(f.value::VARCHAR) AS rx_id
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
    p.rx_id,
    p.prescription_source,
    p.rx_status,
    p.rx_creation_datetime::VARCHAR AS rx_creation_datetime,
    p.prescription_source_rows,
    TO_CHAR(
        CONVERT_TIMEZONE('UTC', CURRENT_TIMESTAMP()),
        'YYYY-MM-DD HH24:MI:SS'
    ) AS extracted_at_utc,
    h.rx_id IS NOT NULL AS has_hcdm_upload,
    n.rx_id IS NOT NULL AS has_notification_upload
FROM prescriptions AS p
LEFT JOIN hcdm_ids AS h ON p.rx_id = h.rx_id
LEFT JOIN notification_ids AS n ON p.rx_id = n.rx_id

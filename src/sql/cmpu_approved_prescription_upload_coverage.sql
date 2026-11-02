-- One record per qualifying vet-diet prescription, retaining every current RX_STATUS.
-- July 30, 2026 is inclusive at 00:00 UTC; there is no upper creation-date bound.
WITH prescriptions AS (
    SELECT TRIM(rx_id) AS rx_id, rx_creation_datetime, rx_status, prescription_source,
           COUNT(*) OVER (PARTITION BY TRIM(rx_id)) AS prescription_source_rows
    FROM EDLDB.BT_HCA_HCDM.RXP_PRESCRIPTIONS
    WHERE approval_channel = 'CUSTOMER_UPLOAD'
      AND is_vet_diet_flag = TRUE
      AND rx_creation_datetime >= '2026-07-30 00:00:00'::TIMESTAMP_NTZ
), hcdm_ids AS (
    SELECT DISTINCT TRIM(f.value::VARCHAR) AS rx_id
    FROM EDLDB.BT_HCA_HCDM.RXP_UPLOAD_ENTITY u,
         LATERAL FLATTEN(INPUT => SPLIT(TRANSLATE(COALESCE(u.rx_id, ''), '{}[]"', ''), ',')) f
    WHERE LOWER(TRIM(f.value::VARCHAR)) NOT IN ('', 'null')
      AND COALESCE(TRY_TO_DOUBLE(TRIM(f.value::VARCHAR)), 1) <> 0
), notification_ids AS (
    SELECT DISTINCT TRIM(f.value::VARCHAR) AS rx_id
    FROM EDLDB.RXP_NOTIFICATION_SERVICE.UPLOAD_ENTITY u,
         LATERAL FLATTEN(INPUT => SPLIT(
             TRANSLATE(COALESCE(TO_JSON(u.associated_resource_ids), ''), '{}[]"', ''), ','
         )) f
    WHERE LOWER(TRIM(f.value::VARCHAR)) NOT IN ('', 'null')
      AND COALESCE(TRY_TO_DOUBLE(TRIM(f.value::VARCHAR)), 1) <> 0
)
SELECT TO_CHAR(CONVERT_TIMEZONE('UTC', CURRENT_TIMESTAMP()),
               'YYYY-MM-DD HH24:MI:SS') AS extracted_at_utc,
       p.rx_id, p.prescription_source, p.rx_status,
       p.rx_creation_datetime::VARCHAR AS rx_creation_datetime,
       p.prescription_source_rows,
       h.rx_id IS NOT NULL AS has_hcdm_upload,
       n.rx_id IS NOT NULL AS has_notification_upload
FROM prescriptions p
LEFT JOIN hcdm_ids h ON p.rx_id = h.rx_id
LEFT JOIN notification_ids n ON p.rx_id = n.rx_id

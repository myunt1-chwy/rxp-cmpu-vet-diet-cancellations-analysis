-- Independent vet-diet membership aggregation by status; rx_id-only upload joins.
WITH prescriptions AS (
    SELECT TRIM(rx_id) AS rx_id, rx_status, prescription_source
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
), membership AS (
    SELECT p.rx_id, p.rx_status, p.prescription_source,
           h.rx_id IS NOT NULL AS in_hcdm,
           n.rx_id IS NOT NULL AS in_notification
    FROM prescriptions p
    LEFT JOIN hcdm_ids h ON p.rx_id = h.rx_id
    LEFT JOIN notification_ids n ON p.rx_id = n.rx_id
)
SELECT prescription_source, rx_status,
       GROUPING(prescription_source) = 1 AS is_source_rollup,
       GROUPING(rx_status) = 1 AS is_status_rollup,
       GROUPING(prescription_source) = 1 AND GROUPING(rx_status) = 1 AS is_overall,
       COUNT(*) AS source_rows,
       COUNT(DISTINCT rx_id) AS eligible_prescriptions,
       COUNT_IF(rx_id IS NULL OR rx_id = '') AS missing_rx_ids,
       COUNT(DISTINCT CASE WHEN in_hcdm THEN rx_id END) AS any_hcdm,
       COUNT(DISTINCT CASE WHEN in_notification THEN rx_id END) AS any_notification,
       COUNT(DISTINCT CASE WHEN in_hcdm AND in_notification THEN rx_id END) AS both_sources,
       COUNT(DISTINCT CASE WHEN in_hcdm AND NOT in_notification THEN rx_id END) AS hcdm_only,
       COUNT(DISTINCT CASE WHEN NOT in_hcdm AND in_notification THEN rx_id END) AS notification_only,
       COUNT(DISTINCT CASE WHEN NOT in_hcdm AND NOT in_notification THEN rx_id END) AS neither_source
FROM membership
GROUP BY GROUPING SETS (
    (prescription_source, rx_status),
    (prescription_source),
    (rx_status),
    ()
)

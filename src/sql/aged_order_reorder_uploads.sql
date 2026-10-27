-- Different RX_IDs used on frozen eligible REFNUM 22 reorders.
-- Search all DIET_PRESCRIPTION history through the baseline as-of cutoff.
WITH requested AS (
    SELECT value[0]::VARCHAR AS rx_id, value[1]::NUMBER(38,0) AS customer_id
    FROM TABLE(FLATTEN(INPUT => PARSE_JSON('{{ requested_json }}')))
), prescriptions AS (
    SELECT p.rx_id, MIN(p.customer_id) AS rx_customer_id,
           MIN(p.rx_creation_datetime) AS rx_created_at_utc, COUNT(*) AS prescription_rows
    FROM EDLDB.BT_HCA_HCDM.RXP_PRESCRIPTIONS p
    JOIN requested k ON p.rx_id=k.rx_id
    GROUP BY p.rx_id
), upload_source AS (
    SELECT upload_id, customer_id AS raw_customer_id, rx_id AS rx_ids,
           created_ts_utc, has_uploaded_file::VARCHAR AS uploaded_file_flag,
           COUNT(*) OVER (PARTITION BY upload_id) AS upload_source_rows
    FROM EDLDB.BT_HCA_HCDM.RXP_UPLOAD_ENTITY
    WHERE upload_type='DIET_PRESCRIPTION'
      AND (created_ts_utc <= '{{ as_of_date }}'::TIMESTAMP_NTZ OR created_ts_utc IS NULL)
), expanded AS (
    SELECT DISTINCT u.upload_id, u.raw_customer_id, u.created_ts_utc, u.uploaded_file_flag,
           u.upload_source_rows, NULLIF(TRIM(t.value::VARCHAR),'') AS rx_id,
           CASE WHEN REGEXP_LIKE(TRIM(u.raw_customer_id),'^[0-9]+$')
                THEN TRY_TO_NUMBER(u.raw_customer_id) END AS upload_customer_id
    FROM upload_source u,
         LATERAL FLATTEN(INPUT => SPLIT(TRIM(COALESCE(u.rx_ids,''),'{}'),','), OUTER => TRUE) t
), relevant AS (
    SELECT e.* FROM expanded e JOIN requested k ON e.rx_id=k.rx_id
), audit AS (
    SELECT k.rx_id,
           COUNT_IF(e.upload_id IS NULL OR e.upload_source_rows<>1) AS invalid_related_upload_rows,
           COUNT_IF(e.upload_customer_id IS NULL) AS invalid_related_customer_rows,
           COUNT(DISTINCT IFF(e.upload_customer_id<>k.customer_id,e.upload_id,NULL)) AS other_customer_uploads
    FROM relevant e JOIN requested k ON e.rx_id=k.rx_id
    GROUP BY k.rx_id
)
SELECT CURRENT_TIMESTAMP::VARCHAR AS extracted_at_session_time,
       CURRENT_WAREHOUSE() AS extraction_warehouse,
       k.rx_id, k.customer_id, p.rx_customer_id, COALESCE(p.prescription_rows,0) AS prescription_rows,
       TO_CHAR(p.rx_created_at_utc,'YYYY-MM-DD HH24:MI:SS.FF9') AS rx_created_at_utc,
       e.upload_id, e.upload_customer_id, e.upload_source_rows, e.uploaded_file_flag,
       TO_CHAR(e.created_ts_utc,'YYYY-MM-DD HH24:MI:SS.FF9') AS uploaded_at_utc,
       COALESCE(a.invalid_related_upload_rows,0) AS invalid_related_upload_rows,
       COALESCE(a.invalid_related_customer_rows,0) AS invalid_related_customer_rows,
       COALESCE(a.other_customer_uploads,0) AS other_customer_uploads
FROM requested k
LEFT JOIN prescriptions p ON k.rx_id=p.rx_id
LEFT JOIN relevant e ON k.rx_id=e.rx_id AND k.customer_id=e.upload_customer_id
LEFT JOIN audit a ON k.rx_id=a.rx_id

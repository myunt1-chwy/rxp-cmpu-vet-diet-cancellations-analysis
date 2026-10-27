-- REFNUM 25 follow-up: all handled contact legs on the original aged order; no category filter.
-- Strict interval: cancellation < SESSION_START_DTTM (converted to UTC) < reorder placement.
WITH requested AS (
    SELECT value[0]::NUMBER(38,0) AS request_id, value[1]::NUMBER(38,0) AS original_order_id,
           value[2]::VARCHAR::TIMESTAMP_NTZ(9) AS order_cancel_time,
           value[3]::VARCHAR::TIMESTAMP_NTZ(9) AS reorder_placed_at_utc
    FROM TABLE(FLATTEN(INPUT => PARSE_JSON('{{ requested_json }}')))
), contacts AS (
    SELECT c.ORDER_ID, c.LEG_ID, c.SESSION_ID, c.SESSION_CHANNEL,
           c.SESSION_START_DTTM AS session_start_dttm_raw,
           {{ contact_time_expression }} AS contact_at_utc,
           c.CATEGORY_WISMO_FLAG, c.HANDLED_FLAG
    FROM EDLDB.BT_CUSTOMER_CARE.FCT_CONTACTS_BRD c
    INNER JOIN (SELECT DISTINCT original_order_id FROM requested) d ON c.ORDER_ID=d.original_order_id
    WHERE c.HANDLED_FLAG=TRUE
), order_audit AS (
    SELECT order_id, COUNT(*) AS all_handled_wismo_order_rows,
           COUNT_IF(contact_at_utc IS NULL) AS missing_session_time_rows
    FROM contacts GROUP BY order_id
), wismo_contacts AS (
    SELECT d.request_id, COUNT(*) AS wismo_contact_count,
           COUNT(DISTINCT c.SESSION_ID) AS distinct_wismo_sessions,
           MIN(c.contact_at_utc) AS first_wismo_dttm,
           MAX(c.contact_at_utc) AS last_wismo_dttm,
           LISTAGG(DISTINCT c.SESSION_CHANNEL, ', ') WITHIN GROUP (ORDER BY c.SESSION_CHANNEL) AS wismo_channels,
           ARRAY_AGG(OBJECT_CONSTRUCT_KEEP_NULL(
               'order_id', c.ORDER_ID, 'leg_id', c.LEG_ID, 'session_id', c.SESSION_ID,
               'session_channel', c.SESSION_CHANNEL,
               'session_start_dttm_raw', TO_CHAR(c.session_start_dttm_raw,'YYYY-MM-DD HH24:MI:SS.FF9'),
               'contact_at_utc', TO_CHAR(c.contact_at_utc,'YYYY-MM-DD HH24:MI:SS.FF9'),
               'category_wismo_flag', c.CATEGORY_WISMO_FLAG, 'handled_flag', c.HANDLED_FLAG
           ))::VARCHAR AS matched_contacts_json
    FROM requested d
    INNER JOIN contacts c ON c.ORDER_ID=d.original_order_id
      AND c.contact_at_utc > d.order_cancel_time
      AND c.contact_at_utc < d.reorder_placed_at_utc
    GROUP BY d.request_id
)
SELECT CURRENT_TIMESTAMP::VARCHAR AS extracted_at_session_time,
       CURRENT_WAREHOUSE() AS extraction_warehouse,
       d.request_id, d.original_order_id,
       TO_CHAR(d.order_cancel_time,'YYYY-MM-DD HH24:MI:SS.FF9') AS order_cancel_time,
       TO_CHAR(d.reorder_placed_at_utc,'YYYY-MM-DD HH24:MI:SS.FF9') AS reorder_placed_at_utc,
       COALESCE(w.wismo_contact_count,0) AS wismo_contact_count,
       COALESCE(w.distinct_wismo_sessions,0) AS distinct_wismo_sessions,
       TO_CHAR(w.first_wismo_dttm,'YYYY-MM-DD HH24:MI:SS.FF9') AS first_wismo_dttm,
       TO_CHAR(w.last_wismo_dttm,'YYYY-MM-DD HH24:MI:SS.FF9') AS last_wismo_dttm,
       COALESCE(w.wismo_channels,'') AS wismo_channels,
       COALESCE(w.matched_contacts_json,'[]') AS matched_contacts_json,
       COALESCE(a.all_handled_wismo_order_rows,0) AS all_handled_wismo_order_rows,
       COALESCE(a.missing_session_time_rows,0) AS missing_session_time_rows
FROM requested d
LEFT JOIN wismo_contacts w ON d.request_id=w.request_id
LEFT JOIN order_audit a ON d.original_order_id=a.order_id

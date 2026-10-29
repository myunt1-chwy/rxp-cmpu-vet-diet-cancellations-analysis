-- REFNUM 20. All unsuffixed timestamps are interpreted as UTC.
-- ORDER_CANCEL_DTTM follows the UTC/Eastern convention verified by REFNUM 5.
-- Shipment rows collapse before prescription associations; no status/flag exclusions.
WITH prescriptions AS (
    SELECT rx_id, customer_id, rx_creation_datetime, approval_channel,
           first_order_id, first_orderitem_id,
           CASE WHEN REGEXP_LIKE(TRIM(first_orderitem_id), '^[0-9]+$')
                THEN TRY_TO_NUMBER(first_orderitem_id) END AS first_order_line_id,
           COUNT(*) OVER (PARTITION BY rx_id) AS rx_source_rows
    FROM EDLDB.BT_HCA_HCDM.RXP_PRESCRIPTIONS
    WHERE prescription_source = 'CMPU' AND is_vet_diet_flag = TRUE
      AND approval_channel = 'CUSTOMER_UPLOAD'
      AND rx_creation_datetime >= '{{ start_date }}'::TIMESTAMP_NTZ
      AND rx_creation_datetime < '{{ end_date }}'::TIMESTAMP_NTZ
), lines AS (
    SELECT o.order_id, o.order_line_id, COUNT(*) AS shipment_rows,
           MIN(o.order_order_line_status) AS line_status,
           COUNT(DISTINCT o.order_order_line_status) + IFF(COUNT_IF(o.order_order_line_status IS NULL) > 0, 1, 0) AS line_status_variants,
           MIN(o.is_deleted) AS is_deleted,
           COUNT(DISTINCT o.is_deleted) + IFF(COUNT_IF(o.is_deleted IS NULL) > 0, 1, 0) AS is_deleted_variants,
           MIN(o.is_refill) AS is_refill,
           COUNT(DISTINCT o.is_refill) + IFF(COUNT_IF(o.is_refill IS NULL) > 0, 1, 0) AS is_refill_variants,
           MIN(o.order_line_created_dttm) AS line_created_utc,
           MIN(o.order_line_created_dttm_est) AS line_created_eastern,
           MIN(o.order_placed_dttm) AS order_placed_utc,
           COUNT(DISTINCT o.order_placed_dttm) + IFF(COUNT_IF(o.order_placed_dttm IS NULL) > 0, 1, 0) AS order_placed_utc_variants,
           MIN(o.order_placed_dttm_est) AS order_placed_eastern,
           COUNT(DISTINCT o.order_placed_dttm_est) AS eastern_variants,
           COUNT_IF(o.order_placed_dttm_est IS NULL) AS missing_eastern_rows,
           MIN(o.order_cancel_dttm) AS order_cancel_time,
           COUNT(DISTINCT o.order_cancel_dttm) AS cancellation_variants,
           MIN(o.min_approved_denied_datetime) AS min_approved_denied_datetime,
           COUNT(DISTINCT o.min_approved_denied_datetime) AS approval_variants,
           COUNT_IF(o.min_approved_denied_datetime IS NULL) AS missing_approval_rows
    FROM EDLDB.BT_HCA_HCDM.ORDER_LINE_COST_MEASURES_RXP o
    JOIN (SELECT DISTINCT first_order_id, first_order_line_id FROM prescriptions
          WHERE first_order_id IS NOT NULL AND first_order_line_id IS NOT NULL) p
      ON o.order_id = p.first_order_id AND o.order_line_id = p.first_order_line_id
    GROUP BY o.order_id, o.order_line_id
), upload_source AS (
    SELECT upload_id, customer_id AS raw_customer_id, rx_id AS rx_ids, created_ts_utc, state_name, state_changed_ts_utc,
           CASE WHEN REGEXP_LIKE(TRIM(customer_id), '^[0-9]+$')
                THEN TRY_TO_NUMBER(customer_id) END AS customer_id,
           COUNT(*) OVER (PARTITION BY upload_id) AS upload_source_rows
    FROM EDLDB.BT_HCA_HCDM.RXP_UPLOAD_ENTITY
    WHERE upload_type = 'DIET_PRESCRIPTION'
      AND created_ts_utc >= '{{ upload_start_date }}'::TIMESTAMP_NTZ
      -- Upload evidence may arrive 11 days beyond the prescription window.
      AND created_ts_utc < '{{ upload_end_date }}'::TIMESTAMP_NTZ
), expanded AS (
    SELECT DISTINCT u.upload_id, u.customer_id, u.created_ts_utc, u.state_name, u.state_changed_ts_utc,
           NULLIF(TRIM(t.value::VARCHAR), '') AS rx_id
    FROM upload_source u,
         LATERAL FLATTEN(INPUT => SPLIT(TRIM(COALESCE(u.rx_ids, ''), '{}'), ','), OUTER => TRUE) t
), ranked_uploads AS (
    SELECT *, ROW_NUMBER() OVER (
        PARTITION BY rx_id, customer_id ORDER BY created_ts_utc, upload_id
    ) AS upload_rank
    FROM expanded
    WHERE customer_id IS NOT NULL AND REGEXP_LIKE(rx_id, '^[A-Za-z0-9_-]+$')
      AND state_name = 'ACCEPTED'
), uploads AS (
    SELECT rx_id, customer_id, COUNT(DISTINCT upload_id) AS upload_count,
           MIN(created_ts_utc) AS first_upload_at_utc,
           MAX(IFF(upload_rank=1, upload_id, NULL)) AS selected_upload_id,
           MAX(IFF(upload_rank=1, state_changed_ts_utc, NULL)) AS upload_state_changed_at_utc,
           MIN(state_name) AS selected_upload_state
    FROM ranked_uploads
    GROUP BY rx_id, customer_id
), audit AS (
    SELECT COUNT(*) AS window_upload_rows,
           COUNT_IF(state_name='ACCEPTED') AS accepted_window_upload_rows,
           COUNT_IF(state_name IS NULL OR state_name<>'ACCEPTED') AS excluded_window_upload_rows,
           COALESCE(COUNT_IF(upload_id IS NULL OR upload_source_rows <> 1), 0) AS invalid_upload_source_rows,
           COALESCE(COUNT_IF(NULLIF(TRIM(raw_customer_id), '') IS NULL), 0) AS uploads_missing_customer,
           COALESCE(COUNT_IF(NULLIF(TRIM(raw_customer_id), '') IS NOT NULL AND customer_id IS NULL), 0) AS uploads_invalid_customer,
           (SELECT COUNT(*) FROM expanded WHERE rx_id IS NULL) AS upload_rows_missing_rx,
           (SELECT COUNT(*) FROM expanded WHERE rx_id IS NOT NULL
            AND NOT REGEXP_LIKE(rx_id, '^[A-Za-z0-9_-]+$')) AS upload_rows_malformed_rx
    FROM upload_source
), associations AS (
    SELECT p.*, COALESCE(u.upload_count, 0) AS upload_count,
           u.upload_state_changed_at_utc AS association_upload_time,
           u.first_upload_at_utc AS association_upload_created_time,
           u.selected_upload_id AS association_upload_id,
           u.selected_upload_state AS association_upload_state
    FROM prescriptions p
    LEFT JOIN uploads u ON p.rx_id = u.rx_id AND p.customer_id = u.customer_id
), ranked_line_uploads AS (
    SELECT *, COUNT(*) OVER (PARTITION BY first_order_id, first_order_line_id) AS prescription_associations,
           ROW_NUMBER() OVER (PARTITION BY first_order_id, first_order_line_id
               ORDER BY association_upload_created_time NULLS LAST, association_upload_id) AS line_upload_rank
    FROM associations
), line_uploads AS (
    SELECT first_order_id, first_order_line_id,
           association_upload_time AS actual_upload_time,
           association_upload_created_time AS actual_upload_created_time,
           association_upload_id AS actual_upload_id,
           prescription_associations
    FROM ranked_line_uploads WHERE line_upload_rank=1
), estimated AS (
    SELECT l.*, u.actual_upload_time, u.actual_upload_created_time, u.actual_upload_id, u.prescription_associations,
           DATEADD(nanosecond,
                   ROUND(DATEDIFF(nanosecond, l.order_placed_utc,
                                  l.min_approved_denied_datetime) * 0.96, 0)::NUMBER(38,0),
                   l.order_placed_utc) AS estimated_upload_time
    FROM lines l
    JOIN line_uploads u ON l.order_id = u.first_order_id
                      AND l.order_line_id = u.first_order_line_id
), candidates AS (
    SELECT *, COALESCE(actual_upload_time, estimated_upload_time) AS candidate_upload_time,
           CASE WHEN actual_upload_time IS NOT NULL THEN 'actual_upload'
                WHEN estimated_upload_time IS NOT NULL THEN 'estimated_upload'
                ELSE 'missing' END AS candidate_upload_source
    FROM estimated
), events AS (
    SELECT *, CASE WHEN candidate_upload_time IS NULL THEN order_cancel_time
                   WHEN order_cancel_time IS NULL THEN candidate_upload_time
                   ELSE LEAST(candidate_upload_time, order_cancel_time) END AS event_time,
           CASE WHEN candidate_upload_time IS NULL AND order_cancel_time IS NULL THEN 'missing'
                WHEN candidate_upload_time = order_cancel_time THEN 'tie'
                WHEN candidate_upload_time IS NULL OR order_cancel_time < candidate_upload_time
                     THEN 'order_cancellation'
                ELSE candidate_upload_source END AS event_time_source
    FROM candidates
)
SELECT CURRENT_TIMESTAMP::VARCHAR AS extracted_at_session_time,
       CURRENT_WAREHOUSE() AS extraction_warehouse,
       a.* REPLACE(TO_CHAR(rx_creation_datetime, 'YYYY-MM-DD HH24:MI:SS.FF9') AS rx_creation_datetime,
                   TO_CHAR(association_upload_time, 'YYYY-MM-DD HH24:MI:SS.FF9') AS association_upload_time,
                   TO_CHAR(association_upload_created_time, 'YYYY-MM-DD HH24:MI:SS.FF9') AS association_upload_created_time),
       e.* REPLACE(
           TO_CHAR(line_created_utc, 'YYYY-MM-DD HH24:MI:SS.FF9') AS line_created_utc,
           TO_CHAR(line_created_eastern, 'YYYY-MM-DD HH24:MI:SS.FF9') AS line_created_eastern,
           TO_CHAR(order_placed_utc, 'YYYY-MM-DD HH24:MI:SS.FF9') AS order_placed_utc,
           TO_CHAR(order_placed_eastern, 'YYYY-MM-DD HH24:MI:SS.FF9') AS order_placed_eastern,
           TO_CHAR(order_cancel_time, 'YYYY-MM-DD HH24:MI:SS.FF9') AS order_cancel_time,
           TO_CHAR(min_approved_denied_datetime, 'YYYY-MM-DD HH24:MI:SS.FF9') AS min_approved_denied_datetime,
           TO_CHAR(actual_upload_time, 'YYYY-MM-DD HH24:MI:SS.FF9') AS actual_upload_time,
           TO_CHAR(actual_upload_created_time, 'YYYY-MM-DD HH24:MI:SS.FF9') AS actual_upload_created_time,
           TO_CHAR(estimated_upload_time, 'YYYY-MM-DD HH24:MI:SS.FF9') AS estimated_upload_time,
           TO_CHAR(candidate_upload_time, 'YYYY-MM-DD HH24:MI:SS.FF9') AS candidate_upload_time,
           TO_CHAR(event_time, 'YYYY-MM-DD HH24:MI:SS.FF9') AS event_time),
       DATEDIFF(nanosecond, e.order_placed_utc, e.event_time) / 3600000000000::DOUBLE AS elapsed_hours,
       e.order_placed_utc IS NULL AS missing_placement,
       e.event_time IS NULL AS missing_event,
       e.estimated_upload_time IS NULL AS missing_estimate,
       e.event_time < e.order_placed_utc AS negative_duration,
       e.min_approved_denied_datetime < e.order_placed_utc AS negative_approval_interval,
       audit.*
FROM associations a
LEFT JOIN events e ON a.first_order_id = e.order_id AND a.first_order_line_id = e.order_line_id
CROSS JOIN audit

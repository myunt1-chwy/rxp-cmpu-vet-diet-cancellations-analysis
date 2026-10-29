-- Approval-time analyses for the aged-order study.
-- Run each semicolon-delimited WITH ... SELECT statement independently.
-- Cohort: CMPU vet-diet CUSTOMER_UPLOAD prescriptions created in UTC
-- [2026-08-15, 2026-10-15), linked on BOTH first-order ID and numeric item ID.
-- Aged Order cancellations are observed through 2026-10-27 00:00 UTC inclusive.
-- This cutoff applies to cancellations; approval timestamps are not date-filtered.
-- Shipment rows collapse to distinct order/order-line pairs before association.
-- Prior validation found one RX per line, no reason/cancellation/creation conflicts,
-- and at most one populated MIN_APPROVED_DENIED_DATETIME per line.
-- Counts are a current snapshot and may change with later source updates.
-- MIN_APPROVED_DENIED_DATETIME is not evidence of an approval by itself.
-- Sections 1a/1b reproduce in SQL the duration tables originally calculated in
-- Python from validated frozen Parquet exports; percentile interpolation is linear.
-- Sections 2/3 are the exact SQL run for the two approval checks on 2026-10-28.

-- 1a. Creation to MIN_APPROVED_DENIED_DATETIME: duration summary (hours).
-- Divide hours by 24 for the reported day values.
-- Prior result: 26,442 timed lines; 1 missing decision; 0 negatives/zeros.
WITH prescriptions AS (
    SELECT rx_id, customer_id, first_order_id,
           CASE WHEN REGEXP_LIKE(TRIM(first_orderitem_id), '^[0-9]+$')
                THEN TRY_TO_NUMBER(first_orderitem_id) END AS first_order_line_id
    FROM EDLDB.BT_HCA_HCDM.RXP_PRESCRIPTIONS
    WHERE prescription_source = 'CMPU'
      AND is_vet_diet_flag = TRUE
      AND approval_channel = 'CUSTOMER_UPLOAD'
      AND rx_creation_datetime >= '2026-08-15'::TIMESTAMP_NTZ
      AND rx_creation_datetime < '2026-10-15'::TIMESTAMP_NTZ
), lines AS (
    SELECT l.order_id, l.order_line_id,
           MIN(LOWER(TRIM(l.order_cancel_reason))) AS cancel_reason,
           MIN(l.order_cancel_dttm) AS cancel_time,
           MIN(l.order_line_created_dttm) AS line_created_utc,
           MIN(l.min_approved_denied_datetime) AS min_approved_denied_datetime
    FROM EDLDB.BT_HCA_HCDM.ORDER_LINE_COST_MEASURES_RXP l
    JOIN (
        SELECT DISTINCT first_order_id, first_order_line_id FROM prescriptions
        WHERE first_order_id IS NOT NULL AND first_order_line_id IS NOT NULL
    ) p ON l.order_id = p.first_order_id
       AND l.order_line_id = p.first_order_line_id
    GROUP BY l.order_id, l.order_line_id
), aged AS (
    SELECT p.rx_id, p.customer_id, l.*,
           DATEDIFF(nanosecond, l.line_created_utc,
                    l.min_approved_denied_datetime) / 3600000000000.0 AS elapsed_hours
    FROM prescriptions p
    JOIN lines l ON p.first_order_id = l.order_id
                AND p.first_order_line_id = l.order_line_id
    WHERE l.cancel_reason = 'aged order'
      AND l.cancel_time IS NOT NULL
      AND l.cancel_time <= '2026-10-27'::TIMESTAMP_NTZ
)
SELECT COUNT(*) AS cohort_prescriptions,
       COUNT(elapsed_hours) AS timed_order_lines,
       COUNT_IF(line_created_utc IS NULL) AS missing_creation,
       COUNT_IF(min_approved_denied_datetime IS NULL) AS missing_decision,
       COUNT_IF(elapsed_hours < 0) AS negative_durations,
       COUNT_IF(elapsed_hours = 0) AS zero_durations,
       MIN(elapsed_hours) AS minimum_hours,
       PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY elapsed_hours) AS p25_hours,
       MEDIAN(elapsed_hours) AS median_hours,
       PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY elapsed_hours) AS p75_hours,
       PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY elapsed_hours) AS p95_hours,
       MAX(elapsed_hours) AS maximum_hours
FROM aged;

-- 1b. Creation-to-decision duration buckets, retaining missing/negative values.
-- Prior nonmissing bucket counts: 933 / 15,232 / 10,223 / 29 / 25.
WITH prescriptions AS (
    SELECT rx_id, customer_id, first_order_id,
           CASE WHEN REGEXP_LIKE(TRIM(first_orderitem_id), '^[0-9]+$')
                THEN TRY_TO_NUMBER(first_orderitem_id) END AS first_order_line_id
    FROM EDLDB.BT_HCA_HCDM.RXP_PRESCRIPTIONS
    WHERE prescription_source = 'CMPU'
      AND is_vet_diet_flag = TRUE
      AND approval_channel = 'CUSTOMER_UPLOAD'
      AND rx_creation_datetime >= '2026-08-15'::TIMESTAMP_NTZ
      AND rx_creation_datetime < '2026-10-15'::TIMESTAMP_NTZ
), lines AS (
    SELECT l.order_id, l.order_line_id,
           MIN(LOWER(TRIM(l.order_cancel_reason))) AS cancel_reason,
           MIN(l.order_cancel_dttm) AS cancel_time,
           MIN(l.order_line_created_dttm) AS line_created_utc,
           MIN(l.min_approved_denied_datetime) AS min_approved_denied_datetime
    FROM EDLDB.BT_HCA_HCDM.ORDER_LINE_COST_MEASURES_RXP l
    JOIN (
        SELECT DISTINCT first_order_id, first_order_line_id FROM prescriptions
        WHERE first_order_id IS NOT NULL AND first_order_line_id IS NOT NULL
    ) p ON l.order_id = p.first_order_id
       AND l.order_line_id = p.first_order_line_id
    GROUP BY l.order_id, l.order_line_id
), aged AS (
    SELECT p.rx_id, p.customer_id, l.*,
           DATEDIFF(nanosecond, l.line_created_utc,
                    l.min_approved_denied_datetime) / 3600000000000.0 AS elapsed_hours
    FROM prescriptions p
    JOIN lines l ON p.first_order_id = l.order_id
                AND p.first_order_line_id = l.order_line_id
    WHERE l.cancel_reason = 'aged order'
      AND l.cancel_time IS NOT NULL
      AND l.cancel_time <= '2026-10-27'::TIMESTAMP_NTZ
)
SELECT CASE
           WHEN elapsed_hours IS NULL THEN 'Missing duration'
           WHEN elapsed_hours < 0 THEN 'Negative duration'
           WHEN elapsed_hours = 0 THEN 'Zero duration'
           WHEN elapsed_hours <= 240 THEN 'Up to 10 days'
           WHEN elapsed_hours <= 264 THEN 'Over 10 through 11 days'
           WHEN elapsed_hours <= 288 THEN 'Over 11 through 12 days'
           WHEN elapsed_hours <= 312 THEN 'Over 12 through 13 days'
           WHEN elapsed_hours <= 336 THEN 'Over 13 through 14 days'
           ELSE 'Over 14 days'
       END AS elapsed_time_bucket,
       COUNT(*) AS order_lines,
       CASE
           WHEN elapsed_hours IS NULL THEN 9
           WHEN elapsed_hours < 0 THEN 0
           WHEN elapsed_hours = 0 THEN 1
           WHEN elapsed_hours <= 240 THEN 2
           WHEN elapsed_hours <= 264 THEN 3
           WHEN elapsed_hours <= 288 THEN 4
           WHEN elapsed_hours <= 312 THEN 5
           WHEN elapsed_hours <= 336 THEN 6
           ELSE 7
       END AS bucket_order
FROM aged
GROUP BY 1, 3
ORDER BY bucket_order;

-- 2. Separate approval and denial timestamp evidence.
-- Prior result: 6 RX minima populated (all before cancellation), 4 line maxima
-- populated (latest: 3 by cancellation, 1 after); 0 RX denial minima populated.
WITH prescriptions AS
  (SELECT rx_id,
          customer_id,
          first_order_id,
          min_approved_datetime AS rx_first_approval,
          min_denied_datetime AS rx_first_denial,
          first_usage_approved_datetime AS first_usage_approval,
          CASE
              WHEN REGEXP_LIKE(TRIM(first_orderitem_id), '^[0-9]+$') THEN TRY_TO_NUMBER(first_orderitem_id)
          END AS first_order_line_id
   FROM EDLDB.BT_HCA_HCDM.RXP_PRESCRIPTIONS
   WHERE prescription_source='CMPU'
     AND is_vet_diet_flag=TRUE
     AND approval_channel='CUSTOMER_UPLOAD'
     AND rx_creation_datetime >= '2026-08-15'::TIMESTAMP_NTZ
     AND rx_creation_datetime < '2026-10-15'::TIMESTAMP_NTZ),
     lines AS
  (SELECT l.order_id,
          l.order_line_id,
          MIN(LOWER(TRIM(l.order_cancel_reason))) AS cancel_reason,
          COUNT(DISTINCT LOWER(TRIM(l.order_cancel_reason))) + IFF(COUNT_IF(l.order_cancel_reason IS NULL)>0, 1, 0) AS reason_variants,
          MIN(l.order_cancel_dttm) AS cancel_time,
          COUNT(DISTINCT l.order_cancel_dttm) AS cancellation_variants,
          MAX(l.max_approved_datetime) AS line_last_approval,
          MIN(l.min_approved_denied_datetime) AS min_approved_denied_datetime,
          COUNT(DISTINCT l.min_approved_denied_datetime) AS approval_variants
   FROM EDLDB.BT_HCA_HCDM.ORDER_LINE_COST_MEASURES_RXP l
   JOIN
     (SELECT DISTINCT first_order_id,
                      first_order_line_id
      FROM prescriptions
      WHERE first_order_id IS NOT NULL
        AND first_order_line_id IS NOT NULL) p ON l.order_id=p.first_order_id
   AND l.order_line_id=p.first_order_line_id
   GROUP BY l.order_id,
            l.order_line_id),
     aged AS
  (SELECT p.rx_id,
          p.customer_id,
          p.rx_first_approval,
          p.rx_first_denial,
          p.first_usage_approval,
          l.*,
          CASE
              WHEN min_approved_denied_datetime IS NULL THEN 'Missing'
              WHEN min_approved_denied_datetime<cancel_time THEN 'Before cancellation'
              WHEN min_approved_denied_datetime=cancel_time THEN 'At cancellation'
              ELSE 'After cancellation'
          END AS decision_timing
   FROM prescriptions p
   JOIN lines l ON p.first_order_id=l.order_id
   AND p.first_order_line_id=l.order_line_id
   WHERE cancel_reason='aged order'
     AND cancel_time IS NOT NULL
     AND cancel_time<='2026-10-27'::TIMESTAMP_NTZ)
SELECT COUNT(DISTINCT rx_id) AS prescriptions,
       COUNT(DISTINCT order_id, order_line_id) AS order_lines,
       COUNT_IF(line_last_approval IS NOT NULL) AS line_approval_populated,
       COUNT_IF(line_last_approval<=cancel_time) AS line_latest_approval_by_cancellation,
       COUNT_IF(line_last_approval>cancel_time) AS line_latest_approval_after_cancellation,
       COUNT_IF(rx_first_approval IS NOT NULL) AS rx_approval_populated,
       COUNT_IF(rx_first_approval<cancel_time) AS rx_first_approval_before_cancel,
       COUNT_IF(rx_first_approval=cancel_time) AS rx_first_approval_at_cancel,
       COUNT_IF(rx_first_approval>cancel_time) AS rx_first_approval_after_cancel,
       COUNT_IF(rx_first_denial IS NOT NULL) AS rx_denial_populated,
       COUNT_IF(rx_first_approval IS NOT NULL
                AND rx_first_denial IS NOT NULL) AS rx_both_approval_denial,
       COUNT_IF(rx_first_approval IS NULL
                AND rx_first_denial IS NOT NULL) AS rx_denial_only,
       COUNT_IF(rx_first_approval IS NOT NULL
                AND rx_first_denial IS NULL) AS rx_approval_only,
       COUNT_IF(rx_first_approval IS NULL
                AND rx_first_denial IS NULL) AS rx_neither,
       COUNT_IF(first_usage_approval IS NOT NULL) AS first_usage_approval_populated,
       COUNT_IF(line_last_approval IS NOT NULL
                AND rx_first_approval IS NULL) AS line_approval_without_rx_min,
       COUNT_IF(line_last_approval IS NULL
                AND rx_first_approval IS NOT NULL) AS rx_min_without_line_approval,
       COUNT_IF(reason_variants>1
                OR cancellation_variants>1) AS conflicting_cohort_rows
FROM aged;

-- 3. PRESCRIPTION_APPROVED flag distribution and dedicated approval times.
-- Prior result: TRUE = 6, FALSE = 26,437, NULL/conflicting = 0.
WITH prescriptions AS
  (SELECT rx_id,
          customer_id,
          first_order_id,
          CASE
              WHEN REGEXP_LIKE(TRIM(first_orderitem_id), '^[0-9]+$') THEN TRY_TO_NUMBER(first_orderitem_id)
          END AS first_order_line_id
   FROM EDLDB.BT_HCA_HCDM.RXP_PRESCRIPTIONS
   WHERE prescription_source='CMPU'
     AND is_vet_diet_flag=TRUE
     AND approval_channel='CUSTOMER_UPLOAD'
     AND rx_creation_datetime >= '2026-08-15'::TIMESTAMP_NTZ
     AND rx_creation_datetime < '2026-10-15'::TIMESTAMP_NTZ),
     lines AS
  (SELECT l.order_id,
          l.order_line_id,
          MIN(LOWER(TRIM(l.order_cancel_reason))) AS cancel_reason,
          COUNT(DISTINCT LOWER(TRIM(l.order_cancel_reason))) + IFF(COUNT_IF(l.order_cancel_reason IS NULL)>0, 1, 0) AS reason_variants,
          MIN(l.order_cancel_dttm) AS cancel_time,
          COUNT(DISTINCT l.order_cancel_dttm) AS cancellation_variants,
          MIN(l.prescription_approved) AS prescription_approved,
          COUNT(DISTINCT l.prescription_approved)+IFF(COUNT_IF(l.prescription_approved IS NULL)>0, 1, 0) AS flag_variants,
          MIN(l.min_prescription_approved_datetime) AS min_prescription_approved_datetime,
          MAX(l.max_prescription_approved_datetime) AS max_prescription_approved_datetime,
          MAX(l.max_approved_datetime) AS max_approved_datetime,
          MIN(l.min_approved_denied_datetime) AS min_approved_denied_datetime,
          COUNT(DISTINCT l.min_approved_denied_datetime) AS approval_variants
   FROM EDLDB.BT_HCA_HCDM.ORDER_LINE_COST_MEASURES_RXP l
   JOIN
     (SELECT DISTINCT first_order_id,
                      first_order_line_id
      FROM prescriptions
      WHERE first_order_id IS NOT NULL
        AND first_order_line_id IS NOT NULL) p ON l.order_id=p.first_order_id
   AND l.order_line_id=p.first_order_line_id
   GROUP BY l.order_id,
            l.order_line_id),
     aged AS
  (SELECT p.rx_id,
          p.customer_id,
          l.*,
          CASE
              WHEN min_approved_denied_datetime IS NULL THEN 'Missing'
              WHEN min_approved_denied_datetime<cancel_time THEN 'Before cancellation'
              WHEN min_approved_denied_datetime=cancel_time THEN 'At cancellation'
              ELSE 'After cancellation'
          END AS decision_timing
   FROM prescriptions p
   JOIN lines l ON p.first_order_id=l.order_id
   AND p.first_order_line_id=l.order_line_id
   WHERE cancel_reason='aged order'
     AND cancel_time IS NOT NULL
     AND cancel_time<='2026-10-27'::TIMESTAMP_NTZ)
SELECT CASE
           WHEN flag_variants>1 THEN 'Conflicting shipment values'
           WHEN prescription_approved=TRUE THEN 'TRUE'
           WHEN prescription_approved=FALSE THEN 'FALSE'
           ELSE 'NULL'
       END AS prescription_approved_flag,
       COUNT(DISTINCT rx_id) AS prescriptions,
       COUNT(DISTINCT order_id, order_line_id) AS order_lines,
       COUNT(DISTINCT order_id) AS orders,
       COUNT(DISTINCT customer_id) AS customers,
       COUNT_IF(min_prescription_approved_datetime IS NOT NULL) AS min_prescription_approval_populated,
       COUNT_IF(min_prescription_approved_datetime<cancel_time) AS min_prescription_approval_before_cancel,
       COUNT_IF(min_prescription_approved_datetime=cancel_time) AS min_prescription_approval_at_cancel,
       COUNT_IF(min_prescription_approved_datetime>cancel_time) AS min_prescription_approval_after_cancel,
       COUNT_IF(max_prescription_approved_datetime IS NOT NULL) AS max_prescription_approval_populated,
       COUNT_IF(max_approved_datetime IS NOT NULL) AS generic_max_approval_populated,
       COUNT_IF(reason_variants>1
                OR cancellation_variants>1) AS conflicting_cohort_rows
FROM aged
GROUP BY 1
ORDER BY 1;

-- 4. Placement to latest matching upload, for orders with an ACCEPTED latest entity.
-- Exact query executed on 2026-10-28. Same aged cohort and cancellation cutoff.
-- Matching uploads: DIET_PRESCRIPTION, RX_ID/customer match, UTC creation window
-- [2026-08-01, 2026-10-26). Each order contributes its latest matching upload.
-- STATE_NAME is the current entity state; it is not a historical cancellation-time
-- state, and ACCEPTED does not itself establish prescription approval.
-- Duration = upload CREATED_TS_UTC minus ORDER_PLACED_DTTM, both UTC.
-- The result includes all accepted orders and a separate nonnegative subset.
-- Observed: 48 accepted orders, all placement times present/consistent;
-- 1 upload predates placement by approximately 21 seconds.
-- Nonnegative subset: N=47; minimum=0.021673 h; p25=0.628739 h;
-- median=37.035941 h; p75=100.7939215 h; p95=228.034063399 h;
-- maximum=257.745947 h. Current-state results may change on a later run.
WITH prescriptions AS
  (SELECT rx_id,
          customer_id,
          first_order_id,
          min_approved_datetime AS rx_min_approved_datetime,
          CASE
              WHEN REGEXP_LIKE(TRIM(first_orderitem_id), '^[0-9]+$') THEN TRY_TO_NUMBER(first_orderitem_id)
          END AS first_order_line_id
   FROM EDLDB.BT_HCA_HCDM.RXP_PRESCRIPTIONS
   WHERE prescription_source='CMPU'
     AND is_vet_diet_flag=TRUE
     AND approval_channel='CUSTOMER_UPLOAD'
     AND rx_creation_datetime >= '2026-08-15'::TIMESTAMP_NTZ
     AND rx_creation_datetime < '2026-10-15'::TIMESTAMP_NTZ),
     lines AS
  (SELECT l.order_id,
          l.order_line_id,
          MIN(LOWER(TRIM(l.order_cancel_reason))) AS cancel_reason,
          COUNT(DISTINCT LOWER(TRIM(l.order_cancel_reason))) + IFF(COUNT_IF(l.order_cancel_reason IS NULL)>0, 1, 0) AS reason_variants,
          MIN(l.order_cancel_dttm) AS cancel_time,
          COUNT(DISTINCT l.order_cancel_dttm) AS cancellation_variants,
          MIN(l.order_line_created_dttm) AS line_created_utc,
          MIN(l.prescription_approved) AS prescription_approved,
          COUNT(DISTINCT l.prescription_approved)+IFF(COUNT_IF(l.prescription_approved IS NULL)>0, 1, 0) AS flag_variants,
          MIN(l.min_prescription_approved_datetime) AS min_prescription_approved_datetime,
          MAX(l.max_prescription_approved_datetime) AS max_prescription_approved_datetime,
          MAX(l.max_approved_datetime) AS max_approved_datetime,
          MIN(l.min_approved_denied_datetime) AS min_approved_denied_datetime,
          COUNT(DISTINCT l.min_approved_denied_datetime) AS approval_variants
   FROM EDLDB.BT_HCA_HCDM.ORDER_LINE_COST_MEASURES_RXP l
   JOIN
     (SELECT DISTINCT first_order_id,
                      first_order_line_id
      FROM prescriptions
      WHERE first_order_id IS NOT NULL
        AND first_order_line_id IS NOT NULL) p ON l.order_id=p.first_order_id
   AND l.order_line_id=p.first_order_line_id
   GROUP BY l.order_id,
            l.order_line_id),
     aged AS
  (SELECT p.rx_id,
          p.customer_id,
          p.rx_min_approved_datetime,
          l.*,
          CASE
              WHEN min_approved_denied_datetime IS NULL THEN 'Missing'
              WHEN min_approved_denied_datetime<cancel_time THEN 'Before cancellation'
              WHEN min_approved_denied_datetime=cancel_time THEN 'At cancellation'
              ELSE 'After cancellation'
          END AS decision_timing
   FROM prescriptions p
   JOIN lines l ON p.first_order_id=l.order_id
   AND p.first_order_line_id=l.order_line_id
   WHERE cancel_reason='aged order'
     AND cancel_time IS NOT NULL
     AND cancel_time<='2026-10-27'::TIMESTAMP_NTZ),
     upload_source AS
  (SELECT upload_id,
          customer_id AS raw_customer_id,
          rx_id AS rx_ids,
          created_ts_utc,
          COALESCE(NULLIF(TRIM(state_id), ''), '[Missing]') AS state_id,
          COALESCE(NULLIF(TRIM(state_name), ''), '[Missing]') AS state_name,
          has_uploaded_file,
          has_associated_rx,
          is_state_active
   FROM EDLDB.BT_HCA_HCDM.RXP_UPLOAD_ENTITY
   WHERE upload_type='DIET_PRESCRIPTION'
     AND created_ts_utc>='2026-08-01'::TIMESTAMP_NTZ
     AND created_ts_utc<'2026-10-26'::TIMESTAMP_NTZ),
     expanded AS
  (SELECT DISTINCT u.* EXCLUDE(raw_customer_id, rx_ids),
                       CASE
                           WHEN REGEXP_LIKE(TRIM(raw_customer_id), '^[0-9]+$') THEN TRY_TO_NUMBER(raw_customer_id)
                       END AS customer_id,
                       NULLIF(TRIM(t.value::VARCHAR), '') AS rx_id
   FROM upload_source u,
        LATERAL FLATTEN(INPUT=>SPLIT(TRIM(COALESCE(rx_ids, ''), '{}'), ','), OUTER=>TRUE) t),
     matched AS
  (SELECT DISTINCT a.order_id,
                   u.upload_id,
                   u.created_ts_utc,
                   u.state_id,
                   u.state_name,
                   u.has_uploaded_file,
                   u.has_associated_rx,
                   u.is_state_active
   FROM aged a
   JOIN expanded u ON a.rx_id=u.rx_id
   AND a.customer_id=u.customer_id
   WHERE u.customer_id IS NOT NULL
     AND REGEXP_LIKE(u.rx_id, '^[A-Za-z0-9_-]+$')),
     latest_times AS
  (SELECT order_id,
          MAX(created_ts_utc) AS latest_upload
   FROM matched
   GROUP BY order_id),
     latest AS
  (SELECT m.*
   FROM matched m
   JOIN latest_times t ON m.order_id=t.order_id
   AND m.created_ts_utc=t.latest_upload),
     latest_order_states AS
  (SELECT order_id,
          COUNT(DISTINCT upload_id) AS latest_entities,
          CASE
              WHEN COUNT(DISTINCT state_id||' / '||state_name)>1 THEN '[Multiple latest states]'
              ELSE MIN(state_name)
          END AS state_name,
          CASE
              WHEN COUNT(DISTINCT state_id||' / '||state_name)>1 THEN '[Multiple]'
              ELSE MIN(state_id)
          END AS state_id,
          COUNT_IF(has_uploaded_file=TRUE)>0 AS has_uploaded_file,
          COUNT_IF(has_associated_rx=TRUE)>0 AS has_associated_rx,
          COUNT_IF(is_state_active=TRUE)>0 AS is_state_active
   FROM latest
   GROUP BY order_id),
     placed AS
  (SELECT l.order_id,
          MIN(l.order_placed_dttm) AS placed_at,
          COUNT(DISTINCT l.order_placed_dttm)+IFF(COUNT_IF(l.order_placed_dttm IS NULL)>0, 1, 0) AS placed_variants
   FROM EDLDB.BT_HCA_HCDM.ORDER_LINE_COST_MEASURES_RXP l
   JOIN
     (SELECT order_id
      FROM latest_order_states
      WHERE state_name='ACCEPTED') p ON l.order_id=p.order_id
   GROUP BY l.order_id),
     accepted AS
  (SELECT s.order_id,
          t.latest_upload,
          p.placed_at,
          p.placed_variants,
          DATEDIFF(nanosecond, p.placed_at, t.latest_upload)/3600000000000.0 AS hours
   FROM latest_order_states s
   JOIN latest_times t ON s.order_id=t.order_id
   JOIN placed p ON s.order_id=p.order_id
   WHERE s.state_name='ACCEPTED'),
     populations AS
  (SELECT 'All accepted orders' AS population,
          *
   FROM accepted
   UNION ALL SELECT 'Nonnegative durations',
                    *
   FROM accepted
   WHERE hours>=0)
SELECT population,
       COUNT(*) AS orders,
       COUNT(hours) AS valid_times,
       COUNT_IF(hours IS NULL) AS missing_placement,
       COUNT_IF(hours<0) AS negative_durations,
       COUNT_IF(placed_variants>1) AS conflicting_placement_times,
       MIN(hours) AS minimum_hours,
       PERCENTILE_CONT(0.25) WITHIN GROUP (
                                           ORDER BY hours) AS p25_hours,
                                          MEDIAN(hours) AS median_hours,
                                          PERCENTILE_CONT(0.75) WITHIN GROUP (
                                                                              ORDER BY hours) AS p75_hours,
                                                                             PERCENTILE_CONT(0.95) WITHIN GROUP (
                                                                                                                 ORDER BY hours) AS p95_hours,
                                                                                                                MAX(hours) AS maximum_hours,
                                                                                                                COUNT_IF(hours>24) AS above_24_hours
FROM populations
GROUP BY population
ORDER BY population;

-- All available linked orders for CMPU vet-diet prescriptions created Sep 1–15.
-- Deduplicate action history and combine direct first-order and usage links.
WITH prescriptions AS (
    SELECT rx_id, rx_creation_datetime, first_order_id,
           COUNT(*) OVER (PARTITION BY rx_id) AS rx_source_rows
    FROM EDLDB.BT_HCA_HCDM.RXP_PRESCRIPTIONS
    WHERE prescription_source = 'CMPU' AND is_vet_diet_flag = TRUE
      AND rx_creation_datetime >= '2026-09-01'::DATE
      AND rx_creation_datetime < '2026-09-16'::DATE
), raw_links AS (
    SELECT rx_id, first_order_id AS order_id,
           1 AS via_first_order, 0 AS via_usage,
           0 AS invalid_order_id, 0 AS missing_order_id, 0 AS deletion_flagged
    FROM prescriptions WHERE first_order_id IS NOT NULL
    UNION ALL
    SELECT DISTINCT a.rx_id,
           CASE WHEN REGEXP_LIKE(TRIM(a.order_id), '^[0-9]+$')
                THEN TRY_TO_NUMBER(a.order_id) END AS order_id,
           0 AS via_first_order, 1 AS via_usage,
           IFF(NULLIF(TRIM(a.order_id), '') IS NOT NULL
               AND (NOT REGEXP_LIKE(TRIM(a.order_id), '^[0-9]+$')
                    OR TRY_TO_NUMBER(a.order_id) IS NULL), 1, 0) AS invalid_order_id,
           IFF(NULLIF(TRIM(a.order_id), '') IS NULL, 1, 0) AS missing_order_id,
           IFF(COALESCE(a.is_deleted, FALSE) OR COALESCE(a.deleted, FALSE)
               OR COALESCE(a.replication_deleted_flag, FALSE), 1, 0) AS deletion_flagged
    FROM EDLDB.BT_HCA_HCDM.RXP_RX_USAGE_ACTIONS a
    JOIN prescriptions p ON a.rx_id = p.rx_id
), links AS (
    SELECT rx_id, order_id, MAX(via_first_order) AS via_first_order,
           MAX(via_usage) AS via_usage, MAX(invalid_order_id) AS invalid_order_id,
           MAX(missing_order_id) AS missing_order_id,
           MAX(deletion_flagged) AS deletion_flagged
    FROM raw_links GROUP BY rx_id, order_id
), orders AS (
    SELECT o.order_id, COUNT(*) AS order_source_rows,
           MIN(o.order_status) AS order_status,
           MIN(o.order_status_description) AS order_status_description,
           MIN(o.order_cancel_reason) AS order_cancel_reason,
           MIN(o.order_placed_dttm) AS order_placed_at_utc,
           MIN(o.order_placed_dttm_est) AS order_placed_at_eastern,
           MIN(o.order_cancel_dttm) AS cancelled_at_utc,
           MIN(o.order_cancel_dttm_est) AS cancelled_at_eastern
    FROM EDLDB.ECOM.ORDERS o
    JOIN (SELECT DISTINCT order_id FROM links WHERE order_id IS NOT NULL) l
      ON o.order_id = l.order_id
    GROUP BY o.order_id
)
SELECT CURRENT_TIMESTAMP::VARCHAR AS extracted_at_session_time,
       p.*, l.order_id, l.via_first_order, l.via_usage,
       l.invalid_order_id, l.missing_order_id, l.deletion_flagged,
       COALESCE(o.order_source_rows, 0) AS order_source_rows,
       o.order_status, o.order_status_description, o.order_cancel_reason,
       o.order_placed_at_utc, o.order_placed_at_eastern,
       o.cancelled_at_utc, o.cancelled_at_eastern,
       CONVERT_TIMEZONE('UTC', 'America/New_York', o.order_placed_at_utc) AS expected_placed_at_eastern,
       CONVERT_TIMEZONE('UTC', 'America/New_York', o.cancelled_at_utc) AS expected_cancelled_at_eastern
FROM prescriptions p
LEFT JOIN links l ON p.rx_id = l.rx_id
LEFT JOIN orders o ON l.order_id = o.order_id

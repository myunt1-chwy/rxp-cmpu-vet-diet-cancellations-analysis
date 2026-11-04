-- Time from order placed to first diet upload for Sept 2026 CMPU vet diet
-- prescriptions that have both a first order and an upload.
--
-- ORDER_PLACED_DTTM is UTC (ORDER_PLACED_DTTM_EST + 4 h in Sept), matching
-- RXP_UPLOAD_ENTITY.CREATED_TS_UTC.
-- Only the first order and first upload per prescription are considered.
--
-- Upload join notes: see cmpu_vet_diet_upload_match_sept2026.sql.

-- 1. Bucketed distribution
WITH rx AS (
    SELECT rx_id, customer_id, first_order_id
    FROM EDLDB.BT_HCA_HCDM.RXP_PRESCRIPTIONS
    WHERE is_vet_diet_flag
      AND prescription_source = 'CMPU'
      AND rx_creation_datetime >= '2026-09-01'
      AND rx_creation_datetime <  '2026-10-01'
),

up AS (
    SELECT
        TRIM(s.value)                AS rx_id,
        TRY_TO_NUMBER(u.customer_id) AS customer_id,
        MIN(u.created_ts_utc)        AS first_upload_ts
    FROM EDLDB.BT_HCA_HCDM.RXP_UPLOAD_ENTITY u,
         LATERAL SPLIT_TO_TABLE(TRIM(u.rx_id, '{}'), ',') s
    WHERE u.upload_type = 'DIET_PRESCRIPTION'
      AND u.rx_id IS NOT NULL
    GROUP BY 1, 2
),

d AS (
    SELECT
        o.order_status,
        o.order_cancel_reason,
        DATEDIFF(minute, o.order_placed_dttm, up.first_upload_ts) / 60.0 AS hrs
    FROM rx
    JOIN up
      ON up.rx_id = rx.rx_id
     AND up.customer_id = rx.customer_id
    JOIN EDLDB.ECOM.ORDERS o
      ON o.order_id = rx.first_order_id
)

SELECT
    CASE
        WHEN hrs < 0   THEN '0. Before order'
        WHEN hrs < 1   THEN '1. < 1 hr'
        WHEN hrs < 6   THEN '2. 1-6 hrs'
        WHEN hrs < 24  THEN '3. 6-24 hrs'
        WHEN hrs < 48  THEN '4. 1-2 days'
        WHEN hrs < 72  THEN '5. 2-3 days'
        WHEN hrs < 120 THEN '6. 3-5 days'
        WHEN hrs < 168 THEN '7. 5-7 days'
        ELSE '8. 7+ days'
    END                                                     AS bucket,
    COUNT(*)                                                AS orders,
    ROUND(100 * RATIO_TO_REPORT(COUNT(*)) OVER (), 1)       AS pct,
    COUNT_IF(order_status = 'X')                            AS canceled,
    COUNT_IF(order_cancel_reason = 'Aged Order')            AS aged_order,
    COUNT_IF(order_cancel_reason IN ('Customer Initiated Cancellation',
                                     'Customer Request'))   AS customer_cancel
FROM d
GROUP BY 1
ORDER BY 1;

-- 2. Percentiles, overall and by whether the order was canceled
WITH rx AS (
    SELECT rx_id, customer_id, first_order_id
    FROM EDLDB.BT_HCA_HCDM.RXP_PRESCRIPTIONS
    WHERE is_vet_diet_flag
      AND prescription_source = 'CMPU'
      AND rx_creation_datetime >= '2026-09-01'
      AND rx_creation_datetime <  '2026-10-01'
),

up AS (
    SELECT
        TRIM(s.value)                AS rx_id,
        TRY_TO_NUMBER(u.customer_id) AS customer_id,
        MIN(u.created_ts_utc)        AS first_upload_ts
    FROM EDLDB.BT_HCA_HCDM.RXP_UPLOAD_ENTITY u,
         LATERAL SPLIT_TO_TABLE(TRIM(u.rx_id, '{}'), ',') s
    WHERE u.upload_type = 'DIET_PRESCRIPTION'
      AND u.rx_id IS NOT NULL
    GROUP BY 1, 2
),

d AS (
    SELECT
        IFF(o.order_status = 'X', 'Order canceled', 'Order not canceled') AS grp,
        DATEDIFF(minute, o.order_placed_dttm, up.first_upload_ts) / 60.0  AS hrs
    FROM rx
    JOIN up
      ON up.rx_id = rx.rx_id
     AND up.customer_id = rx.customer_id
    JOIN EDLDB.ECOM.ORDERS o
      ON o.order_id = rx.first_order_id
),

d2 AS (
    SELECT grp, hrs FROM d
    UNION ALL
    SELECT 'All', hrs FROM d
)

SELECT
    grp,
    COUNT(*)                                                     AS orders,
    ROUND(PERCENTILE_CONT(0.10) WITHIN GROUP (ORDER BY hrs), 2)  AS p10,
    ROUND(PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY hrs), 2)  AS p25,
    ROUND(PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY hrs), 2)  AS p50,
    ROUND(PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY hrs), 2)  AS p75,
    ROUND(PERCENTILE_CONT(0.90) WITHIN GROUP (ORDER BY hrs), 2)  AS p90,
    ROUND(PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY hrs), 2)  AS p95,
    ROUND(AVG(hrs), 1)                                           AS mean_hrs
FROM d2
GROUP BY 1
ORDER BY 1;

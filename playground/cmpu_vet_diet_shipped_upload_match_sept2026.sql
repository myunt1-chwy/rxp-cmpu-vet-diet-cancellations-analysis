-- Shipped CMPU vet diet prescriptions (Sept 2026) matched to customer diet uploads.
--
-- "Shipped" proxy: FIRST_RX_USAGE_STATUS = 'APPROVED' AND FIRST_ORDER_ID IS NOT NULL.
-- RXP_PRESCRIPTIONS has no shipped flag; this is not validated against
-- fulfillment data.
--
-- Join notes: see cmpu_vet_diet_upload_match_sept2026.sql.

WITH rx AS (
    SELECT
        rx_id,
        customer_id,
        approval_channel,
        rx_creation_datetime,
        min_approved_datetime
    FROM EDLDB.BT_HCA_HCDM.RXP_PRESCRIPTIONS
    WHERE is_vet_diet_flag
      AND prescription_source = 'CMPU'
      AND rx_creation_datetime >= '2026-09-01'
      AND rx_creation_datetime <  '2026-10-01'
      AND first_rx_usage_status = 'APPROVED'
      AND first_order_id IS NOT NULL
),

up_raw AS (
    SELECT
        TRIM(s.value)                 AS rx_id,
        TRY_TO_NUMBER(u.customer_id)  AS customer_id,
        u.created_ts_utc,
        u.client_source,
        u.state_name
    FROM EDLDB.BT_HCA_HCDM.RXP_UPLOAD_ENTITY u,
         LATERAL SPLIT_TO_TABLE(TRIM(u.rx_id, '{}'), ',') s
    WHERE u.upload_type = 'DIET_PRESCRIPTION'
      AND u.rx_id IS NOT NULL
),

up AS (
    SELECT
        rx_id,
        customer_id,
        MIN(created_ts_utc)                                          AS first_upload_ts,
        MAX(IFF(client_source NOT ILIKE 'MEDICINE_CABINET%', 1, 0))  AS vd_flow,
        MAX(IFF(client_source ILIKE 'MEDICINE_CABINET%', 1, 0))      AS med_cabinet_flow,
        MAX(IFF(state_name = 'ACCEPTED', 1, 0))                      AS any_accepted,
        MAX(IFF(state_name = 'REVIEW_REQUIRED', 1, 0))               AS any_review_required,
        MAX(IFF(state_name = 'REJECTED', 1, 0))                      AS any_rejected
    FROM up_raw
    GROUP BY 1, 2
)

SELECT
    COALESCE(rx.approval_channel, '(null)')                              AS approval_channel,
    COUNT(*)                                                             AS shipped_prescriptions,
    COUNT(up.rx_id)                                                      AS with_upload,
    ROUND(100 * COUNT(up.rx_id) / COUNT(*), 1)                           AS pct_with_upload,
    COUNT_IF(up.vd_flow = 1)                                             AS via_checkout_order_flows,
    COUNT_IF(up.med_cabinet_flow = 1)                                    AS via_medicine_cabinet,
    COUNT_IF(up.any_accepted = 1)                                        AS upload_accepted,
    COUNT_IF(up.any_review_required = 1)                                 AS upload_review_required,
    COUNT_IF(up.any_rejected = 1)                                        AS upload_rejected,
    COUNT_IF(up.rx_id IS NULL)                                           AS no_upload,
    MEDIAN(DATEDIFF(hour, up.first_upload_ts, rx.min_approved_datetime)) AS median_hrs_upload_to_approve
FROM rx
LEFT JOIN up
       ON up.rx_id = rx.rx_id
      AND up.customer_id = rx.customer_id
GROUP BY ROLLUP(1)
ORDER BY shipped_prescriptions DESC;

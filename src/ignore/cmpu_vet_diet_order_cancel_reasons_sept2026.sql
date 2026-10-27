-- Cancellation reasons for the first order of Sept 2026 CMPU vet diet prescriptions.
--
-- RXP_PRESCRIPTIONS.FIRST_ORDER_ID -> EDLDB.ECOM.ORDERS.ORDER_ID.
-- Canceled = ORDER_STATUS = 'X'. Aged Order, Customer Initiated Cancellation,
-- and Customer Request are broken out; all other cancel reasons are grouped.
-- Only the first order per prescription is considered.
--
-- Upload join notes: see cmpu_vet_diet_upload_match_sept2026.sql.

WITH rx AS (
    SELECT
        rx_id,
        customer_id,
        approval_channel,
        customer_canceled,
        first_order_id
    FROM EDLDB.BT_HCA_HCDM.RXP_PRESCRIPTIONS
    WHERE is_vet_diet_flag
      AND prescription_source = 'CMPU'
      AND rx_creation_datetime >= '2026-09-01'
      AND rx_creation_datetime <  '2026-10-01'
),

up AS (
    SELECT DISTINCT
        TRIM(s.value)                AS rx_id,
        TRY_TO_NUMBER(u.customer_id) AS customer_id
    FROM EDLDB.BT_HCA_HCDM.RXP_UPLOAD_ENTITY u,
         LATERAL SPLIT_TO_TABLE(TRIM(u.rx_id, '{}'), ',') s
    WHERE u.upload_type = 'DIET_PRESCRIPTION'
      AND u.rx_id IS NOT NULL
),

b AS (
    SELECT
        rx.*,
        (up.rx_id IS NOT NULL) AS had_upload,
        CASE
            WHEN o.order_id IS NULL                                        THEN '6. No first order'
            WHEN o.order_status <> 'X'                                     THEN '5. Order not canceled'
            WHEN o.order_cancel_reason = 'Aged Order'                      THEN '1. Aged Order'
            WHEN o.order_cancel_reason = 'Customer Initiated Cancellation' THEN '2. Customer Initiated Cancellation'
            WHEN o.order_cancel_reason = 'Customer Request'                THEN '3. Customer Request'
            ELSE '4. Other cancel reasons'
        END AS cancel_bucket
    FROM rx
    LEFT JOIN up
           ON up.rx_id = rx.rx_id
          AND up.customer_id = rx.customer_id
    LEFT JOIN EDLDB.ECOM.ORDERS o
           ON o.order_id = rx.first_order_id
)

SELECT
    cancel_bucket,
    COUNT(*)                                                          AS all_rx,
    COUNT_IF(approval_channel = 'CUSTOMER_UPLOAD')                    AS cu_rx,
    COUNT_IF(approval_channel = 'CUSTOMER_UPLOAD' AND had_upload)     AS cu_with_upload,
    COUNT_IF(approval_channel = 'CUSTOMER_UPLOAD' AND NOT had_upload) AS cu_no_upload,
    COUNT_IF(approval_channel <> 'CUSTOMER_UPLOAD')                   AS other_channels,
    COUNT_IF(customer_canceled)                                       AS rx_customer_canceled
FROM b
GROUP BY ROLLUP(1)
ORDER BY 1 NULLS LAST;

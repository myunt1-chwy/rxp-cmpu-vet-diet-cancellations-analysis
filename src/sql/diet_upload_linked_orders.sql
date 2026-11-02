-- Current ECOM order records for numeric order IDs associated with diet uploads.
-- No date, order status, order-item, replication, or study-cohort filters.
WITH ids AS (
    SELECT TRY_TO_NUMBER(TRIM(order_id)) AS order_id
    FROM EDLDB.BT_HCA_HCDM.RXP_UPLOAD_ENTITY
    WHERE associated_resource_type = 'DIET_PRESCRIPTION'
      AND REGEXP_LIKE(TRIM(order_id), '^[0-9]+$')
    UNION
    SELECT TRY_TO_NUMBER(TRIM(context:orderId::VARCHAR))
    FROM EDLDB.RXP_NOTIFICATION_SERVICE.UPLOAD_ENTITY
    WHERE associated_resource_type = 'DIET_PRESCRIPTION'
      AND REGEXP_LIKE(TRIM(context:orderId::VARCHAR), '^[0-9]+$')
)
SELECT CURRENT_TIMESTAMP()::VARCHAR AS extracted_at_session_time,
       o.order_id, o.order_cancel_reason, o.order_status_description
FROM EDLDB.ECOM.ORDERS o
JOIN ids i ON o.order_id = i.order_id

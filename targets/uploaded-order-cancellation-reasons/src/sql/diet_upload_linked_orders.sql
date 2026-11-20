-- Current ECOM order records for numeric order IDs associated with diet
-- uploads.
-- No date, order status, order-item, replication, or study-cohort filters.
WITH ids AS (
    SELECT TRY_TO_NUMBER(TRIM(order_id)) AS order_id
    FROM edldb.bt_hca_hcdm.rxp_upload_entity
    WHERE
        associated_resource_type = 'DIET_PRESCRIPTION'
        AND REGEXP_LIKE(TRIM(order_id), '^[0-9]+$')
    UNION DISTINCT
    SELECT TRY_TO_NUMBER(TRIM(context:orderId::VARCHAR))
    FROM edldb.rxp_notification_service.upload_entity
    WHERE
        associated_resource_type = 'DIET_PRESCRIPTION'
        AND REGEXP_LIKE(TRIM(context:orderId::VARCHAR), '^[0-9]+$')
)

SELECT
    o.order_id,
    o.order_cancel_reason,
    o.order_status_description,
    CURRENT_TIMESTAMP()::VARCHAR AS extracted_at_session_time
FROM edldb.ecom.orders AS o
INNER JOIN ids AS i ON o.order_id = i.order_id

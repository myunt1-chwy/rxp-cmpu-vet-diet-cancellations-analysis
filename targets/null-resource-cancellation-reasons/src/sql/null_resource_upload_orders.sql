-- Order-level source extract for every numeric CONTEXT orderId in the NULL-type
-- population.
-- No date, cancellation-status, upload-type, item-ID, or deleted-record
-- filters.
WITH ids AS (
    SELECT DISTINCT TRY_TO_NUMBER(TRIM(context:orderId::VARCHAR)) AS order_id
    FROM edldb.rxp_notification_service.upload_entity
    WHERE
        associated_resource_type IS NULL
        AND REGEXP_LIKE(TRIM(context:orderId::VARCHAR), '^[0-9]+$')
)

SELECT
    o.order_id,
    o.order_cancel_reason,
    o.order_status,
    o.order_status_description,
    o.order_cancel_dttm::VARCHAR AS order_cancel_dttm,
    CURRENT_TIMESTAMP()::VARCHAR AS extracted_at_session_time
FROM edldb.ecom.orders AS o
INNER JOIN ids AS i ON o.order_id = i.order_id

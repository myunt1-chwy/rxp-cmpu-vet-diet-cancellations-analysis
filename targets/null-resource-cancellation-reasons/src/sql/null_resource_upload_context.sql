-- All available physical uploads with SQL NULL associated_resource_type.
-- JSON null is missing, not the literal string 'null'; preserve blank strings.
SELECT
    upload_id,
    replication_deleted_flag,
    created_at::VARCHAR AS upload_created_at,
    CURRENT_TIMESTAMP()::VARCHAR AS extracted_at_session_time,
    TYPEOF(context) AS context_type,
    TYPEOF(context:orderId) AS order_id_value_type,
    TYPEOF(context:orderItemId) AS order_item_id_value_type,
    IFF(IS_NULL_VALUE(context:orderId), NULL, context:orderId::VARCHAR)
        AS context_order_id,
    IFF(
        IS_NULL_VALUE(context:orderItemId), NULL, context:orderItemId::VARCHAR
    ) AS context_order_item_id
FROM edldb.rxp_notification_service.upload_entity
WHERE associated_resource_type IS NULL

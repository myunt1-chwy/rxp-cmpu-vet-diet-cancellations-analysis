-- All DIET_PRESCRIPTION physical source rows; keep missing order IDs for
-- coverage.
SELECT
    CURRENT_TIMESTAMP()::VARCHAR AS extracted_at_session_time,
    'EDLDB.BT_HCA_HCDM.rxp_upload_entity' AS source_table,
    upload_id,
    order_id AS order_id_text
FROM edldb.bt_hca_hcdm.rxp_upload_entity
WHERE associated_resource_type = 'DIET_PRESCRIPTION'
UNION ALL
SELECT
    CURRENT_TIMESTAMP()::VARCHAR AS extracted_at_session_time,
    'EDLDB.rxp_notification_service.upload_entity' AS source_table,
    upload_id,
    IFF(IS_NULL_VALUE(context:orderId), NULL, context:orderId::VARCHAR)
        AS order_id_text
FROM edldb.rxp_notification_service.upload_entity
WHERE associated_resource_type = 'DIET_PRESCRIPTION'

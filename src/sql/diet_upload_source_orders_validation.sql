-- Independent warehouse aggregation, preserving distinct-order and upload grains.
WITH raw AS (
    SELECT 'EDLDB.BT_HCA_HCDM.rxp_upload_entity' AS source_table,
           order_id AS order_id_text
    FROM EDLDB.BT_HCA_HCDM.RXP_UPLOAD_ENTITY
    WHERE associated_resource_type = 'DIET_PRESCRIPTION'
    UNION ALL
    SELECT 'EDLDB.rxp_notification_service.upload_entity',
           IFF(IS_NULL_VALUE(context:orderId), NULL, context:orderId::VARCHAR)
    FROM EDLDB.RXP_NOTIFICATION_SERVICE.UPLOAD_ENTITY
    WHERE associated_resource_type = 'DIET_PRESCRIPTION'
), coverage AS (
    SELECT source_table, COUNT(*) AS diet_uploads,
           COUNT_IF(order_id_text IS NOT NULL) AS uploads_with_order_id
    FROM raw GROUP BY source_table
), ids AS (
    SELECT source_table, TRY_TO_NUMBER(TRIM(order_id_text)) AS order_id,
           COUNT(*) AS upload_entries
    FROM raw
    WHERE REGEXP_LIKE(TRIM(order_id_text), '^[0-9]+$')
    GROUP BY source_table, TRY_TO_NUMBER(TRIM(order_id_text))
)
SELECT i.source_table, c.diet_uploads, c.uploads_with_order_id,
       o.order_id IS NOT NULL AS matched,
       o.order_cancel_reason,
       COUNT(*) AS distinct_orders, SUM(i.upload_entries) AS upload_entries,
       COUNT_IF(o.order_status_description = 'Canceled') AS canceled_orders,
       COUNT_IF(o.order_status_description = 'Canceled' AND o.order_cancel_reason IS NULL) AS canceled_with_null_reason
FROM ids i
LEFT JOIN EDLDB.ECOM.ORDERS o ON o.order_id = i.order_id
JOIN coverage c ON i.source_table = c.source_table
GROUP BY i.source_table, c.diet_uploads, c.uploads_with_order_id,
         o.order_id IS NOT NULL, o.order_cancel_reason

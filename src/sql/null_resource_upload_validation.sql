-- Independent warehouse aggregation of the identifier and order/reason counts.
WITH uploads AS (
    SELECT upload_id,
           IFF(IS_NULL_VALUE(context:orderId), NULL, context:orderId::VARCHAR) AS order_id_text,
           IFF(IS_NULL_VALUE(context:orderItemId), NULL, context:orderItemId::VARCHAR) AS item_id_text
    FROM EDLDB.RXP_NOTIFICATION_SERVICE.UPLOAD_ENTITY
    WHERE associated_resource_type IS NULL
), ids AS (
    SELECT upload_id, TRY_TO_NUMBER(TRIM(order_id_text)) AS order_id
    FROM uploads
    WHERE REGEXP_LIKE(TRIM(order_id_text), '^[0-9]+$')
)
SELECT (SELECT COUNT(*) FROM uploads) AS null_type_uploads,
       (SELECT COUNT_IF(order_id_text IS NOT NULL) FROM uploads) AS order_id_present,
       (SELECT COUNT_IF(item_id_text IS NOT NULL) FROM uploads) AS item_id_present,
       (SELECT COUNT_IF(order_id_text IS NOT NULL AND item_id_text IS NOT NULL) FROM uploads) AS both_ids_present,
       o.order_status_description,
       o.order_cancel_reason,
       o.order_id IS NOT NULL AS matched,
       COUNT(*) AS upload_entries,
       COUNT(DISTINCT i.order_id) AS distinct_orders
FROM ids i
LEFT JOIN EDLDB.ECOM.ORDERS o ON o.order_id = i.order_id
GROUP BY o.order_status_description, o.order_cancel_reason, o.order_id IS NOT NULL

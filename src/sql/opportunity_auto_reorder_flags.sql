-- Enrich only frozen successful reorder lines; preserve missing ECOM matches.
WITH requested AS (
    {{ requested_keys }}
)

SELECT DISTINCT
    r.order_id AS reorder_order_id,
    r.order_line_id AS reorder_line_id,
    e.customer_id AS ecom_customer_id,
    e.order_line_auto_reorder_flag AS auto_reorder_flag,
    CASE WHEN e.order_line_id IS NULL THEN 0 ELSE 1 END AS ecom_matched
FROM requested AS r
LEFT JOIN edldb.ecom.order_line AS e
    ON r.order_id = e.order_id AND r.order_line_id = e.order_line_id

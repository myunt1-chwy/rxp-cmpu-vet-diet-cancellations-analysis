-- sqlfluff:dialect:duckdb
SELECT
    request_id,
    original_order_id,
    CAST(order_cancel_time AS TIMESTAMP_NS) AS order_cancel_time,
    CAST(reorder_placed_at_utc AS TIMESTAMP_NS) AS reorder_placed_at_utc
FROM interval_fixture

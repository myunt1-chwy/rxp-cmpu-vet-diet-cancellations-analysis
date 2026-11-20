-- sqlfluff:dialect:duckdb
SELECT
    rx_id,
    CAST(customer_id AS DECIMAL(38, 0)) AS customer_id
FROM request_fixture

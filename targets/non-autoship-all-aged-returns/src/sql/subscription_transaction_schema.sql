SELECT
    column_name,
    data_type
FROM edldb.information_schema.columns
WHERE
    table_schema = 'BT_SHARED_DW'
    AND table_name = 'FCT_SUBSCRIPTION_ORDER_LINE_TRANSACTION'
ORDER BY ordinal_position

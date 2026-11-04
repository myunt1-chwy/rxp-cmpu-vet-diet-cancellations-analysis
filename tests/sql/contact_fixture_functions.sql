-- sqlfluff:dialect:duckdb
CREATE MACRO CONVERT_TIMEZONE(source_zone, target_zone, value) AS
CASE
    WHEN source_zone = target_zone THEN value
    ELSE ERROR('This SQL fixture supports identical source/target zones only')
END;

CREATE MACRO OBJECT_CONSTRUCT_KEEP_NULL(
    k1, v1, k2, v2, k3, v3, k4, v4, k5, v5, k6, v6, k7, v7, k8, v8
) AS STRUCT_PACK(
    order_id := v1,
    leg_id := v2,
    session_id := v3,
    session_channel := v4,
    session_start_dttm_raw := v5,
    contact_at_utc := v6,
    category_wismo_flag := v7,
    handled_flag := v8
);

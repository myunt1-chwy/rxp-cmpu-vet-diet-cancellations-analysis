-- ORDER_PLACED_DTTM is interpreted as UTC, based on its observed offsets
-- from ORDER_PLACED_DTTM_EST. Do not apply a second Eastern-to-UTC shift.
-- The upload cohort is UTC, start inclusive and end exclusive.
WITH uploads AS (
    SELECT
        UPLOAD_ID,
        RX_ID AS RX_IDS,
        ORDER_ID AS RAW_ORDER_ID,
        TRY_TO_NUMBER(ORDER_ID) AS ORDER_ID,
        CREATED_TS_UTC AS UPLOADED_AT_UTC
    FROM EDLDB.BT_HCA_HCDM.RXP_UPLOAD_ENTITY
    WHERE UPLOAD_TYPE = 'DIET_PRESCRIPTION'
      AND ASSOCIATED_RESOURCE_TYPE = 'DIET_PRESCRIPTION'
      AND HAS_ASSOCIATED_RX = TRUE
      AND HAS_UPLOADED_FILE = TRUE
      AND CREATED_TS_UTC >= '{{ start_date }}'::TIMESTAMP_NTZ
      AND CREATED_TS_UTC < '{{ end_date }}'::TIMESTAMP_NTZ
), prescription_uploads AS (
    -- RX_ID contains a brace-delimited list. ASSOCIATED_RX_CNT does not
    -- reliably count its members, so expand and deduplicate IDs explicitly.
    SELECT DISTINCT u.*, NULLIF(TRIM(p.VALUE::VARCHAR), '') AS RX_ID
    FROM uploads u,
         LATERAL FLATTEN(INPUT => SPLIT(TRIM(COALESCE(u.RX_IDS, ''), '{}'), ','), OUTER => TRUE) p
), orders AS (
    SELECT o.ORDER_ID,
           MIN(o.ORDER_PLACED_DTTM) AS ORDER_PLACED_AT_UTC,
           MIN(o.ORDER_CANCEL_REASON) AS ORDER_CANCEL_REASON,
           COUNT(*) AS ORDER_ROWS
    FROM EDLDB.ECOM.ORDERS o
    INNER JOIN (SELECT DISTINCT ORDER_ID FROM uploads WHERE ORDER_ID IS NOT NULL) u
        ON o.ORDER_ID = u.ORDER_ID
    GROUP BY o.ORDER_ID
)
SELECT
    u.UPLOAD_ID,
    u.RX_ID,
    u.ORDER_ID,
    u.UPLOADED_AT_UTC,
    o.ORDER_PLACED_AT_UTC,
    o.ORDER_CANCEL_REASON,
    CASE
        WHEN u.RX_ID IS NULL THEN 'missing_prescription_id'
        WHEN u.RAW_ORDER_ID IS NULL THEN 'missing_order_id'
        WHEN u.ORDER_ID IS NULL THEN 'invalid_order_id'
        WHEN o.ORDER_ID IS NULL THEN 'unmatched_order'
        WHEN o.ORDER_ROWS > 1 THEN 'duplicate_order_rows'
        WHEN o.ORDER_PLACED_AT_UTC IS NULL THEN 'missing_order_timestamp'
        ELSE 'matched'
    END AS ROW_STATUS,
    DATEDIFF('millisecond', o.ORDER_PLACED_AT_UTC, u.UPLOADED_AT_UTC)
        / 3600000.0 AS ELAPSED_HOURS
FROM prescription_uploads u
LEFT JOIN orders o ON u.ORDER_ID = o.ORDER_ID

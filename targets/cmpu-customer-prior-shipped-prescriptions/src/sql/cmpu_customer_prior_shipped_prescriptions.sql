-- REFNUM 38: all cohort customers, before order placement; no
-- cancellation/reorder requirement.
-- All order IDs in the analysed cohort are excluded from prior shipment
-- evidence.
WITH prescriptions AS (
    SELECT
        rx_id,
        customer_id AS rx_customer_id,
        approval_channel,
        first_order_id,
        first_orderitem_id,
        CASE
            WHEN REGEXP_LIKE(TRIM(first_orderitem_id), '^[0-9]+$')
                THEN TRY_TO_NUMBER(first_orderitem_id)
        END AS first_order_line_id,
        TO_CHAR(rx_creation_datetime, 'YYYY-MM-DD HH24:MI:SS.FF9')
            AS rx_creation_datetime,
        COUNT(*) OVER (PARTITION BY rx_id) AS rx_source_rows
    FROM edldb.bt_hca_hcdm.rxp_prescriptions
    WHERE
        prescription_source = 'CMPU' AND is_vet_diet_flag = TRUE
        {% if approval_channel != 'ALL' %}
            AND approval_channel = '{{ approval_channel }}'{% endif %}
        AND rx_creation_datetime >= '{{ start_date }}'::TIMESTAMP_NTZ
        AND rx_creation_datetime < '{{ end_date }}'::TIMESTAMP_NTZ
),

lines_keys AS (
    SELECT DISTINCT
        first_order_id,
        first_order_line_id
    FROM prescriptions
    WHERE first_order_id IS NOT NULL AND first_order_line_id IS NOT NULL
),

lines AS (
    SELECT
        l.order_id,
        l.order_line_id,
        MIN(l.customer_id) AS customer_id,
        COUNT(DISTINCT l.customer_id)
        + IFF(COUNT_IF(l.customer_id IS NULL) > 0, 1, 0) AS customer_variants,
        MIN(l.order_placed_dttm) AS order_placed_time,
        MIN(l.order_placed_dttm_est) AS order_placed_eastern,
        COUNT(DISTINCT l.order_placed_dttm) AS placed_variants,
        COUNT(DISTINCT l.order_placed_dttm_est) AS eastern_variants,
        COUNT(*) AS shipment_rows
    FROM edldb.bt_hca_hcdm.order_line_cost_measures_rxp AS l
    INNER JOIN lines_keys AS p
        ON
            l.order_id = p.first_order_id
            AND l.order_line_id = p.first_order_line_id
    GROUP BY l.order_id, l.order_line_id
),

associations AS (
    SELECT
        p.*,
        l.order_id,
        l.order_line_id,
        l.customer_id,
        l.customer_variants,
        l.placed_variants,
        l.eastern_variants,
        l.shipment_rows,
        TO_CHAR(l.order_placed_time, 'YYYY-MM-DD HH24:MI:SS.FF9'
        ) AS order_placed_time,
        TO_CHAR(l.order_placed_eastern, 'YYYY-MM-DD HH24:MI:SS.FF9'
        ) AS order_placed_eastern
    FROM prescriptions AS p LEFT JOIN lines AS l
        ON
            p.first_order_id = l.order_id
            AND p.first_order_line_id = l.order_line_id
),

customers AS (
    -- Missing any reference can obscure which cohort order was earliest: do not
    -- call it no prior history.
    SELECT
        a.rx_customer_id AS customer_id,
        IFF(COUNT_IF(
            a.order_id IS NULL
            OR a.order_placed_time IS NULL
            OR a.customer_id IS NULL
            OR a.customer_id <> a.rx_customer_id
            OR a.order_placed_time::TIMESTAMP_NTZ
            > '{{ as_of_date }}'::TIMESTAMP_NTZ
        ) > 0,
        NULL, MIN(a.order_placed_time::TIMESTAMP_NTZ)) AS reference_placed_time
    FROM associations AS a
    WHERE a.rx_customer_id IS NOT NULL
    GROUP BY a.rx_customer_id
),

candidate_keys AS (
    -- Candidate discovery is time-bounded; fetch all their shipment rows before
    -- collapsing.
    SELECT DISTINCT
        l.order_id,
        l.order_line_id
    FROM edldb.bt_hca_hcdm.order_line_cost_measures_rxp AS l
    INNER JOIN customers AS c ON l.customer_id = c.customer_id
    WHERE
        l.order_line_shipped_dttm < c.reference_placed_time
        AND l.rx_id IS NOT NULL
        AND NOT EXISTS (
            SELECT 1 FROM prescriptions AS x
            WHERE x.first_order_id = l.order_id
        )
),

historical_lines AS (
    SELECT
        l.order_id,
        l.order_line_id,
        l.rx_id,
        MIN(l.customer_id) AS shipment_customer_id,
        COUNT(DISTINCT l.customer_id)
        + IFF(COUNT_IF(l.customer_id IS NULL) > 0, 1, 0) AS customer_variants,
        MIN(l.order_line_shipped_dttm) AS shipped_at_utc,
        COUNT(*) AS shipment_rows
    FROM edldb.bt_hca_hcdm.order_line_cost_measures_rxp AS l
    INNER JOIN
        candidate_keys AS k
        ON l.order_id = k.order_id AND l.order_line_id = k.order_line_id
    GROUP BY l.order_id, l.order_line_id, l.rx_id
),

historical_prescriptions_keys_2 AS (
    SELECT DISTINCT rx_id FROM historical_lines
    WHERE rx_id IS NOT NULL
),

historical_prescriptions AS (
    SELECT
        r.rx_id,
        MIN(r.customer_id) AS rx_customer_id,
        COUNT(*) AS rx_source_rows,
        ANY_VALUE(r.is_vet_diet_flag) AS is_vet_diet_flag,
        ANY_VALUE(r.prescription_source) AS prescription_source,
        ANY_VALUE(r.merch_class2) AS merch_class2
    FROM edldb.bt_hca_hcdm.rxp_prescriptions AS r
    INNER JOIN
        historical_prescriptions_keys_2 AS h
        ON r.rx_id = h.rx_id
    GROUP BY r.rx_id
),

history AS (
    SELECT
        h.order_id,
        h.order_line_id,
        h.rx_id,
        h.shipment_customer_id,
        h.customer_variants,
        h.shipment_rows,
        r.rx_customer_id,
        r.is_vet_diet_flag,
        r.prescription_source,
        r.merch_class2,
        TO_CHAR(h.shipped_at_utc, 'YYYY-MM-DD HH24:MI:SS.FF9'
        ) AS shipped_at_utc,
        COALESCE(r.rx_source_rows, 0) AS rx_source_rows
    FROM historical_lines AS h
    LEFT JOIN historical_prescriptions AS r ON h.rx_id = r.rx_id
),

records AS (
    SELECT
        'association' AS record_type,
        OBJECT_CONSTRUCT_KEEP_NULL(a.*)::VARCHAR AS payload
    FROM associations AS a
    UNION ALL
    SELECT
        'shipment' AS record_type,
        OBJECT_CONSTRUCT_KEEP_NULL(h.*)::VARCHAR AS payload
    FROM history AS h
)

SELECT
    record_type,
    payload,
    CURRENT_TIMESTAMP::VARCHAR AS extracted_at_session_time,
    CURRENT_WAREHOUSE() AS extraction_warehouse
FROM records

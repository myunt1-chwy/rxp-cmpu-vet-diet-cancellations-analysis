-- Contacts through the observed order endpoint, without creation-relative
-- bounds.
-- CMPU vet-diet CUSTOMER_UPLOAD orders with qualifying shipment/cancellation
-- activity in [start_date,end_date), UTC; reasons are the current snapshot.
WITH registry AS (
    SELECT
        rx_id,
        MIN(customer_id) AS customer_id,
        MIN(is_vet_diet_flag) AS is_vet_diet_flag,
        MIN(approval_channel) AS approval_channel,
        MIN(prescription_source) AS prescription_source,
        GREATEST(
            COUNT(DISTINCT customer_id)
            + IFF(COUNT_IF(customer_id IS NULL) > 0, 1, 0),
            COUNT(DISTINCT is_vet_diet_flag)
            + IFF(COUNT_IF(is_vet_diet_flag IS NULL) > 0, 1, 0),
            COUNT(DISTINCT approval_channel)
            + IFF(COUNT_IF(approval_channel IS NULL) > 0, 1, 0),
            COUNT(DISTINCT prescription_source)
            + IFF(COUNT_IF(prescription_source IS NULL) > 0, 1, 0)
        ) AS registry_variants
    FROM edldb.bt_hca_hcdm.rxp_prescriptions
    GROUP BY rx_id
),

qualified AS (
    SELECT
        l.order_id,
        l.order_line_id,
        l.customer_id,
        l.order_placed_dttm,
        l.order_line_shipped_dttm,
        l.order_cancel_dttm,
        p.registry_variants,
        CASE
            WHEN l.order_cancel_reason IS NULL THEN '[SQL NULL]'
            WHEN TRIM(l.order_cancel_reason) = '' THEN '[Blank]'
            ELSE LOWER(TRIM(l.order_cancel_reason))
        END AS reason_key
    FROM edldb.bt_hca_hcdm.order_line_cost_measures_rxp AS l
    INNER JOIN registry AS p
        ON NULLIF(TRIM(l.rx_id), '') = p.rx_id AND l.customer_id = p.customer_id
    WHERE
        l.is_vet_diet_flag = TRUE AND p.is_vet_diet_flag = TRUE
        AND p.approval_channel = 'CUSTOMER_UPLOAD'
        AND p.prescription_source = 'CMPU'
),

period_pairs AS (
    SELECT DISTINCT
        order_id,
        reason_key
    FROM qualified
    WHERE (
        order_line_shipped_dttm >= '{{ start_date }}'::TIMESTAMP_NTZ
        AND order_line_shipped_dttm < '{{ end_date }}'::TIMESTAMP_NTZ
    )
    OR (
        order_cancel_dttm >= '{{ start_date }}'::TIMESTAMP_NTZ
        AND order_cancel_dttm < '{{ end_date }}'::TIMESTAMP_NTZ
    )
),

order_reasons AS (
    SELECT
        q.order_id,
        q.reason_key,
        MIN(q.customer_id) AS customer_id,
        MIN(q.order_placed_dttm) AS placed_at_utc,
        MAX(q.order_line_shipped_dttm) AS shipped_at_utc,
        MAX(q.order_cancel_dttm) AS cancelled_at_utc,
        GREATEST_IGNORE_NULLS(
            MAX(q.order_line_shipped_dttm), MAX(q.order_cancel_dttm)
        ) AS observed_end_utc,
        COUNT(DISTINCT q.order_line_id) AS qualifying_lines,
        MAX(q.registry_variants) AS registry_variants,
        COUNT(DISTINCT q.customer_id)
        + IFF(COUNT_IF(q.customer_id IS NULL) > 0, 1, 0) AS customer_variants,
        COUNT(DISTINCT q.order_placed_dttm)
        + IFF(COUNT_IF(q.order_placed_dttm IS NULL) > 0, 1, 0)
            AS placement_variants
    FROM qualified AS q
    INNER JOIN
        period_pairs AS k
        ON q.order_id = k.order_id AND q.reason_key = k.reason_key
    GROUP BY q.order_id, q.reason_key
)

SELECT
    o.order_id,
    o.reason_key,
    o.customer_id,
    o.qualifying_lines,
    o.registry_variants,
    o.customer_variants,
    o.placement_variants,
    c.order_id AS contact_order_id,
    c.customer_id AS contact_customer_id,
    c.leg_id,
    c.session_id,
    c.session_channel,
    c.session_ingress_point,
    c.session_initial_direction,
    c.handled_flag,
    TO_CHAR(o.placed_at_utc, 'YYYY-MM-DD HH24:MI:SS.FF9') AS placed_at_utc,
    TO_CHAR(o.shipped_at_utc, 'YYYY-MM-DD HH24:MI:SS.FF9') AS shipped_at_utc,
    TO_CHAR(o.cancelled_at_utc, 'YYYY-MM-DD HH24:MI:SS.FF9'
    ) AS cancelled_at_utc,
    TO_CHAR(o.observed_end_utc, 'YYYY-MM-DD HH24:MI:SS.FF9'
    ) AS observed_end_utc,
    TO_CHAR(c.session_start_dttm, 'YYYY-MM-DD HH24:MI:SS.FF9') AS contact_at_utc
FROM order_reasons AS o LEFT JOIN edldb.bt_customer_care.fct_contacts_brd AS c
    ON
        o.order_id = c.order_id
        AND (
            o.observed_end_utc >= c.session_start_dttm
            OR c.session_start_dttm IS NULL
        )

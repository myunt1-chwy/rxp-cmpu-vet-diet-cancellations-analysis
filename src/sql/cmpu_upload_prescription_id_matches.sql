-- September 1–15 inclusive; preserve the original upload-event filters/grain.
WITH events AS (
    SELECT 1 AS event_present, customer_id AS event_customer_id,
           product_id AS event_product_id, event_id, event_category, event_label,
           event_timestamp,
           NULLIF(NULLIF(TRIM(properties:eventData:prescriptionId::VARCHAR), ''), 'null') AS nested_prescription_id,
           NULLIF(NULLIF(TRIM(properties:prescriptionId::VARCHAR), ''), 'null') AS root_prescription_id
    FROM EDLDB.SEGMENT.SEGMENT_HITS_PRODUCTS_UNION
    WHERE session_date_est >= '2026-09-01'::DATE
      AND session_date_est < '2026-09-16'::DATE
      AND (
          (event_category = 'pet-healthcare' AND event_action = 'click'
           AND event_label = 'auth-file-submit')
          OR (event_category = 'van-damme'
              AND event_label IN ('upload-preview-upload', 'upload-success'))
      )
    QUALIFY ROW_NUMBER() OVER (
        PARTITION BY event_id, product_id ORDER BY event_timestamp
    ) = 1
), identified_events AS (
    SELECT *, COALESCE(nested_prescription_id, root_prescription_id) AS event_prescription_id
    FROM events
), prescriptions AS (
    SELECT 1 AS cohort_present, rx_id, customer_id AS rx_customer_id,
           product_id AS rx_product_id, rx_creation_datetime,
           COUNT(*) OVER (PARTITION BY rx_id) AS rx_source_rows
    FROM EDLDB.BT_HCA_HCDM.RXP_PRESCRIPTIONS
    WHERE prescription_source = 'CMPU' AND is_vet_diet_flag = TRUE
      AND rx_creation_datetime >= '2026-09-01'::DATE
      AND rx_creation_datetime < '2026-09-16'::DATE
)
SELECT e.*, p.*
FROM identified_events e
FULL OUTER JOIN prescriptions p ON e.event_prescription_id = p.rx_id

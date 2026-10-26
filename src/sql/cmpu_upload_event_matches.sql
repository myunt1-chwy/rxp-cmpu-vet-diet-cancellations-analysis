-- Customer/product association only: no event/creation timestamp ordering.
-- Include September 1 through September 15 using an exclusive September 16 end.
WITH date_window AS (
    SELECT '2026-09-01'::DATE AS start_date, '2026-09-16'::DATE AS end_date
), events AS (
    SELECT customer_id, product_id, event_id, event_timestamp
    FROM EDLDB.SEGMENT.SEGMENT_HITS_PRODUCTS_UNION
    WHERE session_date_est >= (SELECT start_date FROM date_window)
      AND session_date_est < (SELECT end_date FROM date_window)
      AND (
          (event_category = 'pet-healthcare' AND event_action = 'click'
           AND event_label = 'auth-file-submit')
          OR (event_category = 'van-damme'
              AND event_label IN ('upload-preview-upload', 'upload-success'))
      )
    QUALIFY ROW_NUMBER() OVER (
        PARTITION BY event_id, product_id ORDER BY event_timestamp
    ) = 1
), event_pairs AS (
    SELECT customer_id, product_id, COUNT(*) AS event_count
    FROM events
    WHERE customer_id IS NOT NULL AND product_id IS NOT NULL
    GROUP BY customer_id, product_id
), prescriptions AS (
    SELECT rx_id, customer_id, product_id
    FROM EDLDB.BT_HCA_HCDM.RXP_PRESCRIPTIONS
    WHERE prescription_source = 'CMPU'
      AND is_vet_diet_flag = TRUE
      AND rx_creation_datetime >= (SELECT start_date FROM date_window)
      AND rx_creation_datetime < (SELECT end_date FROM date_window)
), rx_pairs AS (
    SELECT customer_id, product_id, COUNT(DISTINCT rx_id) AS prescription_count
    FROM prescriptions
    WHERE customer_id IS NOT NULL AND product_id IS NOT NULL
    GROUP BY customer_id, product_id
), summary AS (
    SELECT COUNT(DISTINCT p.rx_id) AS total_prescriptions,
           COUNT(DISTINCT CASE WHEN e.event_count IS NOT NULL THEN p.rx_id END) AS matched_prescriptions,
           COUNT(DISTINCT CASE WHEN e.event_count IS NULL THEN p.rx_id END) AS unmatched_prescriptions,
           COUNT(DISTINCT CASE WHEN p.customer_id IS NULL OR p.product_id IS NULL THEN p.rx_id END) AS prescriptions_missing_keys,
           COUNT(DISTINCT CASE WHEN e.event_count > 1 THEN p.rx_id END) AS prescriptions_with_multiple_events,
           COUNT(*) AS prescription_source_rows,
           COUNT(*) - COUNT(p.rx_id) AS prescription_rows_missing_rx_id,
           COUNT(p.rx_id) - COUNT(DISTINCT p.rx_id) AS duplicate_rx_id_rows
    FROM prescriptions p
    LEFT JOIN event_pairs e
      ON p.customer_id = e.customer_id AND p.product_id = e.product_id
)
SELECT CURRENT_DATE AS execution_date,
       CURRENT_TIMESTAMP::VARCHAR AS extracted_at_session_time,
       (SELECT start_date FROM date_window) AS window_start_date,
       (SELECT end_date FROM date_window) AS window_end_date_exclusive,
       s.*,
       100.0 * matched_prescriptions / NULLIF(total_prescriptions, 0) AS match_percent,
       (SELECT COUNT(*) FROM events) AS deduplicated_events,
       (SELECT COUNT(*) FROM events WHERE customer_id IS NULL OR product_id IS NULL) AS events_missing_keys,
       (SELECT COUNT(*) FROM events WHERE event_id IS NULL) AS events_missing_event_id,
       (SELECT COUNT(*) FROM event_pairs WHERE event_count > 1) AS event_pairs_with_multiple_events,
       (SELECT COUNT(*) FROM rx_pairs WHERE prescription_count > 1) AS rx_pairs_with_multiple_prescriptions,
       (SELECT COUNT(*) FROM rx_pairs r JOIN event_pairs e
        ON r.customer_id = e.customer_id AND r.product_id = e.product_id
        WHERE r.prescription_count > 1) AS matched_pairs_with_multiple_prescriptions
FROM summary s

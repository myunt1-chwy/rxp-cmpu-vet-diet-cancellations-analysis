-- Approval channels for RX_IDs already linked to frozen REFNUM 22 reordered lines.
WITH requested_prescriptions AS (
    SELECT value::VARCHAR AS rx_id
    FROM TABLE(FLATTEN(INPUT => PARSE_JSON('{{ rx_ids_json }}')))
)
SELECT CURRENT_TIMESTAMP::VARCHAR AS extracted_at_session_time,
       CURRENT_WAREHOUSE() AS extraction_warehouse,
       k.rx_id, p.rx_id AS matched_rx_id, p.approval_channel,
       COUNT(p.rx_id) OVER (PARTITION BY k.rx_id) AS prescription_rows
FROM requested_prescriptions k
LEFT JOIN EDLDB.BT_HCA_HCDM.RXP_PRESCRIPTIONS p ON k.rx_id=p.rx_id

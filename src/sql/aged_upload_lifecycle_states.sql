-- Latest available lifecycle state, not the historical state at upload time.
SELECT RX_ID, RX_LIFECYCLE_STATE
FROM EDLDB.BT_HCA_HCDM.RXP_PRESCRIPTIONS
{% if rx_ids %}
WHERE RX_ID IN ({{ rx_ids }})
{% else %}
WHERE FALSE
{% endif %}

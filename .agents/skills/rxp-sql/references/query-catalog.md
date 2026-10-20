# Prescription KPI query catalog

Source: [Pet Health Analytics KPI Catalog](https://chewyinc.atlassian.net/wiki/spaces/PHDS/pages/4322230298/Pet+Health+Analytics+KPI+Catalog), retrieved August 26, 2026. These are legacy-source examples using `PET_HEALTH_ANALYTICS_SANDBOX`; see the data model before adapting them to certified HDE views. Most weekly examples use Eastern Time and exclude the incomplete current week.

## Approval and usage

### Approval rate

Weekly approved non-refill prescriptions divided by approved-or-denied non-refill prescriptions, with an approval method.

```sql
SELECT date_trunc('week', CONVERT_TIMEZONE('America/New_York', FINISHED_RXP))::date AS week,
  count(DISTINCT CASE WHEN IS_REFILL = false AND final_status = 'APPROVED' THEN rx_id END) AS approval_num,
  count(DISTINCT CASE WHEN IS_REFILL = false AND final_status IN ('APPROVED','DENIED') THEN rx_id END) AS approval_denom,
  approval_num / approval_denom AS approval_perc
FROM PET_HEALTH_ANALYTICS_SANDBOX.fct__rx_usage_journey
WHERE date_trunc('week', CONVERT_TIMEZONE('America/New_York', FINISHED_RXP))::date <> date_trunc('week', current_date)::date
  AND approval_method IS NOT NULL AND FINISHED_RXP > current_date - 120
GROUP BY ALL;
```

### Approval-method mix

Weekly share of approved usages by approval method.

```sql
WITH totals AS (
  SELECT date_trunc('week', CONVERT_TIMEZONE('America/New_York', FINISHED_RXP))::date AS week,
    count(DISTINCT usage_id) AS total_usages
  FROM PET_HEALTH_ANALYTICS_SANDBOX.fct__rx_usage_journey
  WHERE date_trunc('week', CONVERT_TIMEZONE('America/New_York', FINISHED_RXP))::date <> date_trunc('week', current_date)::date
    AND approval_method IS NOT NULL AND FINISHED_RXP > current_date - 120 AND final_status = 'APPROVED'
  GROUP BY ALL
)
SELECT date_trunc('week', CONVERT_TIMEZONE('America/New_York', FINISHED_RXP))::date AS week,
  approval_method, count(DISTINCT usage_id) / max(total_usages) AS mix_perc
FROM PET_HEALTH_ANALYTICS_SANDBOX.fct__rx_usage_journey u
LEFT JOIN totals t ON t.week = date_trunc('week', CONVERT_TIMEZONE('America/New_York', FINISHED_RXP))::date
WHERE date_trunc('week', CONVERT_TIMEZONE('America/New_York', FINISHED_RXP))::date <> date_trunc('week', current_date)::date
  AND approval_method IS NOT NULL AND FINISHED_RXP > current_date - 120 AND final_status = 'APPROVED'
GROUP BY ALL;
```

### Vet-approved usage

Non-refill usages that either passed DUR with an eligible status or are approved. Parentheses make the source intent explicit.

```sql
SELECT * FROM PET_HEALTH_ANALYTICS_SANDBOX.fct__rx_usage_journey
WHERE (DUR_FLAG = 1 AND FINAL_STATUS IN ('APPROVED','DENIED','VALIDATED'))
   OR (FINAL_STATUS = 'APPROVED' AND is_refill = false);
```

### Usage count, clinic volume, and cancellations

Weekly distinct usage count; adding `clinic_id` creates clinic volume. The source cancellation query used typographic quotes, normalized below.

```sql
SELECT date_trunc('week', CONVERT_TIMEZONE('America/New_York', FINISHED_RXP))::date AS week,
  count(DISTINCT usage_id) AS total_usages
FROM PET_HEALTH_ANALYTICS_SANDBOX.fct__rx_usage_journey
WHERE date_trunc('week', CONVERT_TIMEZONE('America/New_York', FINISHED_RXP))::date <> date_trunc('week', current_date)::date
  AND FINISHED_RXP > current_date - 120
GROUP BY ALL;
```

```sql
SELECT date_trunc('week', CONVERT_TIMEZONE('America/New_York', FINISHED_RXP))::date AS week,
  clinic_id, count(DISTINCT usage_id) AS total_usages
FROM PET_HEALTH_ANALYTICS_SANDBOX.fct__rx_usage_journey
WHERE date_trunc('week', CONVERT_TIMEZONE('America/New_York', FINISHED_RXP))::date <> date_trunc('week', current_date)::date
  AND FINISHED_RXP > current_date - 120
GROUP BY ALL;
```

```sql
SELECT date_trunc('week', CONVERT_TIMEZONE('America/New_York', FINISHED_RXP))::date AS week,
  count(DISTINCT CASE WHEN final_status = 'CANCELED' THEN usage_id END) AS canceled_usages
FROM PET_HEALTH_ANALYTICS_SANDBOX.fct__rx_usage_journey
WHERE date_trunc('week', CONVERT_TIMEZONE('America/New_York', FINISHED_RXP))::date <> date_trunc('week', current_date)::date
  AND FINISHED_RXP > current_date - 120
GROUP BY ALL;
```

### Prescription dwell and partially approved orders

Active in-window admin dwell rows; and orders with both an approved and a pending usage.

```sql
SELECT id AS usage_id, DAY_OF_ORDER, DAY_BUCKET
FROM PET_HEALTH_ANALYTICS_SANDBOX.fct__pharmacist_admin_dwell_metrics
WHERE IS_ACTIVE = true AND IS_IN_WINDOW = true;
```

```sql
WITH usages AS (
  SELECT order_id, count(DISTINCT usage_id) AS total_usages,
    count(DISTINCT CASE WHEN final_status = 'APPROVED' THEN usage_id END) AS approved_usages,
    count(DISTINCT CASE WHEN final_status NOT IN ('APPROVED','DENIED','CANCELED') THEN usage_id END) AS pending_usages
  FROM PET_HEALTH_ANALYTICS_SANDBOX.fct__rx_usage_journey
  WHERE ORDER_PLACED_DTTM > current_date - 120
  GROUP BY ALL
)
SELECT * FROM usages WHERE approved_usages > 0 AND pending_usages > 0;
```

## Order journey and clinic outcomes

### Click-to-approval and click-to-delivery fields

The source headings appear swapped; validate semantic labels before reporting CTA/CTD metrics.

```sql
SELECT usage_id, ORDER_PLACED_DTTM, BULK_TRACK_DELIVERY_DTTM, CTD, CTD_DAYS
FROM PET_HEALTH_ANALYTICS_SANDBOX.fct__rx_usage_journey
WHERE BULK_TRACK_DELIVERY_DTTM IS NOT NULL;
```

```sql
SELECT usage_id, ORDER_PLACED_DTTM, FINISHED_RXP, CTA, CTA_DAYS
FROM PET_HEALTH_ANALYTICS_SANDBOX.fct__rx_usage_journey
WHERE final_status = 'APPROVED';
```

### Denials by reason

Weekly denial rate by denial reason, excluding approval-related reasons and retaining rates of at least 0.1%.

```sql
WITH totals AS (
  SELECT date_trunc('week', FINISHED_RXP)::date AS week,
    count(DISTINCT CASE WHEN final_status IN ('APPROVED','DENIED') THEN rx_id END) AS prescriptions
  FROM PET_HEALTH_ANALYTICS_SANDBOX.fct__rx_usage_journey
  WHERE date_trunc('week', FINISHED_RXP)::date >= date_trunc('week', current_date - 49)::date
    AND date_trunc('week', FINISHED_RXP)::date <> date_trunc('week', current_date)::date
    AND approval_method IS NOT NULL AND is_refill = false
  GROUP BY ALL
)
SELECT DENIAL_REASON AS wh_id, date_trunc('week', FINISHED_RXP)::date AS week, 'Denials' AS metric,
  count(DISTINCT rx_id) AS num, max(prescriptions) AS denom, count(DISTINCT rx_id) / max(prescriptions) AS val
FROM PET_HEALTH_ANALYTICS_SANDBOX.fct__rx_usage_journey
LEFT JOIN totals ON date_trunc('week', FINISHED_RXP)::date = week
WHERE date_trunc('week', FINISHED_RXP)::date >= date_trunc('week', current_date - 49)::date
  AND date_trunc('week', FINISHED_RXP)::date <> date_trunc('week', current_date)::date
  AND approval_method IS NOT NULL AND is_refill = false AND NOT contains(DENIAL_REASON, 'APPROVED') AND final_status = 'DENIED'
GROUP BY ALL HAVING count(DISTINCT rx_id) / max(prescriptions) >= 0.001;
```

## Task operations

### Charge and throughput

Daily task creation and closure counts by task type.

```sql
SELECT transition_ended_at::date AS date, task_type, count(*) AS tasks_created
FROM pet_health_analytics_sandbox.fct__tasks_lifecycle
WHERE task_created_at >= current_date - 30 AND task_type IS NOT NULL
GROUP BY ALL ORDER BY 1 DESC;
```

```sql
SELECT transition_ended_at::date AS date, task_type, count(*) AS tasks_closed
FROM pet_health_analytics_sandbox.fct__tasks_lifecycle
WHERE current_status = 'CLOSED' AND transition_ended_at >= current_date - 30 AND task_type IS NOT NULL
GROUP BY ALL ORDER BY 1 DESC;
```

### Turns per hour and handle time

Hourly by task type and user; DUR time is capped at five minutes in the source definitions.

```sql
SELECT DATE_TRUNC('HOUR', CONVERT_TIMEZONE('America/New_York', TRANSITION_ENDED_AT)) AS date_hour,
  TASK_TYPE, USER_ID, USER_NAME, count(DISTINCT TASK_ID) AS tasks,
  sum(CASE WHEN DWELL_IN_PROGRESS_TO_CLOSED_MINUTES > 5 AND task_type = 'DUR' THEN 5 ELSE NULLIF(DWELL_IN_PROGRESS_TO_CLOSED_MINUTES,0) END) / 60 AS working_hours,
  count(DISTINCT TASK_ID) / (sum(CASE WHEN DWELL_IN_PROGRESS_TO_CLOSED_MINUTES > 5 AND task_type = 'DUR' THEN 5 ELSE NULLIF(DWELL_IN_PROGRESS_TO_CLOSED_MINUTES,0) END) / 60) AS tph
FROM PET_HEALTH_ANALYTICS_SANDBOX.fct__tasks_lifecycle
WHERE FINAL_STATUS = 'CLOSED' AND USER_ID IS NOT NULL
GROUP BY ALL;
```

```sql
SELECT DATE_TRUNC('HOUR', CONVERT_TIMEZONE('America/New_York', TRANSITION_ENDED_AT)) AS date_hour,
  TASK_TYPE, USER_ID, USER_NAME,
  avg(CASE WHEN NULLIF(DWELL_IN_PROGRESS_TO_CLOSED_MINUTES,0) > 5 AND task_type = 'DUR' THEN 5 ELSE NULLIF(DWELL_IN_PROGRESS_TO_CLOSED_MINUTES,0) END) AS AHT_minutes
FROM PET_HEALTH_ANALYTICS_SANDBOX.fct__tasks_lifecycle
WHERE FINAL_STATUS = 'CLOSED' AND USER_ID IS NOT NULL
GROUP BY ALL;
```

### Queue time, aging tasks, and P95 DE/DUR time

Queue time is task-level cumulative duration. Aging tasks are non-closed tasks in queue for at least six hours. The source P95 query divides duration by 60; validate whether that is minutes-to-hours conversion before reporting.

```sql
SELECT task_id, CUMULATIVE_TIME_SECONDS, CUMULATIVE_TIME_MINUTES
FROM PET_HEALTH_ANALYTICS_SANDBOX.fct__tasks_lifecycle;

SELECT task_id, CUMULATIVE_TIME_MINUTES
FROM PET_HEALTH_ANALYTICS_SANDBOX.fct__tasks_lifecycle
WHERE FINAL_STATUS NOT IN ('CLOSED') AND CUMULATIVE_TIME_MINUTES / 60 >= 6;
```

Use the catalog definition, but request approved source SQL, for failed-fax retry success rate and defect rate: complete SQL was not present in the retrieved page content.

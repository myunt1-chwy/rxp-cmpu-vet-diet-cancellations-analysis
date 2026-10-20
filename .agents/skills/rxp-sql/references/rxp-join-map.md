# RxP core join map

Source: [HDE Schema Architecture 101](https://chewyinc.atlassian.net/wiki/spaces/HDE/pages/3358097890/HDE+Schema+Architecture+101#BT_HCA_HCDM) and the supplied EDL diagram: [edl-rxp-core.svg](../assets/edl-rxp-core.svg).

## Relationship map

| Start table | Join table | Join predicate | Expected relationship | Use and caution |
| --- | --- | --- | --- |
| `BT_HCA_HCDM.CLINICS` | `BT_HCA_HCDM.RXP_PRESCRIPTIONS` | `clinics.clinic_id = rxp_prescriptions.clinic_id` | One clinic to many prescriptions | Use for clinic attributes on prescription analysis. `CLINICS` is one row per clinic. |
| `BT_HCA_HCDM.CLINICS` | `BT_HCA_HCDM.ORDER_LINE_COST_MEASURES_RXP` | `clinics.clinic_id = olcm.clinic_id` | One clinic to many order lines | Use for clinic attributes on order-line analysis; do not count this table as order grain. |
| `BT_HCA_HCDM.RXP_PRESCRIPTIONS` | `BT_HCA_HCDM.ORDER_LINE_COST_MEASURES_RXP` | `rxp.rx_id = olcm.rx_id` | One prescription to one or more order lines/shipments | Start with distinct `rx_id` when returning to prescription grain; an order line can map to multiple shipment rows. |
| `BT_HCA_HCDM.RXP_PRESCRIPTIONS` | `BT_HCA_HCDM.RXP_RX_USAGE_ACTIONS` | `rxp.rx_id = usage_actions.rx_id` | One prescription to many usage actions | Verified from current Snowflake metadata. Aggregate actions before returning to prescription grain. |
| `CHEWYBI.CUSTOMER_PETPROFILES` | `BT_HCA_HCDM.RXP_PRESCRIPTIONS` | `pet_profiles.petprofile_id = prescriptions.pet_id` | Pet profile to prescriptions | User-confirmed join. The profile key is not declared unique in the supplied metadata; check grain before aggregating. |
| `CHEWYBI.CUSTOMER_PETPROFILES` | `BT_HCA_HCDM.RXP_PRESCRIPTIONS` | `pet_profiles.petprofile_customer_id = prescriptions.customer_id` | Customer profile to prescriptions | User-confirmed join. Use for customer-level context and check for duplicate profile rows. |
| `BT_HCA_HCDM.ORDER_LINE_COST_MEASURES_RXP` | `BT_HCA_HCDM.RXP_RX_USAGE_ACTIONS` | `olcm.rx_usage_id = usage_actions.rx_usage_id` | One usage to many actions | Verified common key in current metadata. The diagram labels this edge `ORDER_LINE_ID`, but the current actions view does not expose that column. |
| `BT_HCA_HCDM.ORDER_LINE_COST_MEASURES_RXP` | `BT_HCA_HCDM.RXP_RX_USAGE_ACTIONS` | `olcm.product_part_number = usage_actions.part_number` | Product-level match; potentially many-to-many | User-confirmed field mapping. Use only to align product context, never as the sole join for prescription, usage, or order-line metrics. |
| `PET_HEALTH_ANALYTICS_SANDBOX.FCT__TASKS_LIFECYCLE` | `BT_PET_HEALTH_RX_OPERATIONS.RX_DIM_EMPLOYEES` | `tasks.user_id = CAST(employees.employee_kyrios_id AS VARCHAR)` | Many task rows to one latest employee row | Deduplicate employees to the latest row per Kyrios ID before joining; see [task and employee schemas](task-employee-schemas.md). |

## Join templates

### Prescription with clinic context

```sql
SELECT p.rx_id, p.rx_lifecycle_state, c.name, c.state
FROM bt_hca_hcdm.rxp_prescriptions AS p
JOIN bt_hca_hcdm.clinics AS c
  ON c.clinic_id = p.clinic_id;
```

### Prescription to order-line revenue

```sql
SELECT p.rx_id,
  SUM(olcm.order_line_net_sales) AS net_sales
FROM bt_hca_hcdm.rxp_prescriptions AS p
JOIN bt_hca_hcdm.order_line_cost_measures_rxp AS olcm
  ON olcm.rx_id = p.rx_id
GROUP BY p.rx_id;
```

### Prescription actions at action grain

```sql
SELECT p.rx_id, a.action_id, a.action_name, a.from_state, a.to_state
FROM bt_hca_hcdm.rxp_prescriptions AS p
JOIN bt_hca_hcdm.rxp_rx_usage_actions AS a
  ON a.rx_id = p.rx_id;
```

### Add product context to usage actions

Use the usage key when available; the part-number predicate prevents mismatched product context without turning a product match into the record identity.

```sql
SELECT olcm.rx_usage_id, olcm.product_part_number, a.action_id, a.action_name
FROM bt_hca_hcdm.order_line_cost_measures_rxp AS olcm
JOIN bt_hca_hcdm.rxp_rx_usage_actions AS a
  ON a.rx_usage_id = olcm.rx_usage_id
 AND a.part_number = olcm.product_part_number;
```

## Rules for agents

- Join by `clinic_id` for operational analysis. `clinic_key` is a surrogate dimensional key, not the diagrammed operational join key.
- `ORDER_LINE_COST_MEASURES_RXP` is shipment × order-line grain; it can duplicate `order_line_id` across shipments.
- `RXP_RX_USAGE_ACTIONS` is action grain, so it can duplicate usage and order-line records. Aggregate it before combining it with prescription-level metrics.
- `RXP_RX_USAGE_ACTIONS` exposes `ACTION_ID` at action grain and `RX_USAGE_ID` as the usage-level join key. Use `RX_ID` to relate an action back to its prescription.
- `ORDER_LINE_COST_MEASURES_RXP.product_part_number` corresponds to `RXP_RX_USAGE_ACTIONS.part_number`. A part number identifies product context, not a unique prescription, usage, or order line.
- The source diagram's `ORDER_LINE_ID` edge to actions conflicts with current metadata. Use `RX_USAGE_ID` for that relationship unless a future schema revision reintroduces `ORDER_LINE_ID` on the actions view.
- Join task lifecycle `USER_ID` to employee `EMPLOYEE_KYRIOS_ID`, casting the numeric employee identifier to text. Deduplicate the employee dimension first because it contains reporting snapshots.

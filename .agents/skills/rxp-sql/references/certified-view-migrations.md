# Certified RxP view migrations

Source: [Certified Views in BT_HCA_% Repository](https://chewyinc.atlassian.net/wiki/spaces/HDE/pages/3358097890/HDE+Schema+Architecture+101#Certified-Views-in-BT_HCA_%25-Repository), retrieved August 26, 2026.

Use the `BT_HCA_HCDM` views below for new RxP work. They are curated replacements, not mechanical table-name swaps: review grain and renamed columns before migrating a query.

| Certified view | Legacy source view(s) it replaces | Grain / migration instruction |
| --- | --- | --- |
| `ORDER_LINE_COST_MEASURES_RXP` | `pet_health_medication_order_line_details`, `rx_approval_metrics`, `prescription_usage_measures`, `order_line_cost_measures` | Shipment × order line. An `order_line_id` can have multiple `shipment_key` values; unshipped/canceled lines may lack a shipment. Replace fragmented order-line, approval, and usage logic with this integrated view, then preserve the intended distinct-count grain. |
| `RXP_RX_USAGE_ACTIONS` | `prescription_order_items` | `action_id`. Use for state changes and updates to prescription usages across drug and vet-diet systems. |
| `RXP_PRESCRIPTIONS` | `authorizations_master_final`, `prescriptions` | `rx_id`. Use for the enriched prescription snapshot. Validate renamed fields and lifecycle semantics before replacing a legacy query. |
| `RXP_RX_ACTIONS` | `prescription_life_cycle` | `action_id`. Use for actions performed on the prescription/authorization record itself, rather than usage actions. |
| `CLINICS` | `prescription_providers` | `clinic_id`. `CLINICS` is a consolidated one-row-per-clinic master; its simpler column names and additional lifecycle/program fields are not a one-for-one legacy schema match. |
| `CLINIC_DATAMART_V2` | `clinic_datamart` | Daily expanded grain: `activity_date`, `clinic_id`, `rx_origination_type`, `merch_class2`, `compound_flag`, `is_swap`, `b2b_flag`, and `approval_channel`. Aggregate deliberately to recreate legacy totals. |

## Migration rules

- New queries must use the certified view when the needed metric and grain are available.
- Never replace a legacy table name without checking the certified view's grain, keys, filters, and status definitions.
- `CLINIC_DATAMART_V2` is daily only. Its unsuffixed prescription measures are creation-date metrics; use `*_BY_ACTION_DATE` measures for action-date reporting.
- Preserve legacy SQL as a documented source example when the certified mapping is incomplete or its fields have not been validated.

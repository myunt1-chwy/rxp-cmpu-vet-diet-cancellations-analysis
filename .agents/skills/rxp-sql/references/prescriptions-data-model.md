# Prescription data model

Source: [HDE Schema Architecture 101](https://chewyinc.atlassian.net/wiki/spaces/HDE/pages/3358097890/HDE+Schema+Architecture+101), retrieved August 26, 2026. It identifies the `BT_HCA_*` view layer as the system of record for new Healthcare Analytics work; do not add new dependencies on retiring `CHEWYBI` views.

For diagrammed RxP relationships, read [the core join map](rxp-join-map.md) and its [EDL asset](../assets/edl-rxp-core.svg).

## Certified HCDM views

| View | Primary grain | Use it for |
| --- | --- | --- |
| `BT_HCA_HCDM.RXP_PRESCRIPTIONS` | `rx_id` | Prescription snapshot with product, clinic, vet, customer, and order context. |
| `BT_HCA_HCDM.RXP_RX_USAGE_ACTIONS` | `action_id` | State changes and updates to prescription usages across drug and vet-diet systems. |
| `BT_HCA_HCDM.RXP_RX_ACTIONS` | `action_id` | State changes and updates to prescription/authorization records. |
| `BT_HCA_HCDM.CLINICS` | `clinic_id` | Clinic/practice identity, lifecycle, programs, and contact preferences. |
| `BT_HCA_HCDM.ORDER_LINE_COST_MEASURES_RXP` | `shipment_key × order_line_id` | Enriched RxP order-line and shipment performance. |
| `BT_HCA_HCDM.ORDER_LINE_PET_VET_CLINIC_XREF` | `order_line_id × pet_id × vet_id × clinic_id` | Link order lines to pets, vets, and clinics. |
| `BT_HCA_HCDM.CLINIC_DATAMART_V2` | `activity_date × clinic_id × rx_origination_type × merch_class2 × compound_flag × is_swap × b2b_flag × approval_channel` | Daily clinic performance reporting. |

The complete `RXP_PRESCRIPTIONS` column catalog is in the [prescription schema reference](rxp-prescriptions-schema.md).
The complete `RXP_RX_USAGE_ACTIONS` column catalog is in the
[usage-actions schema reference](rxp-rx-usage-actions-schema.md).

## Pet-profile source

`CHEWYBI.CUSTOMER_PETPROFILES` is a legacy pet-profile source documented in
the [pet-profile schema reference](customer-petprofiles-schema.md). Use
`PETPROFILE_ID = RXP_PRESCRIPTIONS.PET_ID` to connect a pet profile to
prescriptions, or `PETPROFILE_CUSTOMER_ID = RXP_PRESCRIPTIONS.CUSTOMER_ID` for
customer-level context. Neither profile key is declared unique in the supplied
metadata, so validate the requested grain before joining or aggregating.

## Join and grain rules

- Use `clinic_id` for operational joins such as prescriptions to clinics; use `clinic_key` only for dimensional/star-schema joins.
- `CLINICS` has one row per clinic and is not historical. Exclude `test_clinic_flag = FALSE` only when appropriate for the metric.
- `9999-12-31` end dates represent active/ongoing relationships.
- `CLINIC_DATAMART_V2` is daily only. Unsuffixed prescription metrics use prescription creation date; `*_BY_ACTION_DATE` metrics use action date.
- `ORDER_LINE_COST_MEASURES_RXP` is not order grain: one `order_line_id` can have multiple `shipment_key` values, and unshipped/canceled lines can lack a shipment key.

## Product catalog enrichment

Use `EDLDB.PDM.PRODUCT` to enrich a prescription or order-line `part_number` with catalog attributes. Join `source.part_number = product.part_number` to retrieve fields such as `NAME`, `PURCHASE_BRAND`, `MANUFACTURER_NAME`, category classifications, and product flags.

`PRODUCT` is snapshot-based. When a report needs one current product record per part number, select the latest `snapshot_date` (with `last_updated_dttm` as a tie-breaker) before joining, for example with `ROW_NUMBER() OVER (PARTITION BY part_number ORDER BY snapshot_date DESC, last_updated_dttm DESC) = 1`. Use a left join so valid prescription activity is retained when catalog metadata is absent.

## Legacy catalog migration

Read [the certified-view migrations](certified-view-migrations.md) before replacing legacy source tables. The initial KPI examples use `PET_HEALTH_ANALYTICS_SANDBOX.FCT__RX_USAGE_JOURNEY` and `FCT__TASKS_LIFECYCLE`; treat them as source examples, not automatically certified equivalents. Before translating, confirm a documented `BT_HCA_*` replacement has the needed columns and preserves the original grain; otherwise label the result as legacy.

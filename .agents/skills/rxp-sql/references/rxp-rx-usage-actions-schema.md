# `EDLDB.BT_HCA_HCDM.RXP_RX_USAGE_ACTIONS` schema

`RXP_RX_USAGE_ACTIONS` is an action-level view. `ACTION_ID` identifies an
action, while `RX_USAGE_ID` identifies the prescription usage associated with
the action. A single usage can therefore have multiple rows; aggregate action
rows before returning to usage or prescription grain.

The fields below are nullable Snowflake columns from the schema supplied for
REFNUM 1.16.

| Column | Type |
| --- | --- |
| `ACTION_ID` | `VARCHAR(16777216)` |
| `RX_USAGE_ID` | `VARCHAR(16777216)` |
| `ACTION_CREATION_DATETIME` | `TIMESTAMP_TZ(9)` |
| `IS_VET_DIET_FLAG` | `BOOLEAN` |
| `ACTION_SPEC_ID` | `NUMBER(38,0)` |
| `FROM_STATE` | `VARCHAR(16777216)` |
| `TO_STATE` | `VARCHAR(16777216)` |
| `PERSONA` | `VARCHAR(16777216)` |
| `ACTION_NAME` | `VARCHAR(16777216)` |
| `USER_ID` | `VARCHAR(16777216)` |
| `CLIENT_ID` | `VARCHAR(16777216)` |
| `BLOCK_REASONS` | `ARRAY` |
| `CLINIC_ID` | `VARCHAR(16777216)` |
| `CREATION_DATETIME` | `TIMESTAMP_TZ(9)` |
| `CUSTOMER_ID` | `VARCHAR(16777216)` |
| `DELETED` | `BOOLEAN` |
| `DISPENSED_AMOUNT` | `FLOAT` |
| `FULFILLMENT_CENTER` | `VARCHAR(16777216)` |
| `NOTES` | `ARRAY` |
| `ORDER_ID` | `VARCHAR(16777216)` |
| `ORDER_ITEM_AMOUNT` | `FLOAT` |
| `ORDER_ITEM_ID` | `VARCHAR(16777216)` |
| `PART_NUMBER` | `VARCHAR(16777216)` |
| `PET_ID` | `VARCHAR(16777216)` |
| `PHARMACIST_ID` | `VARCHAR(16777216)` |
| `RX_ID` | `VARCHAR(16777216)` |
| `SHIPPING_STATE` | `VARCHAR(16777216)` |
| `STATE_CHANGE_REASON` | `VARCHAR(16777216)` |
| `STATE_CHANGED_DATETIME` | `TIMESTAMP_TZ(9)` |
| `SUBSCRIPTION_ID` | `VARCHAR(16777216)` |
| `UPDATED_DATETIME` | `TIMESTAMP_TZ(9)` |
| `USAGE_CONTEXTS` | `ARRAY` |
| `VET_ID` | `VARCHAR(16777216)` |
| `IS_DELETED` | `BOOLEAN` |
| `ACTION_RESULT` | `VARIANT` |
| `ACTION_REQUEST` | `VARIANT` |
| `REPLICATION_SYNCED` | `TIMESTAMP_TZ(9)` |
| `REPLICATION_DELETED_FLAG` | `BOOLEAN` |

Use `RX_USAGE_ID` to join usage-level records, such as
`BT_HCA_HCDM.ORDER_LINE_COST_MEASURES_RXP`. Use `RX_ID` to join back to
`BT_HCA_HCDM.RXP_PRESCRIPTIONS`. See the [RxP join map](rxp-join-map.md) for
the relationship and aggregation rules.

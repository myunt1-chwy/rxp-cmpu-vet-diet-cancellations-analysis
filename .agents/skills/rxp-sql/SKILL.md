---
name: rxp-sql
description: Run and adapt read-only Snowflake SQL for Chewy prescription, approval, and pharmacy-operations analysis. Use when a request concerns RxP metrics, prescription workflows, clinics, approval outcomes, or the associated HDE views.
---

# RxP SQL

Use this skill for prescription-domain analysis in Snowflake. The skill runs Snowflake SQL through DuckDB using interactive browser SSO; it does not create, update, or delete Snowflake data.

## Workflow

1. Read [the data model](references/prescriptions-data-model.md) before selecting tables or joins.
2. When using `RXP_PRESCRIPTIONS`, read the [prescription schema](references/rxp-prescriptions-schema.md) for its columns and types.
3. When using `RXP_RX_USAGE_ACTIONS`, read [the usage-actions schema](references/rxp-rx-usage-actions-schema.md) for its columns and action-level grain.
4. When using `CHEWYBI.CUSTOMER_PETPROFILES`, read [the pet-profile schema](references/customer-petprofiles-schema.md) and use its documented prescription join keys.
5. For task-lifecycle or employee-role analysis, read [the task and employee schemas](references/task-employee-schemas.md).
6. For a known KPI, read [the query catalog](references/query-catalog.md) and start from its source query.
7. Prefer certified `BT_HCA_*` views for new work. Catalog queries that use `PET_HEALTH_ANALYTICS_SANDBOX` are legacy examples: do not silently translate them when no documented replacement exists.
8. Confirm the requested metric grain, reporting window, time zone, and exclusion rules. State any changes to a catalog query.
9. Run read-only SQL with `scripts/run_snowflake_query.py`; review the returned rows and report the SQL used, result grain, and limitations.

## Execution

Run `uv sync` once at the repository root, then set the required Snowflake settings in `.env` using `.env.example` as the template. The runner uses DuckDB 1.5.3 or newer from the uv environment, DuckDB's Snowflake community extension, and the Snowflake ADBC driver. It launches browser SSO on the first authenticated query.

```bash
uv run python skills/rxp-sql/scripts/run_snowflake_query.py path/to/query.sql
uv run python skills/rxp-sql/scripts/run_snowflake_query.py --query 'SELECT 1'
```

The runner accepts one read-only statement beginning with `SELECT`, `WITH`, `SHOW`, `DESCRIBE`, or `EXPLAIN`. It blocks multiple statements and write/DDL statements; Snowflake roles remain the final authorization boundary.

## References

- Read [the data model](references/prescriptions-data-model.md) for table purpose, grain, approved joins, and migration guidance.
- Read [the prescription schema](references/rxp-prescriptions-schema.md) for the complete `RXP_PRESCRIPTIONS` column catalog.
- Read [the usage-actions schema](references/rxp-rx-usage-actions-schema.md) for the complete `RXP_RX_USAGE_ACTIONS` column catalog and action-level grain.
- Read [the pet-profile schema](references/customer-petprofiles-schema.md) for the complete `CHEWYBI.CUSTOMER_PETPROFILES` column catalog and its joins to `RXP_PRESCRIPTIONS`.
- Read [the task and employee schemas](references/task-employee-schemas.md) for lifecycle fields, employee attributes, and their approved Kyrios-user join.
- Read [the query catalog](references/query-catalog.md) for KPI definitions and source SQL from the Pet Health Analytics KPI Catalog.

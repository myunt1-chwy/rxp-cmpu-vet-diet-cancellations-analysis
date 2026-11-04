---
name: my-sql-code-skill
description: Write, adapt, or review analytical SQL using the user's conventions for database-side computation, self-contained query files, CLI execution, and human code review. Apply when building SQL-backed analyses, including workflows orchestrated with Python or DuckDB.
---

# My SQL Code Skill

Keep as much analytical computation as practical in SQL. Deliver self-contained SQL files that a human can review and run in the target database CLI with minimal changes.

## Computation and inputs

- Derive cohorts, identifiers, matching relationships, filters, deduplication, observation windows, denominators, and aggregations from database source tables in SQL. Keep the logic producing the reported metrics visible in the query.
- Use Python or another host for orchestration, scalar parameter substitution, result export, and presentation. Avoid moving expressible analytical logic into dataframes after extraction. Explain any computation that genuinely cannot reasonably stay in SQL.
- Do not upload identifiers or external data to supply query inputs. This includes JSON arrays of extracted rows, generated VALUES lists of cohort identifiers, staged files, temporary-table uploads, and registered Python dataframes. Derive those inputs from database tables using CTEs, joins, or subqueries instead.
- Apply the same input rule when using DuckDB. A query must not depend on hidden in-memory relations or externally supplied data that make it impossible to run in the target database CLI. DuckDB may orchestrate or inspect returned results without becoming a prerequisite for the database calculation.

## Self-contained query files

- Include the source-to-result analytical logic in the SQL file, including cohort definitions. Do not require a prior application run to generate data-dependent SQL or populate intermediate tables.
- Small scalar parameters such as date ranges, observation cutoffs, and follow-up lengths may be templated. Identify their types and intended values. Provide rendered executable SQL when running or sharing a concrete analysis; substituting those scalars should be sufficient to run it in the target CLI.
- Use the target database's dialect and identify required database/schema context. Cross-database portability is not required; execution must not depend on host-language rewriting of analytical logic.
- If reproducing a frozen result requires unavailable historical database data, explain that limitation rather than injecting saved identifiers or silently changing the cohort.

## Human review and verification

- Use descriptive CTEs and explicit joins so a reviewer can follow source selection, grain changes, eligibility, and final aggregation. Comment non-obvious matching rules, time boundaries, NULL handling, and deduplication choices.
- Keep executable SQL readable. Avoid opaque data payloads, thousands of generated literals, and dynamically assembled fragments that obscure the computation.
- Before delivery, verify that the file contains the reported calculation, all input relations resolve in the database, and running it needs only the documented connection context and scalar substitutions. When execution is authorized and available, reconcile the returned result grain, counts, denominators, and totals with the intended analysis; otherwise state what remains unverified.

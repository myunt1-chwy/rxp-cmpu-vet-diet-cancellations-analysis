# Reproducing the analysis

Run `make setup` to install the project environment and commit hooks. All commands below run from the repository root. Default target builds reuse cached data; `REFRESH=1` explicitly requests refresh where supported.

Checks: `make validate-analysis-structure`, `make validate-analysis-sources`, `make sql-lint`, and `make sql-lint-staged`. SQL formatting is available through `make sql-format SQL_PATH=<file>`. Warehouse queries use Snowflake; local audit templates declare their DuckDB dialect. No lint rules are disabled.

Retained standalone computations: `make opportunity-same-pet-part-auto-reorder CACHED=1`; `make opportunity-reorder-customer-counts` reproduces the retained 42-day order-frequency exports. These command sources and instructions are under their corresponding `targets/<command>/` directories.

## report: CMPU aged-order analysis



### Ownership

Target: `report`. Level: `document`.
Parent: `None`.
Ordered children: `executive-summary`, `next-steps`, `appendix`.


### Reproduction commands

Run from the repository root with the project environment installed:
```sh
make report
make report REPRO=1
make report REFRESH=1
```
Default builds reuse retained source data and rerun the validation and presentation steps. They do not query the warehouse. Missing or stale inputs stop the build; inspect the pipeline log before requesting refresh. REFRESH=1 is explicit and may change results.

The report is a draft by default (FINAL=0). Use `make report FINAL=1` to omit the watermark and opening DRAFT text. REPRO=1 includes the target reproduction instructions. The published copy is `outputs/reports/pdf/phds-cmpu-aged-orders-analysis.pdf`. A graph-wide refresh stops for the frozen-study workflows described below.


### Inputs and dependencies

The child make targets above are actual prerequisites. Parent prose is in `src/latex/body.tex` and may appear before, between and after the ordered children.

Shared dependencies:
- `shared/analysis`
- `shared/artifact-ownership.yaml`
- `shared/paths.py`


### Outputs

Generated content: `targets/report/outputs/latex/content.tex`.
Data and outputs are ignored by Git. `shared/artifact-ownership.yaml` maps historical dataset paths to target-owned locations. Existing legacy paths remain compatibility aliases.


### Review database-derived cohort SQL

`make cohort-sql-review` renders eleven self-contained cohort queries without
warehouse access. `make cohort-sql-check` lints both their templates and rendered
SQL with Snowflake defaults. Inputs are scalar dates/timezone; identifiers come
from database CTEs. See `docs/database-derived-cohorts.org` for cohort definitions,
key-set reconciliation and frozen-snapshot limitations. Cached builds identify
historical replay explicitly; replay does not establish current warehouse totals.


### Python lint and formatting

`make setup` installs Ruff and the repository pre-commit hook. The hook checks staged Python (.py and .pyi) for lint and formatting using the staged pyproject.toml configuration. It preserves both the index and unstaged edits; fix failures locally and stage the corrected files. SQLFluff checks remain enabled.

- `make python-lint` checks Python lint.
- `make python-format` formats Python with a 79-column target.
- `make python-format-check` checks formatting without modifying files.
- `make python-lint-staged` runs both staged Python checks.
- Add `PYTHON_PATH=path/to/file.py` to scope the first three commands.

Ruff's E501 rule checks overlong lines the formatter cannot wrap automatically. Long strings and comments may need manual wrapping; Ruff retains its standard exceptions for URLs, single words and pragma comments. See https://docs.astral.sh/ruff/rules/line-too-long/. Playground, generated, vendored skill and environment files are excluded. Maintained source files have been formatted. Staged files are checked on each commit. SQL formatting changes query fingerprints; retained manifests are not rewritten to pretend the new query was executed.


### Shared Python ownership audit

See `docs/shared-python-audit.org` for the file-by-file review of all original shared/python modules. Analysis entry points now have target owners; shared/python contains reusable libraries and import compatibility only. Run `make validate-analysis-sources` to check this boundary and canonical source dependencies. Existing reproduction commands are preserved.


### SQL line length

SQLFluff explicitly sets `max_line_length = 80` in `.sqlfluff`. The existing `make sql-lint`, `make sql-format` and staged pre-commit checks use this limit for SQL and SQL templates. To work on one file, use `make sql-format SQL_PATH=path/to/query.sql` followed by `make sql-lint SQL_PATH=path/to/query.sql`.


### Source lint cleanup and retained snapshots

Warehouse SQL uses Snowflake. Local audit templates declare DuckDB inline so
its row counting, timestamp and bound-parameter syntax is checked correctly.
SQLFluff checks 80-column SQL, including large queries; no rules are disabled.
Ruff checks 79-column Python. Long report strings preserve their emitted bytes.

The lint cleanup changes SQL and implementation fingerprints. The existing
cached financial baseline therefore stops `make report` before rendering. No
warehouse data has been refreshed and retained manifests have not been relabeled.
See `docs/lint-cleanup-validation.org` for the validation record and outstanding
migration-era tests. A report rebuild needs an explicitly reviewed snapshot
transition or authorized refresh; refreshing historical cohorts may change results.

## executive-summary: Executive summary



### Ownership

Target: `executive-summary`. Level: `section`.
Parent: `report`.
Ordered children: none.


### Reproduction commands

Run from the repository root with the project environment installed:
```sh
make executive-summary
make executive-summary REPRO=1
make executive-summary REFRESH=1
```
Default builds reuse retained source data and rerun the validation and presentation steps. They do not query the warehouse. Missing or stale inputs stop the build; inspect the pipeline log before requesting refresh. REFRESH=1 is explicit and may change results.


### Inputs and dependencies


Shared dependencies:
- `shared/analysis`
- `shared/artifact-ownership.yaml`
- `shared/paths.py`


### Outputs

Generated content: `targets/executive-summary/outputs/latex/content.tex`.
Data and outputs are ignored by Git. `shared/artifact-ownership.yaml` maps historical dataset paths to target-owned locations. Existing legacy paths remain compatibility aliases.

## next-steps: What are the next steps?



### Ownership

Target: `next-steps`. Level: `section`.
Parent: `report`.
Ordered children: none.


### Reproduction commands

Run from the repository root with the project environment installed:
```sh
make next-steps
make next-steps REPRO=1
make next-steps REFRESH=1
```
Default builds reuse retained source data and rerun the validation and presentation steps. They do not query the warehouse. Missing or stale inputs stop the build; inspect the pipeline log before requesting refresh. REFRESH=1 is explicit and may change results.


### Inputs and dependencies


Shared dependencies:
- `shared/analysis`
- `shared/artifact-ownership.yaml`
- `shared/paths.py`


### Outputs

Generated content: `targets/next-steps/outputs/latex/content.tex`.
Data and outputs are ignored by Git. `shared/artifact-ownership.yaml` maps historical dataset paths to target-owned locations. Existing legacy paths remain compatibility aliases.

## appendix: Appendix



### Ownership

Target: `appendix`. Level: `section`.
Parent: `report`.
Ordered children: `financial-impact`, `customer-contact-patterns`, `upload-processing-delays`, `aged-order-risk`, `data-verification`.


### Reproduction commands

Run from the repository root with the project environment installed:
```sh
make appendix
make appendix REPRO=1
make appendix REFRESH=1
```
Default builds reuse retained source data and rerun the validation and presentation steps. They do not query the warehouse. Missing or stale inputs stop the build; inspect the pipeline log before requesting refresh. REFRESH=1 is explicit and may change results.


### Inputs and dependencies

The child make targets above are actual prerequisites. Parent prose is in `src/latex/body.tex` and may appear before, between and after the ordered children.

Shared dependencies:
- `shared/analysis`
- `shared/artifact-ownership.yaml`
- `shared/paths.py`


### Outputs

Generated content: `targets/appendix/outputs/latex/content.tex`.
Data and outputs are ignored by Git. `shared/artifact-ownership.yaml` maps historical dataset paths to target-owned locations. Existing legacy paths remain compatibility aliases.

## financial-impact: What is the financial impact of CMPU aged orders?



### Ownership

Target: `financial-impact`. Level: `subsection`.
Parent: `appendix`.
Ordered children: `estimated-sales-loss`, `same-pet-product-returns`, `same-pet-other-product-returns`, `any-vet-diet-returns`, `any-chewy-returns`.


### Reproduction commands

Run from the repository root with the project environment installed:
```sh
make financial-impact
make financial-impact REPRO=1
make financial-impact REFRESH=1
```
Default builds reuse retained source data and rerun the validation and presentation steps. They do not query the warehouse. Missing or stale inputs stop the build; inspect the pipeline log before requesting refresh. REFRESH=1 is explicit and may change results.


### Inputs and dependencies

The child make targets above are actual prerequisites. Parent prose is in `src/latex/body.tex` and may appear before, between and after the ordered children.

Shared dependencies:
- `shared/analysis`
- `shared/artifact-ownership.yaml`
- `shared/paths.py`


### Outputs

Generated content: `targets/financial-impact/outputs/latex/content.tex`.
Data and outputs are ignored by Git. `shared/artifact-ownership.yaml` maps historical dataset paths to target-owned locations. Existing legacy paths remain compatibility aliases.

## estimated-sales-loss: What is the estimated net sales lost from CMPU aged orders?



### Ownership

Target: `estimated-sales-loss`. Level: `subsubsection`.
Parent: `financial-impact`.
Ordered children: `cancellation-sales-baseline`.


### Reproduction commands

Run from the repository root with the project environment installed:
```sh
make estimated-sales-loss
make estimated-sales-loss REPRO=1
make estimated-sales-loss REFRESH=1
```
Default builds reuse retained source data and rerun the validation and presentation steps. They do not query the warehouse. Missing or stale inputs stop the build; inspect the pipeline log before requesting refresh. REFRESH=1 is explicit and may change results.


### Inputs and dependencies

The child make targets above are actual prerequisites. Parent prose is in `src/latex/body.tex` and may appear before, between and after the ordered children.

Shared dependencies:
- `shared/analysis`
- `shared/artifact-ownership.yaml`
- `shared/paths.py`


### Outputs

Generated content: `targets/estimated-sales-loss/outputs/latex/content.tex`.
Data and outputs are ignored by Git. `shared/artifact-ownership.yaml` maps historical dataset paths to target-owned locations. Existing legacy paths remain compatibility aliases.

## cancellation-sales-baseline: How do customer counts, order counts, and estimated net sales vary by cancellation reason and line-item status?



### Ownership

Target: `cancellation-sales-baseline`. Level: `paragraph`.
Parent: `estimated-sales-loss`.
Ordered children: none.


### Reproduction commands

Run from the repository root with the project environment installed:
```sh
make cancellation-sales-baseline
make cancellation-sales-baseline REPRO=1
make cancellation-sales-baseline REFRESH=1
```
Default builds reuse retained source data and rerun the validation and presentation steps. They do not query the warehouse. Missing or stale inputs stop the build; inspect the pipeline log before requesting refresh. REFRESH=1 is explicit and may change results.


### Inputs and dependencies

Generator batch: `financial-baseline`, defined in `shared/analysis/pipelines.yaml`. The batch is shared by related paragraphs and runs once per make invocation.
Existing generator commands (the batch explicitly sets CACHED=1 by default):
- `make opportunity-order-cancellation-summary WRITE_LATEX=1 DATE_BASIS=shipped-or-cancelled CACHED=1`

Retained input folders and ownership:
- `targets/cancellation-sales-baseline/data/`

Dates and cohort parameters are preserved from the source manifests and the existing generator defaults. Financial/contact defaults use May 1 through July 31, 2026, with follow-up observed through October 28; upload/prescription analyses retain their August 15 through October 14 study and documented upload/cancellation cutoffs. Do not mix source snapshots.
- `targets/cancellation-sales-baseline/src/python/create_opportunity_order_cancellation_summary.py`
- `targets/cancellation-sales-baseline/src/sql/create_opportunity_order_cancellation_summary-query-1.sql.j2`
- `targets/cancellation-sales-baseline/src/sql/opportunity_order_cancellation_summary.sql`

Imported analysis dependencies:
- `shared/python/markdown_tables.py`
- `shared/python/opportunity_report_tables.py`

Shared dependencies:
- `shared/analysis`
- `shared/artifact-ownership.yaml`
- `shared/paths.py`
- `shared/python/__init__.py`
- `shared/python/markdown_tables.py`
- `shared/python/opportunity_report_tables.py`
- `shared/source-ownership.yaml`
- `shared/sql_templates.py`


### Outputs

Generated content: `targets/cancellation-sales-baseline/outputs/latex/content.tex`.
Tables are exported to `outputs/tables/table.org` and read back to assemble LaTeX. The compatibility adapter retains cell formatting from the validated legacy renderer; `outputs/tables/provenance.json` records the source and Org fingerprints. Figures and diagrams are copied from their newly regenerated canonical exports. Logs are under the batch owner's `outputs/build/` folder.
Data and outputs are ignored by Git. `shared/artifact-ownership.yaml` maps historical dataset paths to target-owned locations. Existing legacy paths remain compatibility aliases.

## same-pet-product-returns: What percentage of customers come back and place a successful vet diet order for the same pet and part number after an aged order in the next 70 days?



### Ownership

Target: `same-pet-product-returns`. Level: `subsubsection`.
Parent: `financial-impact`.
Ordered children: `same-pet-product-return-comparison`.


### Reproduction commands

Run from the repository root with the project environment installed:
```sh
make same-pet-product-returns
make same-pet-product-returns REPRO=1
make same-pet-product-returns REFRESH=1
```
Default builds reuse retained source data and rerun the validation and presentation steps. They do not query the warehouse. Missing or stale inputs stop the build; inspect the pipeline log before requesting refresh. REFRESH=1 is explicit and may change results.


### Inputs and dependencies

The child make targets above are actual prerequisites. Parent prose is in `src/latex/body.tex` and may appear before, between and after the ordered children.

Shared dependencies:
- `shared/analysis`
- `shared/artifact-ownership.yaml`
- `shared/paths.py`


### Outputs

Generated content: `targets/same-pet-product-returns/outputs/latex/content.tex`.
Data and outputs are ignored by Git. `shared/artifact-ownership.yaml` maps historical dataset paths to target-owned locations. Existing legacy paths remain compatibility aliases.

## same-pet-product-return-comparison: How do same-pet, same-product return rates and net sales compare across the three customer cohorts over 70 days?



### Ownership

Target: `same-pet-product-return-comparison`. Level: `paragraph`.
Parent: `same-pet-product-returns`.
Ordered children: none.


### Reproduction commands

Run from the repository root with the project environment installed:
```sh
make same-pet-product-return-comparison
make same-pet-product-return-comparison REPRO=1
make same-pet-product-return-comparison REFRESH=1
```
Default builds reuse retained source data and rerun the validation and presentation steps. They do not query the warehouse. Missing or stale inputs stop the build; inspect the pipeline log before requesting refresh. REFRESH=1 is explicit and may change results.


### Inputs and dependencies

Generator batch: `financial-returns`, defined in `shared/analysis/pipelines.yaml`. The batch is shared by related paragraphs and runs once per make invocation.
Existing generator commands (the batch explicitly sets CACHED=1 by default):
- `make opportunity-follow-up-sales CACHED=1`
- `make opportunity-new-upload-customer-follow-up CACHED=1`
- `make opportunity-new-vet-diet-customer-follow-up CACHED=1`
- `make combined-follow-up-table CACHED=1`

Retained input folders and ownership:
- `targets/cancellation-sales-baseline/data/`
- `targets/same-pet-product-return-comparison/data/`
- `targets/any-chewy-return-comparison/data/`

Dates and cohort parameters are preserved from the source manifests and the existing generator defaults. Financial/contact defaults use May 1 through July 31, 2026, with follow-up observed through October 28; upload/prescription analyses retain their August 15 through October 14 study and documented upload/cancellation cutoffs. Do not mix source snapshots.

Shared dependencies:
- `shared/analysis`
- `shared/artifact-ownership.yaml`
- `shared/paths.py`


### Outputs

Generated content: `targets/same-pet-product-return-comparison/outputs/latex/content.tex`.
Tables are exported to `outputs/tables/table.org` and read back to assemble LaTeX. The compatibility adapter retains cell formatting from the validated legacy renderer; `outputs/tables/provenance.json` records the source and Org fingerprints. Figures and diagrams are copied from their newly regenerated canonical exports. Logs are under the batch owner's `outputs/build/` folder.
Data and outputs are ignored by Git. `shared/artifact-ownership.yaml` maps historical dataset paths to target-owned locations. Existing legacy paths remain compatibility aliases.

## same-pet-other-product-returns: What percentage of customers come back and place a successful order for the same pet but different product after an aged order in the next 70 days?



### Ownership

Target: `same-pet-other-product-returns`. Level: `subsubsection`.
Parent: `financial-impact`.
Ordered children: `same-pet-other-product-return-comparison`.


### Reproduction commands

Run from the repository root with the project environment installed:
```sh
make same-pet-other-product-returns
make same-pet-other-product-returns REPRO=1
make same-pet-other-product-returns REFRESH=1
```
Default builds reuse retained source data and rerun the validation and presentation steps. They do not query the warehouse. Missing or stale inputs stop the build; inspect the pipeline log before requesting refresh. REFRESH=1 is explicit and may change results.


### Inputs and dependencies

The child make targets above are actual prerequisites. Parent prose is in `src/latex/body.tex` and may appear before, between and after the ordered children.

Shared dependencies:
- `shared/analysis`
- `shared/artifact-ownership.yaml`
- `shared/paths.py`


### Outputs

Generated content: `targets/same-pet-other-product-returns/outputs/latex/content.tex`.
Data and outputs are ignored by Git. `shared/artifact-ownership.yaml` maps historical dataset paths to target-owned locations. Existing legacy paths remain compatibility aliases.

## same-pet-other-product-return-comparison: How do same-pet, different-product return rates and net sales compare across the three customer cohorts over 70 days?



### Ownership

Target: `same-pet-other-product-return-comparison`. Level: `paragraph`.
Parent: `same-pet-other-product-returns`.
Ordered children: none.


### Reproduction commands

Run from the repository root with the project environment installed:
```sh
make same-pet-other-product-return-comparison
make same-pet-other-product-return-comparison REPRO=1
make same-pet-other-product-return-comparison REFRESH=1
```
Default builds reuse retained source data and rerun the validation and presentation steps. They do not query the warehouse. Missing or stale inputs stop the build; inspect the pipeline log before requesting refresh. REFRESH=1 is explicit and may change results.


### Inputs and dependencies

Generator batch: `financial-returns`, defined in `shared/analysis/pipelines.yaml`. The batch is shared by related paragraphs and runs once per make invocation.
Existing generator commands (the batch explicitly sets CACHED=1 by default):
- `make opportunity-follow-up-sales CACHED=1`
- `make opportunity-new-upload-customer-follow-up CACHED=1`
- `make opportunity-new-vet-diet-customer-follow-up CACHED=1`
- `make combined-follow-up-table CACHED=1`

Retained input folders and ownership:
- `targets/cancellation-sales-baseline/data/`
- `targets/same-pet-product-return-comparison/data/`
- `targets/any-chewy-return-comparison/data/`

Dates and cohort parameters are preserved from the source manifests and the existing generator defaults. Financial/contact defaults use May 1 through July 31, 2026, with follow-up observed through October 28; upload/prescription analyses retain their August 15 through October 14 study and documented upload/cancellation cutoffs. Do not mix source snapshots.

Shared dependencies:
- `shared/analysis`
- `shared/artifact-ownership.yaml`
- `shared/paths.py`


### Outputs

Generated content: `targets/same-pet-other-product-return-comparison/outputs/latex/content.tex`.
Tables are exported to `outputs/tables/table.org` and read back to assemble LaTeX. The compatibility adapter retains cell formatting from the validated legacy renderer; `outputs/tables/provenance.json` records the source and Org fingerprints. Figures and diagrams are copied from their newly regenerated canonical exports. Logs are under the batch owner's `outputs/build/` folder.
Data and outputs are ignored by Git. `shared/artifact-ownership.yaml` maps historical dataset paths to target-owned locations. Existing legacy paths remain compatibility aliases.

## any-vet-diet-returns: What percentage of customers place a successful vet diet order after an aged order in the next 70 days?



### Ownership

Target: `any-vet-diet-returns`. Level: `subsubsection`.
Parent: `financial-impact`.
Ordered children: `any-vet-diet-return-comparison`.


### Reproduction commands

Run from the repository root with the project environment installed:
```sh
make any-vet-diet-returns
make any-vet-diet-returns REPRO=1
make any-vet-diet-returns REFRESH=1
```
Default builds reuse retained source data and rerun the validation and presentation steps. They do not query the warehouse. Missing or stale inputs stop the build; inspect the pipeline log before requesting refresh. REFRESH=1 is explicit and may change results.


### Inputs and dependencies

The child make targets above are actual prerequisites. Parent prose is in `src/latex/body.tex` and may appear before, between and after the ordered children.

Shared dependencies:
- `shared/analysis`
- `shared/artifact-ownership.yaml`
- `shared/paths.py`


### Outputs

Generated content: `targets/any-vet-diet-returns/outputs/latex/content.tex`.
Data and outputs are ignored by Git. `shared/artifact-ownership.yaml` maps historical dataset paths to target-owned locations. Existing legacy paths remain compatibility aliases.

## any-vet-diet-return-comparison: How do successful vet-diet return rates and net sales compare across the three customer cohorts over 70 days?



### Ownership

Target: `any-vet-diet-return-comparison`. Level: `paragraph`.
Parent: `any-vet-diet-returns`.
Ordered children: none.


### Reproduction commands

Run from the repository root with the project environment installed:
```sh
make any-vet-diet-return-comparison
make any-vet-diet-return-comparison REPRO=1
make any-vet-diet-return-comparison REFRESH=1
```
Default builds reuse retained source data and rerun the validation and presentation steps. They do not query the warehouse. Missing or stale inputs stop the build; inspect the pipeline log before requesting refresh. REFRESH=1 is explicit and may change results.


### Inputs and dependencies

Generator batch: `financial-returns`, defined in `shared/analysis/pipelines.yaml`. The batch is shared by related paragraphs and runs once per make invocation.
Existing generator commands (the batch explicitly sets CACHED=1 by default):
- `make opportunity-follow-up-sales CACHED=1`
- `make opportunity-new-upload-customer-follow-up CACHED=1`
- `make opportunity-new-vet-diet-customer-follow-up CACHED=1`
- `make combined-follow-up-table CACHED=1`

Retained input folders and ownership:
- `targets/cancellation-sales-baseline/data/`
- `targets/same-pet-product-return-comparison/data/`
- `targets/any-chewy-return-comparison/data/`

Dates and cohort parameters are preserved from the source manifests and the existing generator defaults. Financial/contact defaults use May 1 through July 31, 2026, with follow-up observed through October 28; upload/prescription analyses retain their August 15 through October 14 study and documented upload/cancellation cutoffs. Do not mix source snapshots.

Shared dependencies:
- `shared/analysis`
- `shared/artifact-ownership.yaml`
- `shared/paths.py`


### Outputs

Generated content: `targets/any-vet-diet-return-comparison/outputs/latex/content.tex`.
Tables are exported to `outputs/tables/table.org` and read back to assemble LaTeX. The compatibility adapter retains cell formatting from the validated legacy renderer; `outputs/tables/provenance.json` records the source and Org fingerprints. Figures and diagrams are copied from their newly regenerated canonical exports. Logs are under the batch owner's `outputs/build/` folder.
Data and outputs are ignored by Git. `shared/artifact-ownership.yaml` maps historical dataset paths to target-owned locations. Existing legacy paths remain compatibility aliases.

## any-chewy-returns: What percentage of customers place a Chewy order successfully in the following 70 days after their aged order?



### Ownership

Target: `any-chewy-returns`. Level: `subsubsection`.
Parent: `financial-impact`.
Ordered children: `any-chewy-return-comparison`.


### Reproduction commands

Run from the repository root with the project environment installed:
```sh
make any-chewy-returns
make any-chewy-returns REPRO=1
make any-chewy-returns REFRESH=1
```
Default builds reuse retained source data and rerun the validation and presentation steps. They do not query the warehouse. Missing or stale inputs stop the build; inspect the pipeline log before requesting refresh. REFRESH=1 is explicit and may change results.


### Inputs and dependencies

The child make targets above are actual prerequisites. Parent prose is in `src/latex/body.tex` and may appear before, between and after the ordered children.

Shared dependencies:
- `shared/analysis`
- `shared/artifact-ownership.yaml`
- `shared/paths.py`


### Outputs

Generated content: `targets/any-chewy-returns/outputs/latex/content.tex`.
Data and outputs are ignored by Git. `shared/artifact-ownership.yaml` maps historical dataset paths to target-owned locations. Existing legacy paths remain compatibility aliases.

## any-chewy-return-comparison: How do successful Chewy return rates and net sales compare across the three customer cohorts over 70 days?



### Ownership

Target: `any-chewy-return-comparison`. Level: `paragraph`.
Parent: `any-chewy-returns`.
Ordered children: none.


### Reproduction commands

Run from the repository root with the project environment installed:
```sh
make any-chewy-return-comparison
make any-chewy-return-comparison REPRO=1
make any-chewy-return-comparison REFRESH=1
```
Default builds reuse retained source data and rerun the validation and presentation steps. They do not query the warehouse. Missing or stale inputs stop the build; inspect the pipeline log before requesting refresh. REFRESH=1 is explicit and may change results.


### Inputs and dependencies

Generator batch: `financial-returns`, defined in `shared/analysis/pipelines.yaml`. The batch is shared by related paragraphs and runs once per make invocation.
Existing generator commands (the batch explicitly sets CACHED=1 by default):
- `make opportunity-follow-up-sales CACHED=1`
- `make opportunity-new-upload-customer-follow-up CACHED=1`
- `make opportunity-new-vet-diet-customer-follow-up CACHED=1`
- `make combined-follow-up-table CACHED=1`

Retained input folders and ownership:
- `targets/cancellation-sales-baseline/data/`
- `targets/same-pet-product-return-comparison/data/`
- `targets/any-chewy-return-comparison/data/`

Dates and cohort parameters are preserved from the source manifests and the existing generator defaults. Financial/contact defaults use May 1 through July 31, 2026, with follow-up observed through October 28; upload/prescription analyses retain their August 15 through October 14 study and documented upload/cancellation cutoffs. Do not mix source snapshots.

Shared dependencies:
- `shared/analysis`
- `shared/artifact-ownership.yaml`
- `shared/paths.py`


### Outputs

Generated content: `targets/any-chewy-return-comparison/outputs/latex/content.tex`.
Tables are exported to `outputs/tables/table.org` and read back to assemble LaTeX. The compatibility adapter retains cell formatting from the validated legacy renderer; `outputs/tables/provenance.json` records the source and Org fingerprints. Figures and diagrams are copied from their newly regenerated canonical exports. Logs are under the batch owner's `outputs/build/` folder.
Data and outputs are ignored by Git. `shared/artifact-ownership.yaml` maps historical dataset paths to target-owned locations. Existing legacy paths remain compatibility aliases.

## customer-contact-patterns: What is the contact pattern of CMPU aged order customers?



### Ownership

Target: `customer-contact-patterns`. Level: `subsection`.
Parent: `appendix`.
Ordered children: `contacts-by-cancellation-reason`, `contact-timing`, `contact-frequency`, `contact-frequency-and-returns`, `contact-proximity-and-returns`.


### Reproduction commands

Run from the repository root with the project environment installed:
```sh
make customer-contact-patterns
make customer-contact-patterns REPRO=1
make customer-contact-patterns REFRESH=1
```
Default builds reuse retained source data and rerun the validation and presentation steps. They do not query the warehouse. Missing or stale inputs stop the build; inspect the pipeline log before requesting refresh. REFRESH=1 is explicit and may change results.


### Inputs and dependencies

The child make targets above are actual prerequisites. Parent prose is in `src/latex/body.tex` and may appear before, between and after the ordered children.

Shared dependencies:
- `shared/analysis`
- `shared/artifact-ownership.yaml`
- `shared/paths.py`


### Outputs

Generated content: `targets/customer-contact-patterns/outputs/latex/content.tex`.
Data and outputs are ignored by Git. `shared/artifact-ownership.yaml` maps historical dataset paths to target-owned locations. Existing legacy paths remain compatibility aliases.

## contacts-by-cancellation-reason: What is the distribution of CMPU customers with APPROVAL CHANNEL = CUSTOMER\_UPLOAD that contacted Chewy by cancellation reason?



### Ownership

Target: `contacts-by-cancellation-reason`. Level: `subsubsection`.
Parent: `customer-contact-patterns`.
Ordered children: `contact-cancellation-distribution`.


### Reproduction commands

Run from the repository root with the project environment installed:
```sh
make contacts-by-cancellation-reason
make contacts-by-cancellation-reason REPRO=1
make contacts-by-cancellation-reason REFRESH=1
```
Default builds reuse retained source data and rerun the validation and presentation steps. They do not query the warehouse. Missing or stale inputs stop the build; inspect the pipeline log before requesting refresh. REFRESH=1 is explicit and may change results.


### Inputs and dependencies

The child make targets above are actual prerequisites. Parent prose is in `src/latex/body.tex` and may appear before, between and after the ordered children.

Shared dependencies:
- `shared/analysis`
- `shared/artifact-ownership.yaml`
- `shared/paths.py`


### Outputs

Generated content: `targets/contacts-by-cancellation-reason/outputs/latex/content.tex`.
Data and outputs are ignored by Git. `shared/artifact-ownership.yaml` maps historical dataset paths to target-owned locations. Existing legacy paths remain compatibility aliases.

## contact-cancellation-distribution: What proportion of customers contacted Chewy for each order cancellation reason?



### Ownership

Target: `contact-cancellation-distribution`. Level: `paragraph`.
Parent: `contacts-by-cancellation-reason`.
Ordered children: none.


### Reproduction commands

Run from the repository root with the project environment installed:
```sh
make contact-cancellation-distribution
make contact-cancellation-distribution REPRO=1
make contact-cancellation-distribution REFRESH=1
```
Default builds reuse retained source data and rerun the validation and presentation steps. They do not query the warehouse. Missing or stale inputs stop the build; inspect the pipeline log before requesting refresh. REFRESH=1 is explicit and may change results.


### Inputs and dependencies

Generator batch: `contact-reasons`, defined in `shared/analysis/pipelines.yaml`. The batch is shared by related paragraphs and runs once per make invocation.
Existing generator commands (the batch explicitly sets CACHED=1 by default):
- `make opportunity-customer-contacts-by-cancel-reason HANDLED_ONLY=0 CACHED=1`

Retained input folders and ownership:
- `targets/cancellation-sales-baseline/data/`
- `targets/contact-cancellation-distribution/data/`

Dates and cohort parameters are preserved from the source manifests and the existing generator defaults. Financial/contact defaults use May 1 through July 31, 2026, with follow-up observed through October 28; upload/prescription analyses retain their August 15 through October 14 study and documented upload/cancellation cutoffs. Do not mix source snapshots.
- `targets/contact-cancellation-distribution/src/python/create_opportunity_contacts_by_cancel_reason.py`
- `targets/contact-cancellation-distribution/src/sql/opportunity_customer_contacts_by_cancel_reason.sql`

Imported analysis dependencies:
- `shared/python/markdown_tables.py`
- `shared/python/opportunity_report_tables.py`
- `targets/cancellation-sales-baseline/src/python/create_opportunity_order_cancellation_summary.py`

Shared dependencies:
- `shared/analysis`
- `shared/artifact-ownership.yaml`
- `shared/paths.py`
- `shared/python/__init__.py`
- `shared/python/markdown_tables.py`
- `shared/python/opportunity_report_tables.py`
- `shared/source-ownership.yaml`
- `shared/sql_templates.py`


### Outputs

Generated content: `targets/contact-cancellation-distribution/outputs/latex/content.tex`.
Tables are exported to `outputs/tables/table.org` and read back to assemble LaTeX. The compatibility adapter retains cell formatting from the validated legacy renderer; `outputs/tables/provenance.json` records the source and Org fingerprints. Figures and diagrams are copied from their newly regenerated canonical exports. Logs are under the batch owner's `outputs/build/` folder.
Data and outputs are ignored by Git. `shared/artifact-ownership.yaml` maps historical dataset paths to target-owned locations. Existing legacy paths remain compatibility aliases.

## contact-timing: When did the CMPU aged order customers contact Chewy relative to the cancellation date?



### Ownership

Target: `contact-timing`. Level: `subsubsection`.
Parent: `customer-contact-patterns`.
Ordered children: `contact-days-relative-to-cancellation`.


### Reproduction commands

Run from the repository root with the project environment installed:
```sh
make contact-timing
make contact-timing REPRO=1
make contact-timing REFRESH=1
```
Default builds reuse retained source data and rerun the validation and presentation steps. They do not query the warehouse. Missing or stale inputs stop the build; inspect the pipeline log before requesting refresh. REFRESH=1 is explicit and may change results.


### Inputs and dependencies

The child make targets above are actual prerequisites. Parent prose is in `src/latex/body.tex` and may appear before, between and after the ordered children.

Shared dependencies:
- `shared/analysis`
- `shared/artifact-ownership.yaml`
- `shared/paths.py`


### Outputs

Generated content: `targets/contact-timing/outputs/latex/content.tex`.
Data and outputs are ignored by Git. `shared/artifact-ownership.yaml` maps historical dataset paths to target-owned locations. Existing legacy paths remain compatibility aliases.

## contact-days-relative-to-cancellation: How many customers contacted Chewy on each day relative to aged-order cancellation?



### Ownership

Target: `contact-days-relative-to-cancellation`. Level: `paragraph`.
Parent: `contact-timing`.
Ordered children: none.


### Reproduction commands

Run from the repository root with the project environment installed:
```sh
make contact-days-relative-to-cancellation
make contact-days-relative-to-cancellation REPRO=1
make contact-days-relative-to-cancellation REFRESH=1
```
Default builds reuse retained source data and rerun the validation and presentation steps. They do not query the warehouse. Missing or stale inputs stop the build; inspect the pipeline log before requesting refresh. REFRESH=1 is explicit and may change results.


### Inputs and dependencies

Generator batch: `contacts`, defined in `shared/analysis/pipelines.yaml`. The batch is shared by related paragraphs and runs once per make invocation.
Existing generator commands (the batch explicitly sets CACHED=1 by default):
- `make opportunity-aged-customer-contacts HANDLED_ONLY=0 CACHED=1`

Retained input folders and ownership:
- `targets/cancellation-sales-baseline/data/`
- `targets/contact-days-relative-to-cancellation/data/`

Dates and cohort parameters are preserved from the source manifests and the existing generator defaults. Financial/contact defaults use May 1 through July 31, 2026, with follow-up observed through October 28; upload/prescription analyses retain their August 15 through October 14 study and documented upload/cancellation cutoffs. Do not mix source snapshots.

Shared dependencies:
- `shared/analysis`
- `shared/artifact-ownership.yaml`
- `shared/paths.py`


### Outputs

Generated content: `targets/contact-days-relative-to-cancellation/outputs/latex/content.tex`.
Tables are exported to `outputs/tables/table.org` and read back to assemble LaTeX. The compatibility adapter retains cell formatting from the validated legacy renderer; `outputs/tables/provenance.json` records the source and Org fingerprints. Figures and diagrams are copied from their newly regenerated canonical exports. Logs are under the batch owner's `outputs/build/` folder.
Data and outputs are ignored by Git. `shared/artifact-ownership.yaml` maps historical dataset paths to target-owned locations. Existing legacy paths remain compatibility aliases.


### Additional target-owned source

- `targets/contact-days-relative-to-cancellation/src/sql/opportunity_aged_customer_contacts.sql`

## contact-frequency: What was the frequency of contacting Chewy for CMPU aged order customers?



### Ownership

Target: `contact-frequency`. Level: `subsubsection`.
Parent: `customer-contact-patterns`.
Ordered children: `customer-contact-day-frequency`.


### Reproduction commands

Run from the repository root with the project environment installed:
```sh
make contact-frequency
make contact-frequency REPRO=1
make contact-frequency REFRESH=1
```
Default builds reuse retained source data and rerun the validation and presentation steps. They do not query the warehouse. Missing or stale inputs stop the build; inspect the pipeline log before requesting refresh. REFRESH=1 is explicit and may change results.


### Inputs and dependencies

The child make targets above are actual prerequisites. Parent prose is in `src/latex/body.tex` and may appear before, between and after the ordered children.

Shared dependencies:
- `shared/analysis`
- `shared/artifact-ownership.yaml`
- `shared/paths.py`


### Outputs

Generated content: `targets/contact-frequency/outputs/latex/content.tex`.
Data and outputs are ignored by Git. `shared/artifact-ownership.yaml` maps historical dataset paths to target-owned locations. Existing legacy paths remain compatibility aliases.

## customer-contact-day-frequency: How many distinct days did aged-order customers contact Chewy?



### Ownership

Target: `customer-contact-day-frequency`. Level: `paragraph`.
Parent: `contact-frequency`.
Ordered children: none.


### Reproduction commands

Run from the repository root with the project environment installed:
```sh
make customer-contact-day-frequency
make customer-contact-day-frequency REPRO=1
make customer-contact-day-frequency REFRESH=1
```
Default builds reuse retained source data and rerun the validation and presentation steps. They do not query the warehouse. Missing or stale inputs stop the build; inspect the pipeline log before requesting refresh. REFRESH=1 is explicit and may change results.


### Inputs and dependencies

Generator batch: `contacts`, defined in `shared/analysis/pipelines.yaml`. The batch is shared by related paragraphs and runs once per make invocation.
Existing generator commands (the batch explicitly sets CACHED=1 by default):
- `make opportunity-aged-customer-contacts HANDLED_ONLY=0 CACHED=1`

Retained input folders and ownership:
- `targets/cancellation-sales-baseline/data/`
- `targets/contact-days-relative-to-cancellation/data/`

Dates and cohort parameters are preserved from the source manifests and the existing generator defaults. Financial/contact defaults use May 1 through July 31, 2026, with follow-up observed through October 28; upload/prescription analyses retain their August 15 through October 14 study and documented upload/cancellation cutoffs. Do not mix source snapshots.

Shared dependencies:
- `shared/analysis`
- `shared/artifact-ownership.yaml`
- `shared/paths.py`


### Outputs

Generated content: `targets/customer-contact-day-frequency/outputs/latex/content.tex`.
Tables are exported to `outputs/tables/table.org` and read back to assemble LaTeX. The compatibility adapter retains cell formatting from the validated legacy renderer; `outputs/tables/provenance.json` records the source and Org fingerprints. Figures and diagrams are copied from their newly regenerated canonical exports. Logs are under the batch owner's `outputs/build/` folder.
Data and outputs are ignored by Git. `shared/artifact-ownership.yaml` maps historical dataset paths to target-owned locations. Existing legacy paths remain compatibility aliases.

## contact-frequency-and-returns: Does more frequent contact imply higher propensity to re-order successfully for the same pet and part number in 14 days?



### Ownership

Target: `contact-frequency-and-returns`. Level: `subsubsection`.
Parent: `customer-contact-patterns`.
Ordered children: `return-rates-by-contact-frequency`.


### Reproduction commands

Run from the repository root with the project environment installed:
```sh
make contact-frequency-and-returns
make contact-frequency-and-returns REPRO=1
make contact-frequency-and-returns REFRESH=1
```
Default builds reuse retained source data and rerun the validation and presentation steps. They do not query the warehouse. Missing or stale inputs stop the build; inspect the pipeline log before requesting refresh. REFRESH=1 is explicit and may change results.


### Inputs and dependencies

The child make targets above are actual prerequisites. Parent prose is in `src/latex/body.tex` and may appear before, between and after the ordered children.

Shared dependencies:
- `shared/analysis`
- `shared/artifact-ownership.yaml`
- `shared/paths.py`


### Outputs

Generated content: `targets/contact-frequency-and-returns/outputs/latex/content.tex`.
Data and outputs are ignored by Git. `shared/artifact-ownership.yaml` maps historical dataset paths to target-owned locations. Existing legacy paths remain compatibility aliases.

## return-rates-by-contact-frequency: How do 14-day same-pet, same-product return rates vary with contact-day frequency?



### Ownership

Target: `return-rates-by-contact-frequency`. Level: `paragraph`.
Parent: `contact-frequency-and-returns`.
Ordered children: none.


### Reproduction commands

Run from the repository root with the project environment installed:
```sh
make return-rates-by-contact-frequency
make return-rates-by-contact-frequency REPRO=1
make return-rates-by-contact-frequency REFRESH=1
```
Default builds reuse retained source data and rerun the validation and presentation steps. They do not query the warehouse. Missing or stale inputs stop the build; inspect the pipeline log before requesting refresh. REFRESH=1 is explicit and may change results.


### Inputs and dependencies

Generator batch: `contact-frequency`, defined in `shared/analysis/pipelines.yaml`. The batch is shared by related paragraphs and runs once per make invocation.
Existing generator commands (the batch explicitly sets CACHED=1 by default):
- `make opportunity-contact-frequency-reorders FOLLOWUP_DAYS=14 HANDLED_ONLY=0 CACHED=1`

Retained input folders and ownership:
- `targets/contact-days-relative-to-cancellation/data/`
- `targets/return-rates-by-contact-frequency/data/`

Dates and cohort parameters are preserved from the source manifests and the existing generator defaults. Financial/contact defaults use May 1 through July 31, 2026, with follow-up observed through October 28; upload/prescription analyses retain their August 15 through October 14 study and documented upload/cancellation cutoffs. Do not mix source snapshots.
- `targets/return-rates-by-contact-frequency/src/python/create_opportunity_contact_frequency_reorders.py`
- `targets/return-rates-by-contact-frequency/src/sql/create_opportunity_contact_frequency_reorders-query-1.sql.j2`

Imported analysis dependencies:
- `targets/contact-days-relative-to-cancellation/src/python/create_opportunity_aged_customer_contacts.py`
- `targets/opportunity-aged-reorders/src/python/create_opportunity_aged_reorders.py`
- `shared/python/markdown_tables.py`
- `shared/python/opportunity_report_tables.py`
- `targets/cancellation-sales-baseline/src/python/create_opportunity_order_cancellation_summary.py`

Shared dependencies:
- `shared/analysis`
- `shared/artifact-ownership.yaml`
- `shared/paths.py`
- `shared/python/__init__.py`
- `targets/contact-days-relative-to-cancellation/src/python/create_opportunity_aged_customer_contacts.py`
- `targets/opportunity-aged-reorders/src/python/create_opportunity_aged_reorders.py`
- `shared/python/markdown_tables.py`
- `shared/python/opportunity_report_tables.py`
- `shared/source-ownership.yaml`
- `shared/sql_templates.py`


### Outputs

Generated content: `targets/return-rates-by-contact-frequency/outputs/latex/content.tex`.
Tables are exported to `outputs/tables/table.org` and read back to assemble LaTeX. The compatibility adapter retains cell formatting from the validated legacy renderer; `outputs/tables/provenance.json` records the source and Org fingerprints. Figures and diagrams are copied from their newly regenerated canonical exports. Logs are under the batch owner's `outputs/build/` folder.
Data and outputs are ignored by Git. `shared/artifact-ownership.yaml` maps historical dataset paths to target-owned locations. Existing legacy paths remain compatibility aliases.

## contact-proximity-and-returns: Does contact closer to cancellation imply higher propensity to re-order successfully in 14 days for the same pet and part number?



### Ownership

Target: `contact-proximity-and-returns`. Level: `subsubsection`.
Parent: `customer-contact-patterns`.
Ordered children: `return-rates-by-contact-window`.


### Reproduction commands

Run from the repository root with the project environment installed:
```sh
make contact-proximity-and-returns
make contact-proximity-and-returns REPRO=1
make contact-proximity-and-returns REFRESH=1
```
Default builds reuse retained source data and rerun the validation and presentation steps. They do not query the warehouse. Missing or stale inputs stop the build; inspect the pipeline log before requesting refresh. REFRESH=1 is explicit and may change results.


### Inputs and dependencies

The child make targets above are actual prerequisites. Parent prose is in `src/latex/body.tex` and may appear before, between and after the ordered children.

Shared dependencies:
- `shared/analysis`
- `shared/artifact-ownership.yaml`
- `shared/paths.py`


### Outputs

Generated content: `targets/contact-proximity-and-returns/outputs/latex/content.tex`.
Data and outputs are ignored by Git. `shared/artifact-ownership.yaml` maps historical dataset paths to target-owned locations. Existing legacy paths remain compatibility aliases.

## return-rates-by-contact-window: How do 14-day same-pet, same-product return rates compare for customers contacting on days -7 through +3 and other customers?



### Ownership

Target: `return-rates-by-contact-window`. Level: `paragraph`.
Parent: `contact-proximity-and-returns`.
Ordered children: none.


### Reproduction commands

Run from the repository root with the project environment installed:
```sh
make return-rates-by-contact-window
make return-rates-by-contact-window REPRO=1
make return-rates-by-contact-window REFRESH=1
```
Default builds reuse retained source data and rerun the validation and presentation steps. They do not query the warehouse. Missing or stale inputs stop the build; inspect the pipeline log before requesting refresh. REFRESH=1 is explicit and may change results.


### Inputs and dependencies

Generator batch: `contact-window`, defined in `shared/analysis/pipelines.yaml`. The batch is shared by related paragraphs and runs once per make invocation.
Existing generator commands (the batch explicitly sets CACHED=1 by default):
- `make opportunity-contact-window-reorders CACHED=1`

Retained input folders and ownership:
- `targets/return-rates-by-contact-frequency/data/`
- `targets/return-rates-by-contact-window/data/`

Dates and cohort parameters are preserved from the source manifests and the existing generator defaults. Financial/contact defaults use May 1 through July 31, 2026, with follow-up observed through October 28; upload/prescription analyses retain their August 15 through October 14 study and documented upload/cancellation cutoffs. Do not mix source snapshots.
- `targets/return-rates-by-contact-window/src/python/create_opportunity_contact_window_reorders.py`
- `targets/return-rates-by-contact-window/src/sql/create_opportunity_contact_window_reorders-query-1.sql.j2`

Imported analysis dependencies:
- `targets/contact-days-relative-to-cancellation/src/python/create_opportunity_aged_customer_contacts.py`
- `targets/opportunity-aged-reorders/src/python/create_opportunity_aged_reorders.py`
- `targets/study-population-counts/src/python/create_study_population_report_tables.py`
- `shared/python/markdown_tables.py`
- `shared/python/opportunity_report_tables.py`
- `targets/cancellation-sales-baseline/src/python/create_opportunity_order_cancellation_summary.py`
- `targets/return-rates-by-contact-frequency/src/python/create_opportunity_contact_frequency_reorders.py`

Shared dependencies:
- `shared/analysis`
- `shared/artifact-ownership.yaml`
- `shared/paths.py`
- `shared/python/__init__.py`
- `targets/contact-days-relative-to-cancellation/src/python/create_opportunity_aged_customer_contacts.py`
- `targets/opportunity-aged-reorders/src/python/create_opportunity_aged_reorders.py`
- `targets/study-population-counts/src/python/create_study_population_report_tables.py`
- `shared/python/markdown_tables.py`
- `shared/python/opportunity_report_tables.py`
- `shared/source-ownership.yaml`
- `shared/sql_templates.py`


### Outputs

Generated content: `targets/return-rates-by-contact-window/outputs/latex/content.tex`.
Tables are exported to `outputs/tables/table.org` and read back to assemble LaTeX. The compatibility adapter retains cell formatting from the validated legacy renderer; `outputs/tables/provenance.json` records the source and Org fingerprints. Figures and diagrams are copied from their newly regenerated canonical exports. Logs are under the batch owner's `outputs/build/` folder.
Data and outputs are ignored by Git. `shared/artifact-ownership.yaml` maps historical dataset paths to target-owned locations. Existing legacy paths remain compatibility aliases.

## upload-processing-delays: What are the delays in processing uploaded prescriptions?



### Ownership

Target: `upload-processing-delays`. Level: `subsection`.
Parent: `appendix`.
Ordered children: `study-population-context`, `prescription-upload-coverage`, `customer-upload-delay`, `upload-processing-time`, `accepted-upload-approval-time`.


### Reproduction commands

Run from the repository root with the project environment installed:
```sh
make upload-processing-delays
make upload-processing-delays REPRO=1
make upload-processing-delays REFRESH=1
```
Default builds reuse retained source data and rerun the validation and presentation steps. They do not query the warehouse. Missing or stale inputs stop the build; inspect the pipeline log before requesting refresh. REFRESH=1 is explicit and may change results.


### Inputs and dependencies

The child make targets above are actual prerequisites. Parent prose is in `src/latex/body.tex` and may appear before, between and after the ordered children.

Shared dependencies:
- `shared/analysis`
- `shared/artifact-ownership.yaml`
- `shared/paths.py`


### Outputs

Generated content: `targets/upload-processing-delays/outputs/latex/content.tex`.
Data and outputs are ignored by Git. `shared/artifact-ownership.yaml` maps historical dataset paths to target-owned locations. Existing legacy paths remain compatibility aliases.

## study-population-context: Which prescriptions, orders, customers, and uploads are included in the study?



### Ownership

Target: `study-population-context`. Level: `subsubsection`.
Parent: `upload-processing-delays`.
Ordered children: `study-population-counts`, `study-prescription-decisions`, `study-order-cancellation-sales`, `first-order-upload-status-flow`.


### Reproduction commands

Run from the repository root with the project environment installed:
```sh
make study-population-context
make study-population-context REPRO=1
make study-population-context REFRESH=1
```
Default builds reuse retained source data and rerun the validation and presentation steps. They do not query the warehouse. Missing or stale inputs stop the build; inspect the pipeline log before requesting refresh. REFRESH=1 is explicit and may change results.


### Inputs and dependencies

The child make targets above are actual prerequisites. Parent prose is in `src/latex/body.tex` and may appear before, between and after the ordered children.

Shared dependencies:
- `shared/analysis`
- `shared/artifact-ownership.yaml`
- `shared/paths.py`


### Outputs

Generated content: `targets/study-population-context/outputs/latex/content.tex`.
Data and outputs are ignored by Git. `shared/artifact-ownership.yaml` maps historical dataset paths to target-owned locations. Existing legacy paths remain compatibility aliases.

## study-population-counts: How many prescriptions, orders, lines, customers, and uploaded documents are in each study population?



### Ownership

Target: `study-population-counts`. Level: `paragraph`.
Parent: `study-population-context`.
Ordered children: none.


### Reproduction commands

Run from the repository root with the project environment installed:
```sh
make study-population-counts
make study-population-counts REPRO=1
make study-population-counts REFRESH=1
```
Default builds reuse retained source data and rerun the validation and presentation steps. They do not query the warehouse. Missing or stale inputs stop the build; inspect the pipeline log before requesting refresh. REFRESH=1 is explicit and may change results.

Refresh limitation: The study uses frozen, mutually reconciled extracts. Refresh its source snapshots together before rebuilding; see the target input manifests. No partial refresh is performed.


### Inputs and dependencies

Generator batch: `study-population`, defined in `shared/analysis/pipelines.yaml`. The batch is shared by related paragraphs and runs once per make invocation.
Existing generator commands (the batch explicitly sets CACHED=1 by default):
- `make study-population-tables CACHED=1`

Retained input folders and ownership:
- `targets/first-order-upload-status-flow/data/`
- `targets/study-population-counts/data/`
- `targets/study-prescription-decisions/data/`
- `targets/study-order-cancellation-sales/data/`

Dates and cohort parameters are preserved from the source manifests and the existing generator defaults. Financial/contact defaults use May 1 through July 31, 2026, with follow-up observed through October 28; upload/prescription analyses retain their August 15 through October 14 study and documented upload/cancellation cutoffs. Do not mix source snapshots.
- `targets/study-population-counts/src/python/summarize_study_population_uploaded_documents.py`
- `targets/study-population-counts/src/sql/cmpu_study_population_uploaded_documents.sql`
- `targets/study-population-counts/src/sql/summarize_study_population_uploaded_documents-query-1.sql.j2`

Imported analysis dependencies:
- `shared/upload_entities.py` and `shared/runtime.py`
- `shared/python/markdown_tables.py`

Shared dependencies:
- `shared/analysis`
- `shared/artifact-ownership.yaml`
- `shared/paths.py`
- `shared/python/__init__.py`
- `shared/upload_entities.py` and `shared/runtime.py`
- `shared/python/markdown_tables.py`
- `shared/source-ownership.yaml`
- `shared/sql_templates.py`


### Outputs

Generated content: `targets/study-population-counts/outputs/latex/content.tex`.
Tables are exported to `outputs/tables/table.org` and read back to assemble LaTeX. The compatibility adapter retains cell formatting from the validated legacy renderer; `outputs/tables/provenance.json` records the source and Org fingerprints. Figures and diagrams are copied from their newly regenerated canonical exports. Logs are under the batch owner's `outputs/build/` folder.
Data and outputs are ignored by Git. `shared/artifact-ownership.yaml` maps historical dataset paths to target-owned locations. Existing legacy paths remain compatibility aliases.

## study-prescription-decisions: How are prescription approval decisions distributed across the study populations?



### Ownership

Target: `study-prescription-decisions`. Level: `paragraph`.
Parent: `study-population-context`.
Ordered children: none.


### Reproduction commands

Run from the repository root with the project environment installed:
```sh
make study-prescription-decisions
make study-prescription-decisions REPRO=1
make study-prescription-decisions REFRESH=1
```
Default builds reuse retained source data and rerun the validation and presentation steps. They do not query the warehouse. Missing or stale inputs stop the build; inspect the pipeline log before requesting refresh. REFRESH=1 is explicit and may change results.

Refresh limitation: The study uses frozen, mutually reconciled extracts. Refresh its source snapshots together before rebuilding; see the target input manifests. No partial refresh is performed.


### Inputs and dependencies

Generator batch: `study-population`, defined in `shared/analysis/pipelines.yaml`. The batch is shared by related paragraphs and runs once per make invocation.
Existing generator commands (the batch explicitly sets CACHED=1 by default):
- `make study-population-tables CACHED=1`

Retained input folders and ownership:
- `targets/first-order-upload-status-flow/data/`
- `targets/study-population-counts/data/`
- `targets/study-prescription-decisions/data/`
- `targets/study-order-cancellation-sales/data/`

Dates and cohort parameters are preserved from the source manifests and the existing generator defaults. Financial/contact defaults use May 1 through July 31, 2026, with follow-up observed through October 28; upload/prescription analyses retain their August 15 through October 14 study and documented upload/cancellation cutoffs. Do not mix source snapshots.
- `targets/study-prescription-decisions/src/python/summarize_study_population_prescription_decisions.py`
- `targets/study-prescription-decisions/src/sql/cmpu_study_population_prescription_decisions.sql`
- `targets/study-prescription-decisions/src/sql/summarize_study_population_prescription_decisions-query-1.sql.j2`

Imported analysis dependencies:
- `shared/upload_entities.py` and `shared/runtime.py`
- `shared/python/markdown_tables.py`

Shared dependencies:
- `shared/analysis`
- `shared/artifact-ownership.yaml`
- `shared/paths.py`
- `shared/python/__init__.py`
- `shared/upload_entities.py` and `shared/runtime.py`
- `shared/python/markdown_tables.py`
- `shared/source-ownership.yaml`
- `shared/sql_templates.py`


### Outputs

Generated content: `targets/study-prescription-decisions/outputs/latex/content.tex`.
Tables are exported to `outputs/tables/table.org` and read back to assemble LaTeX. The compatibility adapter retains cell formatting from the validated legacy renderer; `outputs/tables/provenance.json` records the source and Org fingerprints. Figures and diagrams are copied from their newly regenerated canonical exports. Logs are under the batch owner's `outputs/build/` folder.
Data and outputs are ignored by Git. `shared/artifact-ownership.yaml` maps historical dataset paths to target-owned locations. Existing legacy paths remain compatibility aliases.

## study-order-cancellation-sales: How do cancellation reasons, order counts, and net sales compare between first orders and all linked orders?



### Ownership

Target: `study-order-cancellation-sales`. Level: `paragraph`.
Parent: `study-population-context`.
Ordered children: none.


### Reproduction commands

Run from the repository root with the project environment installed:
```sh
make study-order-cancellation-sales
make study-order-cancellation-sales REPRO=1
make study-order-cancellation-sales REFRESH=1
```
Default builds reuse retained source data and rerun the validation and presentation steps. They do not query the warehouse. Missing or stale inputs stop the build; inspect the pipeline log before requesting refresh. REFRESH=1 is explicit and may change results.

Refresh limitation: The study uses frozen, mutually reconciled extracts. Refresh its source snapshots together before rebuilding; see the target input manifests. No partial refresh is performed.


### Inputs and dependencies

Generator batch: `study-population`, defined in `shared/analysis/pipelines.yaml`. The batch is shared by related paragraphs and runs once per make invocation.
Existing generator commands (the batch explicitly sets CACHED=1 by default):
- `make study-population-tables CACHED=1`

Retained input folders and ownership:
- `targets/first-order-upload-status-flow/data/`
- `targets/study-population-counts/data/`
- `targets/study-prescription-decisions/data/`
- `targets/study-order-cancellation-sales/data/`

Dates and cohort parameters are preserved from the source manifests and the existing generator defaults. Financial/contact defaults use May 1 through July 31, 2026, with follow-up observed through October 28; upload/prescription analyses retain their August 15 through October 14 study and documented upload/cancellation cutoffs. Do not mix source snapshots.
- `targets/study-order-cancellation-sales/src/python/summarize_prescription_cohort_order_comparison.py`
- `targets/study-order-cancellation-sales/src/sql/prescription_cohort_order_sales.sql`
- `targets/study-order-cancellation-sales/src/sql/summarize_prescription_cohort_order_comparison-query-1.sql.j2`

Imported analysis dependencies:
- `shared/python/markdown_tables.py`
- `shared/python/opportunity_report_tables.py`
- `targets/cancellation-sales-baseline/src/python/create_opportunity_order_cancellation_summary.py`

Shared dependencies:
- `shared/analysis`
- `shared/artifact-ownership.yaml`
- `shared/paths.py`
- `shared/python/__init__.py`
- `shared/python/markdown_tables.py`
- `shared/python/opportunity_report_tables.py`
- `shared/source-ownership.yaml`
- `shared/sql_templates.py`


### Outputs

Generated content: `targets/study-order-cancellation-sales/outputs/latex/content.tex`.
Tables are exported to `outputs/tables/table.org` and read back to assemble LaTeX. The compatibility adapter retains cell formatting from the validated legacy renderer; `outputs/tables/provenance.json` records the source and Org fingerprints. Figures and diagrams are copied from their newly regenerated canonical exports. Logs are under the batch owner's `outputs/build/` folder.
Data and outputs are ignored by Git. `shared/artifact-ownership.yaml` maps historical dataset paths to target-owned locations. Existing legacy paths remain compatibility aliases.

## first-order-upload-status-flow: How do first-order line statuses relate to accepted prescription uploads?



### Ownership

Target: `first-order-upload-status-flow`. Level: `paragraph`.
Parent: `study-population-context`.
Ordered children: none.


### Reproduction commands

Run from the repository root with the project environment installed:
```sh
make first-order-upload-status-flow
make first-order-upload-status-flow REPRO=1
make first-order-upload-status-flow REFRESH=1
```
Default builds reuse retained source data and rerun the validation and presentation steps. They do not query the warehouse. Missing or stale inputs stop the build; inspect the pipeline log before requesting refresh. REFRESH=1 is explicit and may change results.


### Inputs and dependencies

Generator batch: `first-order-status`, defined in `shared/analysis/pipelines.yaml`. The batch is shared by related paragraphs and runs once per make invocation.
Existing generator commands (the batch explicitly sets CACHED=1 by default):
- `make cmpu-first-order-line-status CACHED=1`

Retained input folders and ownership:
- `targets/first-order-upload-status-flow/data/`

Dates and cohort parameters are preserved from the source manifests and the existing generator defaults. Financial/contact defaults use May 1 through July 31, 2026, with follow-up observed through October 28; upload/prescription analyses retain their August 15 through October 14 study and documented upload/cancellation cutoffs. Do not mix source snapshots.
- `targets/first-order-upload-status-flow/src/python/create_cmpu_first_order_line_status.py`
- `targets/first-order-upload-status-flow/src/sql/cmpu_first_order_line_status.sql`

Imported analysis dependencies:
- `shared/runtime.py`, `shared/prescription_uploads.py` and `shared/sankey.py`
- `shared/python/markdown_tables.py`

Shared dependencies:
- `shared/analysis`
- `shared/artifact-ownership.yaml`
- `shared/paths.py`
- `shared/python/__init__.py`
- `shared/runtime.py`, `shared/prescription_uploads.py` and `shared/sankey.py`
- `shared/python/markdown_tables.py`
- `shared/source-ownership.yaml`
- `shared/sql_templates.py`


### Outputs

Generated content: `targets/first-order-upload-status-flow/outputs/latex/content.tex`.
Tables are exported to `outputs/tables/table.org` and read back to assemble LaTeX. The compatibility adapter retains cell formatting from the validated legacy renderer; `outputs/tables/provenance.json` records the source and Org fingerprints. Figures and diagrams are copied from their newly regenerated canonical exports. Logs are under the batch owner's `outputs/build/` folder.
Data and outputs are ignored by Git. `shared/artifact-ownership.yaml` maps historical dataset paths to target-owned locations. Existing legacy paths remain compatibility aliases.


### Prescription-status source ownership

The prescription-level generator and its query belong to this target:
- `src/python/create_cmpu_prescription_first_order_status.py`
- `src/sql/cmpu_prescription_first_order_status.sql`

The line-status generator calls `shared/prescription_uploads.py` for source validation and normalization, `shared/runtime.py` for paths and file fingerprints, and `shared/sankey.py` for diagram rendering. It no longer imports the prescription-level generator or runs that generator's grouping logic just to validate input. The historical Python module name remains available through the source registry. The existing target Make command still builds the line-status analysis used in the report.

## prescription-upload-coverage: What is the percentage of prescription upload?



### Ownership

Target: `prescription-upload-coverage`. Level: `subsubsection`.
Parent: `upload-processing-delays`.
Ordered children: `first-order-upload-coverage`, `no-recorded-cancellation-upload-statuses`, `aged-line-upload-statuses`.


### Reproduction commands

Run from the repository root with the project environment installed:
```sh
make prescription-upload-coverage
make prescription-upload-coverage REPRO=1
make prescription-upload-coverage REFRESH=1
```
Default builds reuse retained source data and rerun the validation and presentation steps. They do not query the warehouse. Missing or stale inputs stop the build; inspect the pipeline log before requesting refresh. REFRESH=1 is explicit and may change results.


### Inputs and dependencies

The child make targets above are actual prerequisites. Parent prose is in `src/latex/body.tex` and may appear before, between and after the ordered children.

Shared dependencies:
- `shared/analysis`
- `shared/artifact-ownership.yaml`
- `shared/paths.py`


### Outputs

Generated content: `targets/prescription-upload-coverage/outputs/latex/content.tex`.
Data and outputs are ignored by Git. `shared/artifact-ownership.yaml` maps historical dataset paths to target-owned locations. Existing legacy paths remain compatibility aliases.

## first-order-upload-coverage: What proportion of first-order lines have prescription uploads by cancellation reason and line-item status?



### Ownership

Target: `first-order-upload-coverage`. Level: `paragraph`.
Parent: `prescription-upload-coverage`.
Ordered children: none.


### Reproduction commands

Run from the repository root with the project environment installed:
```sh
make first-order-upload-coverage
make first-order-upload-coverage REPRO=1
make first-order-upload-coverage REFRESH=1
```
Default builds reuse retained source data and rerun the validation and presentation steps. They do not query the warehouse. Missing or stale inputs stop the build; inspect the pipeline log before requesting refresh. REFRESH=1 is explicit and may change results.

Refresh limitation: The retained upload tables use frozen prescription/reason membership and upload snapshots. The new SQL derives membership from current database tables; coordinate a full cohort refresh and reconcile membership before replacing the historical report.


### Inputs and dependencies

Generator batch: `upload-coverage`, defined in `shared/analysis/pipelines.yaml`. The batch is shared by related paragraphs and runs once per make invocation.
Existing generator commands (the batch explicitly sets CACHED=1 by default):
- `make study-upload-tables CACHED=1`

Retained input folders and ownership:
- `targets/first-order-upload-status-flow/data/`
- `targets/study-population-counts/data/`
- `targets/study-prescription-decisions/data/`
- `targets/first-order-upload-coverage/data/`
- `targets/no-recorded-cancellation-upload-statuses/data/`
- `targets/aged-line-upload-statuses/data/`

Dates and cohort parameters are preserved from the source manifests and the existing generator defaults. Financial/contact defaults use May 1 through July 31, 2026, with follow-up observed through October 28; upload/prescription analyses retain their August 15 through October 14 study and documented upload/cancellation cutoffs. Do not mix source snapshots.
- `targets/first-order-upload-coverage/src/python/create_study_upload_coverage_by_cancel_reason.py`
- `targets/first-order-upload-coverage/src/sql/create_study_upload_coverage_by_cancel_reason-query-1.sql.j2`

Imported analysis dependencies:
- `shared/upload_entities.py` and `shared/runtime.py`
- `shared/python/markdown_tables.py`
- `shared/python/opportunity_report_tables.py`
- `targets/cancellation-sales-baseline/src/python/create_opportunity_order_cancellation_summary.py`
- `targets/study-prescription-decisions/src/python/summarize_study_population_prescription_decisions.py`

Shared dependencies:
- `shared/analysis`
- `shared/artifact-ownership.yaml`
- `shared/paths.py`
- `shared/python/__init__.py`
- `shared/upload_entities.py` and `shared/runtime.py`
- `shared/python/markdown_tables.py`
- `shared/python/opportunity_report_tables.py`
- `shared/source-ownership.yaml`
- `shared/sql_templates.py`


### Outputs

Generated content: `targets/first-order-upload-coverage/outputs/latex/content.tex`.
Tables are exported to `outputs/tables/table.org` and read back to assemble LaTeX. The compatibility adapter retains cell formatting from the validated legacy renderer; `outputs/tables/provenance.json` records the source and Org fingerprints. Figures and diagrams are copied from their newly regenerated canonical exports. Logs are under the batch owner's `outputs/build/` folder.
Data and outputs are ignored by Git. `shared/artifact-ownership.yaml` maps historical dataset paths to target-owned locations. Existing legacy paths remain compatibility aliases.

## no-recorded-cancellation-upload-statuses: How do prescription, order, and line-item statuses vary by upload coverage when no cancellation reason is recorded?



### Ownership

Target: `no-recorded-cancellation-upload-statuses`. Level: `paragraph`.
Parent: `prescription-upload-coverage`.
Ordered children: none.


### Reproduction commands

Run from the repository root with the project environment installed:
```sh
make no-recorded-cancellation-upload-statuses
make no-recorded-cancellation-upload-statuses REPRO=1
make no-recorded-cancellation-upload-statuses REFRESH=1
```
Default builds reuse retained source data and rerun the validation and presentation steps. They do not query the warehouse. Missing or stale inputs stop the build; inspect the pipeline log before requesting refresh. REFRESH=1 is explicit and may change results.

Refresh limitation: The retained upload tables use frozen prescription/reason membership and upload snapshots. The new SQL derives membership from current database tables; coordinate a full cohort refresh and reconcile membership before replacing the historical report.


### Inputs and dependencies

Generator batch: `upload-coverage`, defined in `shared/analysis/pipelines.yaml`. The batch is shared by related paragraphs and runs once per make invocation.
Existing generator commands (the batch explicitly sets CACHED=1 by default):
- `make study-upload-tables CACHED=1`

Retained input folders and ownership:
- `targets/first-order-upload-status-flow/data/`
- `targets/study-population-counts/data/`
- `targets/study-prescription-decisions/data/`
- `targets/first-order-upload-coverage/data/`
- `targets/no-recorded-cancellation-upload-statuses/data/`
- `targets/aged-line-upload-statuses/data/`

Dates and cohort parameters are preserved from the source manifests and the existing generator defaults. Financial/contact defaults use May 1 through July 31, 2026, with follow-up observed through October 28; upload/prescription analyses retain their August 15 through October 14 study and documented upload/cancellation cutoffs. Do not mix source snapshots.
- `targets/no-recorded-cancellation-upload-statuses/src/python/create_study_no_cancellation_upload_details.py`
- `targets/no-recorded-cancellation-upload-statuses/src/sql/create_study_no_cancellation_upload_details-query-1.sql.j2`
- `targets/no-recorded-cancellation-upload-statuses/src/sql/study_no_cancellation_upload_details.sql`

Imported analysis dependencies:
- `shared/upload_entities.py` and `shared/runtime.py`
- `shared/python/markdown_tables.py`
- `shared/python/opportunity_report_tables.py`
- `targets/cancellation-sales-baseline/src/python/create_opportunity_order_cancellation_summary.py`
- `targets/first-order-upload-coverage/src/python/create_study_upload_coverage_by_cancel_reason.py`
- `targets/study-prescription-decisions/src/python/summarize_study_population_prescription_decisions.py`

Shared dependencies:
- `shared/analysis`
- `shared/artifact-ownership.yaml`
- `shared/paths.py`
- `shared/python/__init__.py`
- `shared/upload_entities.py` and `shared/runtime.py`
- `shared/python/markdown_tables.py`
- `shared/python/opportunity_report_tables.py`
- `shared/source-ownership.yaml`
- `shared/sql_templates.py`


### Outputs

Generated content: `targets/no-recorded-cancellation-upload-statuses/outputs/latex/content.tex`.
Tables are exported to `outputs/tables/table.org` and read back to assemble LaTeX. The compatibility adapter retains cell formatting from the validated legacy renderer; `outputs/tables/provenance.json` records the source and Org fingerprints. Figures and diagrams are copied from their newly regenerated canonical exports. Logs are under the batch owner's `outputs/build/` folder.
Data and outputs are ignored by Git. `shared/artifact-ownership.yaml` maps historical dataset paths to target-owned locations. Existing legacy paths remain compatibility aliases.

## aged-line-upload-statuses: How do prescription, order, and line-item statuses vary by upload coverage for aged orders?



### Ownership

Target: `aged-line-upload-statuses`. Level: `paragraph`.
Parent: `prescription-upload-coverage`.
Ordered children: none.


### Reproduction commands

Run from the repository root with the project environment installed:
```sh
make aged-line-upload-statuses
make aged-line-upload-statuses REPRO=1
make aged-line-upload-statuses REFRESH=1
```
Default builds reuse retained source data and rerun the validation and presentation steps. They do not query the warehouse. Missing or stale inputs stop the build; inspect the pipeline log before requesting refresh. REFRESH=1 is explicit and may change results.

Refresh limitation: The retained upload tables use frozen prescription/reason membership and upload snapshots. The new SQL derives membership from current database tables; coordinate a full cohort refresh and reconcile membership before replacing the historical report.


### Inputs and dependencies

Generator batch: `upload-coverage`, defined in `shared/analysis/pipelines.yaml`. The batch is shared by related paragraphs and runs once per make invocation.
Existing generator commands (the batch explicitly sets CACHED=1 by default):
- `make study-upload-tables CACHED=1`

Retained input folders and ownership:
- `targets/first-order-upload-status-flow/data/`
- `targets/study-population-counts/data/`
- `targets/study-prescription-decisions/data/`
- `targets/first-order-upload-coverage/data/`
- `targets/no-recorded-cancellation-upload-statuses/data/`
- `targets/aged-line-upload-statuses/data/`

Dates and cohort parameters are preserved from the source manifests and the existing generator defaults. Financial/contact defaults use May 1 through July 31, 2026, with follow-up observed through October 28; upload/prescription analyses retain their August 15 through October 14 study and documented upload/cancellation cutoffs. Do not mix source snapshots.
- `targets/aged-line-upload-statuses/src/python/create_study_aged_order_upload_coverage.py`

Imported analysis dependencies:
- `shared/upload_entities.py` and `shared/runtime.py`
- `shared/python/markdown_tables.py`
- `shared/python/opportunity_report_tables.py`
- `targets/cancellation-sales-baseline/src/python/create_opportunity_order_cancellation_summary.py`
- `targets/first-order-upload-coverage/src/python/create_study_upload_coverage_by_cancel_reason.py`
- `targets/no-recorded-cancellation-upload-statuses/src/python/create_study_no_cancellation_upload_details.py`
- `targets/study-prescription-decisions/src/python/summarize_study_population_prescription_decisions.py`

Shared dependencies:
- `shared/analysis`
- `shared/artifact-ownership.yaml`
- `shared/paths.py`
- `shared/python/__init__.py`
- `shared/upload_entities.py` and `shared/runtime.py`
- `shared/python/markdown_tables.py`
- `shared/python/opportunity_report_tables.py`
- `shared/source-ownership.yaml`
- `shared/sql_templates.py`


### Outputs

Generated content: `targets/aged-line-upload-statuses/outputs/latex/content.tex`.
Tables are exported to `outputs/tables/table.org` and read back to assemble LaTeX. The compatibility adapter retains cell formatting from the validated legacy renderer; `outputs/tables/provenance.json` records the source and Org fingerprints. Figures and diagrams are copied from their newly regenerated canonical exports. Logs are under the batch owner's `outputs/build/` folder.
Data and outputs are ignored by Git. `shared/artifact-ownership.yaml` maps historical dataset paths to target-owned locations. Existing legacy paths remain compatibility aliases.

## customer-upload-delay: How long do customers wait to upload a prescription?



### Ownership

Target: `customer-upload-delay`. Level: `subsubsection`.
Parent: `upload-processing-delays`.
Ordered children: `upload-delay-from-order-creation`.


### Reproduction commands

Run from the repository root with the project environment installed:
```sh
make customer-upload-delay
make customer-upload-delay REPRO=1
make customer-upload-delay REFRESH=1
```
Default builds reuse retained source data and rerun the validation and presentation steps. They do not query the warehouse. Missing or stale inputs stop the build; inspect the pipeline log before requesting refresh. REFRESH=1 is explicit and may change results.


### Inputs and dependencies

The child make targets above are actual prerequisites. Parent prose is in `src/latex/body.tex` and may appear before, between and after the ordered children.

Shared dependencies:
- `shared/analysis`
- `shared/artifact-ownership.yaml`
- `shared/paths.py`


### Outputs

Generated content: `targets/customer-upload-delay/outputs/latex/content.tex`.
Data and outputs are ignored by Git. `shared/artifact-ownership.yaml` maps historical dataset paths to target-owned locations. Existing legacy paths remain compatibility aliases.

## upload-delay-from-order-creation: How does time from order creation to upload compare between all study uploads and aged-order uploads?



### Ownership

Target: `upload-delay-from-order-creation`. Level: `paragraph`.
Parent: `customer-upload-delay`.
Ordered children: none.


### Reproduction commands

Run from the repository root with the project environment installed:
```sh
make upload-delay-from-order-creation
make upload-delay-from-order-creation REPRO=1
make upload-delay-from-order-creation REFRESH=1
```
Default builds reuse retained source data and rerun the validation and presentation steps. They do not query the warehouse. Missing or stale inputs stop the build; inspect the pipeline log before requesting refresh. REFRESH=1 is explicit and may change results.


### Inputs and dependencies

Generator batch: `upload-creation`, defined in `shared/analysis/pipelines.yaml`. The batch is shared by related paragraphs and runs once per make invocation.
Existing generator commands (the batch explicitly sets CACHED=1 by default):
- `make cmpu-upload-entity-order-creation-distributions CACHED=1`

Retained input folders and ownership:
- `targets/upload-delay-from-order-creation/data/`

Dates and cohort parameters are preserved from the source manifests and the existing generator defaults. Financial/contact defaults use May 1 through July 31, 2026, with follow-up observed through October 28; upload/prescription analyses retain their August 15 through October 14 study and documented upload/cancellation cutoffs. Do not mix source snapshots.
- `targets/upload-delay-from-order-creation/src/python/create_cmpu_upload_entity_order_creation_distributions.py`
- `targets/upload-delay-from-order-creation/src/sql/cmpu_upload_entity_order_creation_distributions.sql`

Imported analysis dependencies:
- `shared/upload_entities.py` and `shared/runtime.py`
- `shared/python/markdown_tables.py`

Shared dependencies:
- `shared/analysis`
- `shared/artifact-ownership.yaml`
- `shared/paths.py`
- `shared/python/__init__.py`
- `shared/upload_entities.py` and `shared/runtime.py`
- `shared/python/markdown_tables.py`
- `shared/source-ownership.yaml`
- `shared/sql_templates.py`


### Outputs

Generated content: `targets/upload-delay-from-order-creation/outputs/latex/content.tex`.
Tables are exported to `outputs/tables/table.org` and read back to assemble LaTeX. The compatibility adapter retains cell formatting from the validated legacy renderer; `outputs/tables/provenance.json` records the source and Org fingerprints. Figures and diagrams are copied from their newly regenerated canonical exports. Logs are under the batch owner's `outputs/build/` folder.
Data and outputs are ignored by Git. `shared/artifact-ownership.yaml` maps historical dataset paths to target-owned locations. Existing legacy paths remain compatibility aliases.

## upload-processing-time: How long does it take for an uploaded prescription to be ready for approval?



### Ownership

Target: `upload-processing-time`. Level: `subsubsection`.
Parent: `upload-processing-delays`.
Ordered children: `all-upload-state-change-delays`, `aged-upload-state-change-delays`.


### Reproduction commands

Run from the repository root with the project environment installed:
```sh
make upload-processing-time
make upload-processing-time REPRO=1
make upload-processing-time REFRESH=1
```
Default builds reuse retained source data and rerun the validation and presentation steps. They do not query the warehouse. Missing or stale inputs stop the build; inspect the pipeline log before requesting refresh. REFRESH=1 is explicit and may change results.


### Inputs and dependencies

The child make targets above are actual prerequisites. Parent prose is in `src/latex/body.tex` and may appear before, between and after the ordered children.

Shared dependencies:
- `shared/analysis`
- `shared/artifact-ownership.yaml`
- `shared/paths.py`


### Outputs

Generated content: `targets/upload-processing-time/outputs/latex/content.tex`.
Data and outputs are ignored by Git. `shared/artifact-ownership.yaml` maps historical dataset paths to target-owned locations. Existing legacy paths remain compatibility aliases.

## all-upload-state-change-delays: How long does it take study uploads to reach their recorded states?



### Ownership

Target: `all-upload-state-change-delays`. Level: `paragraph`.
Parent: `upload-processing-time`.
Ordered children: none.


### Reproduction commands

Run from the repository root with the project environment installed:
```sh
make all-upload-state-change-delays
make all-upload-state-change-delays REPRO=1
make all-upload-state-change-delays REFRESH=1
```
Default builds reuse retained source data and rerun the validation and presentation steps. They do not query the warehouse. Missing or stale inputs stop the build; inspect the pipeline log before requesting refresh. REFRESH=1 is explicit and may change results.


### Inputs and dependencies

Generator batch: `upload-state`, defined in `shared/analysis/pipelines.yaml`. The batch is shared by related paragraphs and runs once per make invocation.
Existing generator commands (the batch explicitly sets CACHED=1 by default):
- `make cmpu-upload-entity-state-change-distributions CACHED=1`

Retained input folders and ownership:
- `targets/all-upload-state-change-delays/data/`

Dates and cohort parameters are preserved from the source manifests and the existing generator defaults. Financial/contact defaults use May 1 through July 31, 2026, with follow-up observed through October 28; upload/prescription analyses retain their August 15 through October 14 study and documented upload/cancellation cutoffs. Do not mix source snapshots.

Shared dependencies:
- `shared/analysis`
- `shared/artifact-ownership.yaml`
- `shared/paths.py`


### Outputs

Generated content: `targets/all-upload-state-change-delays/outputs/latex/content.tex`.
Tables are exported to `outputs/tables/table.org` and read back to assemble LaTeX. The compatibility adapter retains cell formatting from the validated legacy renderer; `outputs/tables/provenance.json` records the source and Org fingerprints. Figures and diagrams are copied from their newly regenerated canonical exports. Logs are under the batch owner's `outputs/build/` folder.
Data and outputs are ignored by Git. `shared/artifact-ownership.yaml` maps historical dataset paths to target-owned locations. Existing legacy paths remain compatibility aliases.


### Additional target-owned source

- `targets/all-upload-state-change-delays/src/sql/cmpu_upload_entity_state_change_distributions.sql`


### Source ownership

This target owns `src/python/create_cmpu_upload_entity_state_change_distributions.py` and `src/sql/cmpu_upload_entity_state_change_distributions.sql`. The generator produces the full-study and aged-order plots consumed by the two paragraph targets.

Other analyses import `shared/upload_entities.py` for date parameters and entity/association validation, `shared/duration_plots.py` for duration statistics and boxplots, and `shared/runtime.py` for file fingerprints. They no longer import this generator. Cached builds retain the existing recorded source-identity checks; this split does not refresh warehouse data.

## aged-upload-state-change-delays: How long does it take aged-order uploads to reach their recorded states?



### Ownership

Target: `aged-upload-state-change-delays`. Level: `paragraph`.
Parent: `upload-processing-time`.
Ordered children: none.


### Reproduction commands

Run from the repository root with the project environment installed:
```sh
make aged-upload-state-change-delays
make aged-upload-state-change-delays REPRO=1
make aged-upload-state-change-delays REFRESH=1
```
Default builds reuse retained source data and rerun the validation and presentation steps. They do not query the warehouse. Missing or stale inputs stop the build; inspect the pipeline log before requesting refresh. REFRESH=1 is explicit and may change results.


### Inputs and dependencies

Generator batch: `upload-state`, defined in `shared/analysis/pipelines.yaml`. The batch is shared by related paragraphs and runs once per make invocation.
Existing generator commands (the batch explicitly sets CACHED=1 by default):
- `make cmpu-upload-entity-state-change-distributions CACHED=1`

Retained input folders and ownership:
- `targets/all-upload-state-change-delays/data/`

Dates and cohort parameters are preserved from the source manifests and the existing generator defaults. Financial/contact defaults use May 1 through July 31, 2026, with follow-up observed through October 28; upload/prescription analyses retain their August 15 through October 14 study and documented upload/cancellation cutoffs. Do not mix source snapshots.

Shared dependencies:
- `shared/analysis`
- `shared/artifact-ownership.yaml`
- `shared/paths.py`


### Outputs

Generated content: `targets/aged-upload-state-change-delays/outputs/latex/content.tex`.
Tables are exported to `outputs/tables/table.org` and read back to assemble LaTeX. The compatibility adapter retains cell formatting from the validated legacy renderer; `outputs/tables/provenance.json` records the source and Org fingerprints. Figures and diagrams are copied from their newly regenerated canonical exports. Logs are under the batch owner's `outputs/build/` folder.
Data and outputs are ignored by Git. `shared/artifact-ownership.yaml` maps historical dataset paths to target-owned locations. Existing legacy paths remain compatibility aliases.

## accepted-upload-approval-time: How long does it take for an accepted prescription document to get approved?



### Ownership

Target: `accepted-upload-approval-time`. Level: `subsubsection`.
Parent: `upload-processing-delays`.
Ordered children: `accepted-upload-approval-delay`.


### Reproduction commands

Run from the repository root with the project environment installed:
```sh
make accepted-upload-approval-time
make accepted-upload-approval-time REPRO=1
make accepted-upload-approval-time REFRESH=1
```
Default builds reuse retained source data and rerun the validation and presentation steps. They do not query the warehouse. Missing or stale inputs stop the build; inspect the pipeline log before requesting refresh. REFRESH=1 is explicit and may change results.


### Inputs and dependencies

The child make targets above are actual prerequisites. Parent prose is in `src/latex/body.tex` and may appear before, between and after the ordered children.

Shared dependencies:
- `shared/analysis`
- `shared/artifact-ownership.yaml`
- `shared/paths.py`


### Outputs

Generated content: `targets/accepted-upload-approval-time/outputs/latex/content.tex`.
Data and outputs are ignored by Git. `shared/artifact-ownership.yaml` maps historical dataset paths to target-owned locations. Existing legacy paths remain compatibility aliases.

## accepted-upload-approval-delay: How long after an accepted upload is the prescription approved?



### Ownership

Target: `accepted-upload-approval-delay`. Level: `paragraph`.
Parent: `accepted-upload-approval-time`.
Ordered children: none.


### Reproduction commands

Run from the repository root with the project environment installed:
```sh
make accepted-upload-approval-delay
make accepted-upload-approval-delay REPRO=1
make accepted-upload-approval-delay REFRESH=1
```
Default builds reuse retained source data and rerun the validation and presentation steps. They do not query the warehouse. Missing or stale inputs stop the build; inspect the pipeline log before requesting refresh. REFRESH=1 is explicit and may change results.


### Inputs and dependencies

Generator batch: `upload-approval`, defined in `shared/analysis/pipelines.yaml`. The batch is shared by related paragraphs and runs once per make invocation.
Existing generator commands (the batch explicitly sets CACHED=1 by default):
- `make cmpu-upload-to-approval-distribution CACHED=1`

Retained input folders and ownership:
- `targets/accepted-upload-approval-delay/data/`
- `targets/first-order-upload-status-flow/data/`

Dates and cohort parameters are preserved from the source manifests and the existing generator defaults. Financial/contact defaults use May 1 through July 31, 2026, with follow-up observed through October 28; upload/prescription analyses retain their August 15 through October 14 study and documented upload/cancellation cutoffs. Do not mix source snapshots.
- `targets/accepted-upload-approval-delay/src/python/create_cmpu_first_order_line_approval_distribution.py`
- `targets/accepted-upload-approval-delay/src/sql/cmpu_first_order_line_approval_distribution.sql`

Imported analysis dependencies:
- `shared/runtime.py`, `shared/prescription_uploads.py` and `shared/sankey.py`
- `shared/python/markdown_tables.py`

Shared dependencies:
- `shared/analysis`
- `shared/artifact-ownership.yaml`
- `shared/paths.py`
- `shared/python/__init__.py`
- `shared/runtime.py`, `shared/prescription_uploads.py` and `shared/sankey.py`
- `shared/python/markdown_tables.py`
- `shared/source-ownership.yaml`
- `shared/sql_templates.py`


### Outputs

Generated content: `targets/accepted-upload-approval-delay/outputs/latex/content.tex`.
Tables are exported to `outputs/tables/table.org` and read back to assemble LaTeX. The compatibility adapter retains cell formatting from the validated legacy renderer; `outputs/tables/provenance.json` records the source and Org fingerprints. Figures and diagrams are copied from their newly regenerated canonical exports. Logs are under the batch owner's `outputs/build/` folder.
Data and outputs are ignored by Git. `shared/artifact-ownership.yaml` maps historical dataset paths to target-owned locations. Existing legacy paths remain compatibility aliases.


### Additional target-owned source

- `targets/accepted-upload-approval-delay/src/sql/cmpu_upload_to_max_approval_extract.sql`

## aged-order-risk: What is the probability that after X days the order will be an aged order?



### Ownership

Target: `aged-order-risk`. Level: `subsection`.
Parent: `appendix`.
Ordered children: `first-order-event-free-survival`.


### Reproduction commands

Run from the repository root with the project environment installed:
```sh
make aged-order-risk
make aged-order-risk REPRO=1
make aged-order-risk REFRESH=1
```
Default builds reuse retained source data and rerun the validation and presentation steps. They do not query the warehouse. Missing or stale inputs stop the build; inspect the pipeline log before requesting refresh. REFRESH=1 is explicit and may change results.


### Inputs and dependencies

The child make targets above are actual prerequisites. Parent prose is in `src/latex/body.tex` and may appear before, between and after the ordered children.

Shared dependencies:
- `shared/analysis`
- `shared/artifact-ownership.yaml`
- `shared/paths.py`


### Outputs

Generated content: `targets/aged-order-risk/outputs/latex/content.tex`.
Data and outputs are ignored by Git. `shared/artifact-ownership.yaml` maps historical dataset paths to target-owned locations. Existing legacy paths remain compatibility aliases.

## first-order-event-free-survival: How long do first-order lines remain without an accepted upload or cancellation?



### Ownership

Target: `first-order-event-free-survival`. Level: `subsubsection`.
Parent: `aged-order-risk`.
Ordered children: `first-order-survival-curve`.


### Reproduction commands

Run from the repository root with the project environment installed:
```sh
make first-order-event-free-survival
make first-order-event-free-survival REPRO=1
make first-order-event-free-survival REFRESH=1
```
Default builds reuse retained source data and rerun the validation and presentation steps. They do not query the warehouse. Missing or stale inputs stop the build; inspect the pipeline log before requesting refresh. REFRESH=1 is explicit and may change results.


### Inputs and dependencies

The child make targets above are actual prerequisites. Parent prose is in `src/latex/body.tex` and may appear before, between and after the ordered children.

Shared dependencies:
- `shared/analysis`
- `shared/artifact-ownership.yaml`
- `shared/paths.py`


### Outputs

Generated content: `targets/first-order-event-free-survival/outputs/latex/content.tex`.
Data and outputs are ignored by Git. `shared/artifact-ownership.yaml` maps historical dataset paths to target-owned locations. Existing legacy paths remain compatibility aliases.

## first-order-survival-curve: What proportion of first-order lines remain without an accepted upload or cancellation over time?



### Ownership

Target: `first-order-survival-curve`. Level: `paragraph`.
Parent: `first-order-event-free-survival`.
Ordered children: none.


### Reproduction commands

Run from the repository root with the project environment installed:
```sh
make first-order-survival-curve
make first-order-survival-curve REPRO=1
make first-order-survival-curve REFRESH=1
```
Default builds reuse retained source data and rerun the validation and presentation steps. They do not query the warehouse. Missing or stale inputs stop the build; inspect the pipeline log before requesting refresh. REFRESH=1 is explicit and may change results.


### Inputs and dependencies

Generator batch: `survival`, defined in `shared/analysis/pipelines.yaml`. The batch is shared by related paragraphs and runs once per make invocation.
Existing generator commands (the batch explicitly sets CACHED=1 by default):
- `make cmpu-first-order-line-survival CACHED=1`

Retained input folders and ownership:
- `targets/first-order-survival-curve/data/`

Dates and cohort parameters are preserved from the source manifests and the existing generator defaults. Financial/contact defaults use May 1 through July 31, 2026, with follow-up observed through October 28; upload/prescription analyses retain their August 15 through October 14 study and documented upload/cancellation cutoffs. Do not mix source snapshots.
- `targets/first-order-survival-curve/src/python/create_cmpu_first_order_line_survival.py`

Imported analysis dependencies:
- `targets/first-order-survival-curve/src/python/create_cmpu_first_order_line_event_times.py`
- `shared/runtime.py`, `shared/prescription_uploads.py` and `shared/sankey.py`
- `shared/python/markdown_tables.py`

Shared dependencies:
- `shared/analysis`
- `shared/artifact-ownership.yaml`
- `shared/paths.py`
- `shared/python/__init__.py`
- `targets/first-order-survival-curve/src/python/create_cmpu_first_order_line_event_times.py`
- `shared/runtime.py`, `shared/prescription_uploads.py` and `shared/sankey.py`
- `shared/python/markdown_tables.py`
- `shared/source-ownership.yaml`
- `shared/sql_templates.py`


### Outputs

Generated content: `targets/first-order-survival-curve/outputs/latex/content.tex`.
Tables are exported to `outputs/tables/table.org` and read back to assemble LaTeX. The compatibility adapter retains cell formatting from the validated legacy renderer; `outputs/tables/provenance.json` records the source and Org fingerprints. Figures and diagrams are copied from their newly regenerated canonical exports. Logs are under the batch owner's `outputs/build/` folder.
Data and outputs are ignored by Git. `shared/artifact-ownership.yaml` maps historical dataset paths to target-owned locations. Existing legacy paths remain compatibility aliases.


### Additional target-owned source

- `targets/first-order-survival-curve/src/sql/cmpu_first_order_line_event_times.sql`

## data-verification: How did we verify the data?



### Ownership

Target: `data-verification`. Level: `subsection`.
Parent: `appendix`.
Ordered children: `upload-source-origins`, `upload-approval-channel-distribution`, `upload-coverage-by-rx-status`, `upload-order-cancellation-distribution`, `null-resource-order-cancellations`, `data-source-connections`.


### Reproduction commands

Run from the repository root with the project environment installed:
```sh
make data-verification
make data-verification REPRO=1
make data-verification REFRESH=1
```
Default builds reuse retained source data and rerun the validation and presentation steps. They do not query the warehouse. Missing or stale inputs stop the build; inspect the pipeline log before requesting refresh. REFRESH=1 is explicit and may change results.


### Inputs and dependencies

The child make targets above are actual prerequisites. Parent prose is in `src/latex/body.tex` and may appear before, between and after the ordered children.

Shared dependencies:
- `shared/analysis`
- `shared/artifact-ownership.yaml`
- `shared/paths.py`


### Outputs

Generated content: `targets/data-verification/outputs/latex/content.tex`.
Data and outputs are ignored by Git. `shared/artifact-ownership.yaml` maps historical dataset paths to target-owned locations. Existing legacy paths remain compatibility aliases.

## upload-source-origins: Where is the prescription upload data coming from?



### Ownership

Target: `upload-source-origins`. Level: `subsubsection`.
Parent: `data-verification`.
Ordered children: `upload-resource-types`, `upload-source-date-coverage`.


### Reproduction commands

Run from the repository root with the project environment installed:
```sh
make upload-source-origins
make upload-source-origins REPRO=1
make upload-source-origins REFRESH=1
```
Default builds reuse retained source data and rerun the validation and presentation steps. They do not query the warehouse. Missing or stale inputs stop the build; inspect the pipeline log before requesting refresh. REFRESH=1 is explicit and may change results.


### Inputs and dependencies

The child make targets above are actual prerequisites. Parent prose is in `src/latex/body.tex` and may appear before, between and after the ordered children.

Shared dependencies:
- `shared/analysis`
- `shared/artifact-ownership.yaml`
- `shared/paths.py`


### Outputs

Generated content: `targets/upload-source-origins/outputs/latex/content.tex`.
Data and outputs are ignored by Git. `shared/artifact-ownership.yaml` maps historical dataset paths to target-owned locations. Existing legacy paths remain compatibility aliases.

## upload-resource-types: How many upload-source entries have prescription IDs for each associated resource type?



### Ownership

Target: `upload-resource-types`. Level: `paragraph`.
Parent: `upload-source-origins`.
Ordered children: none.


### Reproduction commands

Run from the repository root with the project environment installed:
```sh
make upload-resource-types
make upload-resource-types REPRO=1
make upload-resource-types REFRESH=1
```
Default builds reuse retained source data and rerun the validation and presentation steps. They do not query the warehouse. Missing or stale inputs stop the build; inspect the pipeline log before requesting refresh. REFRESH=1 is explicit and may change results.


### Inputs and dependencies

Generator batch: `verification`, defined in `shared/analysis/pipelines.yaml`. The batch is shared by related paragraphs and runs once per make invocation.
Existing generator commands (the batch explicitly sets CACHED=1 by default):
- `make upload-data-verification-all CACHED=1`

Retained input folders and ownership:
- `targets/upload-resource-types/data/`
- `targets/upload-source-date-coverage/data/`
- `targets/uploaded-prescription-approval-channels/data/`
- `targets/customer-upload-rx-status-coverage/data/`
- `targets/uploaded-order-cancellation-reasons/data/`
- `targets/null-resource-cancellation-reasons/data/`

Dates and cohort parameters are preserved from the source manifests and the existing generator defaults. Financial/contact defaults use May 1 through July 31, 2026, with follow-up observed through October 28; upload/prescription analyses retain their August 15 through October 14 study and documented upload/cancellation cutoffs. Do not mix source snapshots.
- `targets/upload-resource-types/src/python/create_upload_data_verification.py`
- `targets/upload-resource-types/src/sql/upload_data_verification.sql`
- `targets/upload-resource-types/src/sql/upload_data_verification_rx_ids_validation.sql`

Imported analysis dependencies:
- `shared/python/markdown_tables.py`
- `shared/python/opportunity_report_tables.py`
- `targets/cancellation-sales-baseline/src/python/create_opportunity_order_cancellation_summary.py`

Shared dependencies:
- `shared/analysis`
- `shared/artifact-ownership.yaml`
- `shared/paths.py`
- `shared/python/__init__.py`
- `shared/python/markdown_tables.py`
- `shared/python/opportunity_report_tables.py`
- `shared/source-ownership.yaml`
- `shared/sql_templates.py`


### Outputs

Generated content: `targets/upload-resource-types/outputs/latex/content.tex`.
Tables are exported to `outputs/tables/table.org` and read back to assemble LaTeX. The compatibility adapter retains cell formatting from the validated legacy renderer; `outputs/tables/provenance.json` records the source and Org fingerprints. Figures and diagrams are copied from their newly regenerated canonical exports. Logs are under the batch owner's `outputs/build/` folder.
Data and outputs are ignored by Git. `shared/artifact-ownership.yaml` maps historical dataset paths to target-owned locations. Existing legacy paths remain compatibility aliases.

## upload-source-date-coverage: What creation-date ranges do the upload sources cover?



### Ownership

Target: `upload-source-date-coverage`. Level: `paragraph`.
Parent: `upload-source-origins`.
Ordered children: none.


### Reproduction commands

Run from the repository root with the project environment installed:
```sh
make upload-source-date-coverage
make upload-source-date-coverage REPRO=1
make upload-source-date-coverage REFRESH=1
```
Default builds reuse retained source data and rerun the validation and presentation steps. They do not query the warehouse. Missing or stale inputs stop the build; inspect the pipeline log before requesting refresh. REFRESH=1 is explicit and may change results.


### Inputs and dependencies

Generator batch: `verification`, defined in `shared/analysis/pipelines.yaml`. The batch is shared by related paragraphs and runs once per make invocation.
Existing generator commands (the batch explicitly sets CACHED=1 by default):
- `make upload-data-verification-all CACHED=1`

Retained input folders and ownership:
- `targets/upload-resource-types/data/`
- `targets/upload-source-date-coverage/data/`
- `targets/uploaded-prescription-approval-channels/data/`
- `targets/customer-upload-rx-status-coverage/data/`
- `targets/uploaded-order-cancellation-reasons/data/`
- `targets/null-resource-cancellation-reasons/data/`

Dates and cohort parameters are preserved from the source manifests and the existing generator defaults. Financial/contact defaults use May 1 through July 31, 2026, with follow-up observed through October 28; upload/prescription analyses retain their August 15 through October 14 study and documented upload/cancellation cutoffs. Do not mix source snapshots.
- `targets/upload-source-date-coverage/src/python/analyze_upload_source_time_coverage.py`
- `targets/upload-source-date-coverage/src/sql/upload_source_time_coverage.sql`

Imported analysis dependencies:
- `shared/python/markdown_tables.py`
- `shared/python/opportunity_report_tables.py`
- `targets/cancellation-sales-baseline/src/python/create_opportunity_order_cancellation_summary.py`
- `targets/upload-resource-types/src/python/create_upload_data_verification.py`

Shared dependencies:
- `shared/analysis`
- `shared/artifact-ownership.yaml`
- `shared/paths.py`
- `shared/python/__init__.py`
- `shared/python/markdown_tables.py`
- `shared/python/opportunity_report_tables.py`
- `shared/source-ownership.yaml`
- `shared/sql_templates.py`


### Outputs

Generated content: `targets/upload-source-date-coverage/outputs/latex/content.tex`.
Tables are exported to `outputs/tables/table.org` and read back to assemble LaTeX. The compatibility adapter retains cell formatting from the validated legacy renderer; `outputs/tables/provenance.json` records the source and Org fingerprints. Figures and diagrams are copied from their newly regenerated canonical exports. Logs are under the batch owner's `outputs/build/` folder.
Data and outputs are ignored by Git. `shared/artifact-ownership.yaml` maps historical dataset paths to target-owned locations. Existing legacy paths remain compatibility aliases.

## upload-approval-channel-distribution: What's the distribution of all the vet diet prescriptions in the prescription upload tables by \texttt{APPROVAL\_CHANNEL} ?



### Ownership

Target: `upload-approval-channel-distribution`. Level: `subsubsection`.
Parent: `data-verification`.
Ordered children: `uploaded-prescription-approval-channels`.


### Reproduction commands

Run from the repository root with the project environment installed:
```sh
make upload-approval-channel-distribution
make upload-approval-channel-distribution REPRO=1
make upload-approval-channel-distribution REFRESH=1
```
Default builds reuse retained source data and rerun the validation and presentation steps. They do not query the warehouse. Missing or stale inputs stop the build; inspect the pipeline log before requesting refresh. REFRESH=1 is explicit and may change results.


### Inputs and dependencies

The child make targets above are actual prerequisites. Parent prose is in `src/latex/body.tex` and may appear before, between and after the ordered children.

Shared dependencies:
- `shared/analysis`
- `shared/artifact-ownership.yaml`
- `shared/paths.py`


### Outputs

Generated content: `targets/upload-approval-channel-distribution/outputs/latex/content.tex`.
Data and outputs are ignored by Git. `shared/artifact-ownership.yaml` maps historical dataset paths to target-owned locations. Existing legacy paths remain compatibility aliases.

## uploaded-prescription-approval-channels: How are approval channels distributed among distinct uploaded vet-diet prescriptions?



### Ownership

Target: `uploaded-prescription-approval-channels`. Level: `paragraph`.
Parent: `upload-approval-channel-distribution`.
Ordered children: none.


### Reproduction commands

Run from the repository root with the project environment installed:
```sh
make uploaded-prescription-approval-channels
make uploaded-prescription-approval-channels REPRO=1
make uploaded-prescription-approval-channels REFRESH=1
```
Default builds reuse retained source data and rerun the validation and presentation steps. They do not query the warehouse. Missing or stale inputs stop the build; inspect the pipeline log before requesting refresh. REFRESH=1 is explicit and may change results.


### Inputs and dependencies

Generator batch: `verification`, defined in `shared/analysis/pipelines.yaml`. The batch is shared by related paragraphs and runs once per make invocation.
Existing generator commands (the batch explicitly sets CACHED=1 by default):
- `make upload-data-verification-all CACHED=1`

Retained input folders and ownership:
- `targets/upload-resource-types/data/`
- `targets/upload-source-date-coverage/data/`
- `targets/uploaded-prescription-approval-channels/data/`
- `targets/customer-upload-rx-status-coverage/data/`
- `targets/uploaded-order-cancellation-reasons/data/`
- `targets/null-resource-cancellation-reasons/data/`

Dates and cohort parameters are preserved from the source manifests and the existing generator defaults. Financial/contact defaults use May 1 through July 31, 2026, with follow-up observed through October 28; upload/prescription analyses retain their August 15 through October 14 study and documented upload/cancellation cutoffs. Do not mix source snapshots.
- `targets/uploaded-prescription-approval-channels/src/python/analyze_upload_vet_diet_approval_channels.py`
- `targets/uploaded-prescription-approval-channels/src/sql/upload_vet_diet_approval_channels.sql`
- `targets/uploaded-prescription-approval-channels/src/sql/upload_vet_diet_approval_channels_validation.sql`

Imported analysis dependencies:
- `shared/python/markdown_tables.py`
- `shared/python/opportunity_report_tables.py`
- `targets/cancellation-sales-baseline/src/python/create_opportunity_order_cancellation_summary.py`
- `targets/upload-resource-types/src/python/create_upload_data_verification.py`

Shared dependencies:
- `shared/analysis`
- `shared/artifact-ownership.yaml`
- `shared/paths.py`
- `shared/python/__init__.py`
- `shared/python/markdown_tables.py`
- `shared/python/opportunity_report_tables.py`
- `shared/source-ownership.yaml`
- `shared/sql_templates.py`


### Outputs

Generated content: `targets/uploaded-prescription-approval-channels/outputs/latex/content.tex`.
Tables are exported to `outputs/tables/table.org` and read back to assemble LaTeX. The compatibility adapter retains cell formatting from the validated legacy renderer; `outputs/tables/provenance.json` records the source and Org fingerprints. Figures and diagrams are copied from their newly regenerated canonical exports. Logs are under the batch owner's `outputs/build/` folder.
Data and outputs are ignored by Git. `shared/artifact-ownership.yaml` maps historical dataset paths to target-owned locations. Existing legacy paths remain compatibility aliases.

## upload-coverage-by-rx-status: What is the coverage of vet diet prescriptions with \texttt{APPROVAL\_CHANNEL = CUSTOMER\_UPLOAD}, by \texttt{RX\_STATUS}?



### Ownership

Target: `upload-coverage-by-rx-status`. Level: `subsubsection`.
Parent: `data-verification`.
Ordered children: `customer-upload-rx-status-coverage`.


### Reproduction commands

Run from the repository root with the project environment installed:
```sh
make upload-coverage-by-rx-status
make upload-coverage-by-rx-status REPRO=1
make upload-coverage-by-rx-status REFRESH=1
```
Default builds reuse retained source data and rerun the validation and presentation steps. They do not query the warehouse. Missing or stale inputs stop the build; inspect the pipeline log before requesting refresh. REFRESH=1 is explicit and may change results.


### Inputs and dependencies

The child make targets above are actual prerequisites. Parent prose is in `src/latex/body.tex` and may appear before, between and after the ordered children.

Shared dependencies:
- `shared/analysis`
- `shared/artifact-ownership.yaml`
- `shared/paths.py`


### Outputs

Generated content: `targets/upload-coverage-by-rx-status/outputs/latex/content.tex`.
Data and outputs are ignored by Git. `shared/artifact-ownership.yaml` maps historical dataset paths to target-owned locations. Existing legacy paths remain compatibility aliases.

## customer-upload-rx-status-coverage: How does upload-source coverage vary by prescription source and status for customer-upload vet-diet prescriptions?



### Ownership

Target: `customer-upload-rx-status-coverage`. Level: `paragraph`.
Parent: `upload-coverage-by-rx-status`.
Ordered children: none.


### Reproduction commands

Run from the repository root with the project environment installed:
```sh
make customer-upload-rx-status-coverage
make customer-upload-rx-status-coverage REPRO=1
make customer-upload-rx-status-coverage REFRESH=1
```
Default builds reuse retained source data and rerun the validation and presentation steps. They do not query the warehouse. Missing or stale inputs stop the build; inspect the pipeline log before requesting refresh. REFRESH=1 is explicit and may change results.


### Inputs and dependencies

Generator batch: `verification`, defined in `shared/analysis/pipelines.yaml`. The batch is shared by related paragraphs and runs once per make invocation.
Existing generator commands (the batch explicitly sets CACHED=1 by default):
- `make upload-data-verification-all CACHED=1`

Retained input folders and ownership:
- `targets/upload-resource-types/data/`
- `targets/upload-source-date-coverage/data/`
- `targets/uploaded-prescription-approval-channels/data/`
- `targets/customer-upload-rx-status-coverage/data/`
- `targets/uploaded-order-cancellation-reasons/data/`
- `targets/null-resource-cancellation-reasons/data/`

Dates and cohort parameters are preserved from the source manifests and the existing generator defaults. Financial/contact defaults use May 1 through July 31, 2026, with follow-up observed through October 28; upload/prescription analyses retain their August 15 through October 14 study and documented upload/cancellation cutoffs. Do not mix source snapshots.
- `targets/customer-upload-rx-status-coverage/src/python/analyze_cmpu_approved_prescription_upload_coverage.py`
- `targets/customer-upload-rx-status-coverage/src/sql/cmpu_approved_prescription_upload_coverage.sql`
- `targets/customer-upload-rx-status-coverage/src/sql/cmpu_approved_prescription_upload_coverage_validation.sql`

Imported analysis dependencies:
- `shared/python/markdown_tables.py`
- `shared/python/opportunity_report_tables.py`
- `targets/cancellation-sales-baseline/src/python/create_opportunity_order_cancellation_summary.py`
- `targets/upload-resource-types/src/python/create_upload_data_verification.py`

Shared dependencies:
- `shared/analysis`
- `shared/artifact-ownership.yaml`
- `shared/paths.py`
- `shared/python/__init__.py`
- `shared/python/markdown_tables.py`
- `shared/python/opportunity_report_tables.py`
- `shared/source-ownership.yaml`
- `shared/sql_templates.py`


### Outputs

Generated content: `targets/customer-upload-rx-status-coverage/outputs/latex/content.tex`.
Tables are exported to `outputs/tables/table.org` and read back to assemble LaTeX. The compatibility adapter retains cell formatting from the validated legacy renderer; `outputs/tables/provenance.json` records the source and Org fingerprints. Figures and diagrams are copied from their newly regenerated canonical exports. Logs are under the batch owner's `outputs/build/` folder.
Data and outputs are ignored by Git. `shared/artifact-ownership.yaml` maps historical dataset paths to target-owned locations. Existing legacy paths remain compatibility aliases.

## upload-order-cancellation-distribution: What is the distribution of order cancellation reasons in the prescription upload tables?



### Ownership

Target: `upload-order-cancellation-distribution`. Level: `subsubsection`.
Parent: `data-verification`.
Ordered children: `uploaded-order-cancellation-reasons`.


### Reproduction commands

Run from the repository root with the project environment installed:
```sh
make upload-order-cancellation-distribution
make upload-order-cancellation-distribution REPRO=1
make upload-order-cancellation-distribution REFRESH=1
```
Default builds reuse retained source data and rerun the validation and presentation steps. They do not query the warehouse. Missing or stale inputs stop the build; inspect the pipeline log before requesting refresh. REFRESH=1 is explicit and may change results.


### Inputs and dependencies

The child make targets above are actual prerequisites. Parent prose is in `src/latex/body.tex` and may appear before, between and after the ordered children.

Shared dependencies:
- `shared/analysis`
- `shared/artifact-ownership.yaml`
- `shared/paths.py`


### Outputs

Generated content: `targets/upload-order-cancellation-distribution/outputs/latex/content.tex`.
Data and outputs are ignored by Git. `shared/artifact-ownership.yaml` maps historical dataset paths to target-owned locations. Existing legacy paths remain compatibility aliases.

## uploaded-order-cancellation-reasons: How are cancellation reasons distributed among orders associated with vet-diet uploads?



### Ownership

Target: `uploaded-order-cancellation-reasons`. Level: `paragraph`.
Parent: `upload-order-cancellation-distribution`.
Ordered children: none.


### Reproduction commands

Run from the repository root with the project environment installed:
```sh
make uploaded-order-cancellation-reasons
make uploaded-order-cancellation-reasons REPRO=1
make uploaded-order-cancellation-reasons REFRESH=1
```
Default builds reuse retained source data and rerun the validation and presentation steps. They do not query the warehouse. Missing or stale inputs stop the build; inspect the pipeline log before requesting refresh. REFRESH=1 is explicit and may change results.


### Inputs and dependencies

Generator batch: `verification`, defined in `shared/analysis/pipelines.yaml`. The batch is shared by related paragraphs and runs once per make invocation.
Existing generator commands (the batch explicitly sets CACHED=1 by default):
- `make upload-data-verification-all CACHED=1`

Retained input folders and ownership:
- `targets/upload-resource-types/data/`
- `targets/upload-source-date-coverage/data/`
- `targets/uploaded-prescription-approval-channels/data/`
- `targets/customer-upload-rx-status-coverage/data/`
- `targets/uploaded-order-cancellation-reasons/data/`
- `targets/null-resource-cancellation-reasons/data/`

Dates and cohort parameters are preserved from the source manifests and the existing generator defaults. Financial/contact defaults use May 1 through July 31, 2026, with follow-up observed through October 28; upload/prescription analyses retain their August 15 through October 14 study and documented upload/cancellation cutoffs. Do not mix source snapshots.
- `targets/uploaded-order-cancellation-reasons/src/python/analyze_diet_upload_source_orders.py`
- `targets/uploaded-order-cancellation-reasons/src/sql/diet_upload_linked_orders.sql`
- `targets/uploaded-order-cancellation-reasons/src/sql/diet_upload_source_orders.sql`
- `targets/uploaded-order-cancellation-reasons/src/sql/diet_upload_source_orders_validation.sql`

Imported analysis dependencies:
- `shared/python/markdown_tables.py`
- `shared/python/opportunity_report_tables.py`
- `targets/cancellation-sales-baseline/src/python/create_opportunity_order_cancellation_summary.py`
- `targets/null-resource-cancellation-reasons/src/python/analyze_null_resource_uploads.py`
- `targets/upload-resource-types/src/python/create_upload_data_verification.py`

Shared dependencies:
- `shared/analysis`
- `shared/artifact-ownership.yaml`
- `shared/paths.py`
- `shared/python/__init__.py`
- `shared/python/markdown_tables.py`
- `shared/python/opportunity_report_tables.py`
- `shared/source-ownership.yaml`
- `shared/sql_templates.py`


### Outputs

Generated content: `targets/uploaded-order-cancellation-reasons/outputs/latex/content.tex`.
Tables are exported to `outputs/tables/table.org` and read back to assemble LaTeX. The compatibility adapter retains cell formatting from the validated legacy renderer; `outputs/tables/provenance.json` records the source and Org fingerprints. Figures and diagrams are copied from their newly regenerated canonical exports. Logs are under the batch owner's `outputs/build/` folder.
Data and outputs are ignored by Git. `shared/artifact-ownership.yaml` maps historical dataset paths to target-owned locations. Existing legacy paths remain compatibility aliases.

## null-resource-order-cancellations: What are the order cancellation reasons for null associated resource type entries in the rxp\_notification\_service.\texorpdfstring{\allowbreak}{}upload\_entity table?



### Ownership

Target: `null-resource-order-cancellations`. Level: `subsubsection`.
Parent: `data-verification`.
Ordered children: `null-resource-cancellation-reasons`.


### Reproduction commands

Run from the repository root with the project environment installed:
```sh
make null-resource-order-cancellations
make null-resource-order-cancellations REPRO=1
make null-resource-order-cancellations REFRESH=1
```
Default builds reuse retained source data and rerun the validation and presentation steps. They do not query the warehouse. Missing or stale inputs stop the build; inspect the pipeline log before requesting refresh. REFRESH=1 is explicit and may change results.


### Inputs and dependencies

The child make targets above are actual prerequisites. Parent prose is in `src/latex/body.tex` and may appear before, between and after the ordered children.

Shared dependencies:
- `shared/analysis`
- `shared/artifact-ownership.yaml`
- `shared/paths.py`


### Outputs

Generated content: `targets/null-resource-order-cancellations/outputs/latex/content.tex`.
Data and outputs are ignored by Git. `shared/artifact-ownership.yaml` maps historical dataset paths to target-owned locations. Existing legacy paths remain compatibility aliases.

## null-resource-cancellation-reasons: How are cancellation reasons distributed among orders referenced by uploads with no associated resource type?



### Ownership

Target: `null-resource-cancellation-reasons`. Level: `paragraph`.
Parent: `null-resource-order-cancellations`.
Ordered children: none.


### Reproduction commands

Run from the repository root with the project environment installed:
```sh
make null-resource-cancellation-reasons
make null-resource-cancellation-reasons REPRO=1
make null-resource-cancellation-reasons REFRESH=1
```
Default builds reuse retained source data and rerun the validation and presentation steps. They do not query the warehouse. Missing or stale inputs stop the build; inspect the pipeline log before requesting refresh. REFRESH=1 is explicit and may change results.


### Inputs and dependencies

Generator batch: `verification`, defined in `shared/analysis/pipelines.yaml`. The batch is shared by related paragraphs and runs once per make invocation.
Existing generator commands (the batch explicitly sets CACHED=1 by default):
- `make upload-data-verification-all CACHED=1`

Retained input folders and ownership:
- `targets/upload-resource-types/data/`
- `targets/upload-source-date-coverage/data/`
- `targets/uploaded-prescription-approval-channels/data/`
- `targets/customer-upload-rx-status-coverage/data/`
- `targets/uploaded-order-cancellation-reasons/data/`
- `targets/null-resource-cancellation-reasons/data/`

Dates and cohort parameters are preserved from the source manifests and the existing generator defaults. Financial/contact defaults use May 1 through July 31, 2026, with follow-up observed through October 28; upload/prescription analyses retain their August 15 through October 14 study and documented upload/cancellation cutoffs. Do not mix source snapshots.
- `targets/null-resource-cancellation-reasons/src/python/analyze_null_resource_uploads.py`
- `targets/null-resource-cancellation-reasons/src/sql/null_resource_upload_context.sql`
- `targets/null-resource-cancellation-reasons/src/sql/null_resource_upload_orders.sql`
- `targets/null-resource-cancellation-reasons/src/sql/null_resource_upload_validation.sql`

Imported analysis dependencies:
- `shared/python/markdown_tables.py`
- `shared/python/opportunity_report_tables.py`
- `targets/cancellation-sales-baseline/src/python/create_opportunity_order_cancellation_summary.py`
- `targets/upload-resource-types/src/python/create_upload_data_verification.py`

Shared dependencies:
- `shared/analysis`
- `shared/artifact-ownership.yaml`
- `shared/paths.py`
- `shared/python/__init__.py`
- `shared/python/markdown_tables.py`
- `shared/python/opportunity_report_tables.py`
- `shared/source-ownership.yaml`
- `shared/sql_templates.py`


### Outputs

Generated content: `targets/null-resource-cancellation-reasons/outputs/latex/content.tex`.
Tables are exported to `outputs/tables/table.org` and read back to assemble LaTeX. The compatibility adapter retains cell formatting from the validated legacy renderer; `outputs/tables/provenance.json` records the source and Org fingerprints. Figures and diagrams are copied from their newly regenerated canonical exports. Logs are under the batch owner's `outputs/build/` folder.
Data and outputs are ignored by Git. `shared/artifact-ownership.yaml` maps historical dataset paths to target-owned locations. Existing legacy paths remain compatibility aliases.

## data-source-connections: How are data sources connected?



### Ownership

Target: `data-source-connections`. Level: `subsubsection`.
Parent: `data-verification`.
Ordered children: `report-source-overview`, `source-grains-and-counting`, `upload-verification-joins`, `prescription-first-order-joins`, `financial-reorder-contact-joins`, `contact-matching-rules`.


### Reproduction commands

Run from the repository root with the project environment installed:
```sh
make data-source-connections
make data-source-connections REPRO=1
make data-source-connections REFRESH=1
```
Default builds reuse retained source data and rerun the validation and presentation steps. They do not query the warehouse. Missing or stale inputs stop the build; inspect the pipeline log before requesting refresh. REFRESH=1 is explicit and may change results.


### Inputs and dependencies

The child make targets above are actual prerequisites. Parent prose is in `src/latex/body.tex` and may appear before, between and after the ordered children.

Shared dependencies:
- `shared/analysis`
- `shared/artifact-ownership.yaml`
- `shared/paths.py`


### Outputs

Generated content: `targets/data-source-connections/outputs/latex/content.tex`.
Data and outputs are ignored by Git. `shared/artifact-ownership.yaml` maps historical dataset paths to target-owned locations. Existing legacy paths remain compatibility aliases.

## report-source-overview: How do the report’s source tables and analyses connect?



### Ownership

Target: `report-source-overview`. Level: `paragraph`.
Parent: `data-source-connections`.
Ordered children: none.


### Reproduction commands

Run from the repository root with the project environment installed:
```sh
make report-source-overview
make report-source-overview REPRO=1
make report-source-overview REFRESH=1
```
Default builds reuse retained source data and rerun the validation and presentation steps. They do not query the warehouse. Missing or stale inputs stop the build; inspect the pipeline log before requesting refresh. REFRESH=1 is explicit and may change results.


### Inputs and dependencies

Generator batch: `diagrams`, defined in `shared/analysis/pipelines.yaml`. The batch is shared by related paragraphs and runs once per make invocation.
Existing generator commands (the batch explicitly sets CACHED=1 by default):
- `make data-source-diagrams CACHED=1`

Retained input folders and ownership:

Dates and cohort parameters are preserved from the source manifests and the existing generator defaults. Financial/contact defaults use May 1 through July 31, 2026, with follow-up observed through October 28; upload/prescription analyses retain their August 15 through October 14 study and documented upload/cancellation cutoffs. Do not mix source snapshots.
- `targets/report-source-overview/src/mermaid/connections.mmd`

Shared dependencies:
- `shared/analysis`
- `shared/artifact-ownership.yaml`
- `shared/paths.py`
- `shared/python/__init__.py`
- `shared/source-ownership.yaml`
- `shared/sql_templates.py`


### Outputs

Generated content: `targets/report-source-overview/outputs/latex/content.tex`.
Tables are exported to `outputs/tables/table.org` and read back to assemble LaTeX. The compatibility adapter retains cell formatting from the validated legacy renderer; `outputs/tables/provenance.json` records the source and Org fingerprints. Figures and diagrams are copied from their newly regenerated canonical exports. Logs are under the batch owner's `outputs/build/` folder.
Data and outputs are ignored by Git. `shared/artifact-ownership.yaml` maps historical dataset paths to target-owned locations. Existing legacy paths remain compatibility aliases.

## source-grains-and-counting: What is the grain and counting unit of each source?



### Ownership

Target: `source-grains-and-counting`. Level: `paragraph`.
Parent: `data-source-connections`.
Ordered children: none.


### Reproduction commands

Run from the repository root with the project environment installed:
```sh
make source-grains-and-counting
make source-grains-and-counting REPRO=1
make source-grains-and-counting REFRESH=1
```
Default builds reuse retained source data and rerun the validation and presentation steps. They do not query the warehouse. Missing or stale inputs stop the build; inspect the pipeline log before requesting refresh. REFRESH=1 is explicit and may change results.


### Inputs and dependencies

Generator batch: `diagrams`, defined in `shared/analysis/pipelines.yaml`. The batch is shared by related paragraphs and runs once per make invocation.
Existing generator commands (the batch explicitly sets CACHED=1 by default):
- `make data-source-diagrams CACHED=1`

Retained input folders and ownership:

Dates and cohort parameters are preserved from the source manifests and the existing generator defaults. Financial/contact defaults use May 1 through July 31, 2026, with follow-up observed through October 28; upload/prescription analyses retain their August 15 through October 14 study and documented upload/cancellation cutoffs. Do not mix source snapshots.

Shared dependencies:
- `shared/analysis`
- `shared/artifact-ownership.yaml`
- `shared/paths.py`


### Outputs

Generated content: `targets/source-grains-and-counting/outputs/latex/content.tex`.
Tables are exported to `outputs/tables/table.org` and read back to assemble LaTeX. The compatibility adapter retains cell formatting from the validated legacy renderer; `outputs/tables/provenance.json` records the source and Org fingerprints. Figures and diagrams are copied from their newly regenerated canonical exports. Logs are under the batch owner's `outputs/build/` folder.
Data and outputs are ignored by Git. `shared/artifact-ownership.yaml` maps historical dataset paths to target-owned locations. Existing legacy paths remain compatibility aliases.

## upload-verification-joins: How are upload IDs expanded and matched to prescriptions and orders?



### Ownership

Target: `upload-verification-joins`. Level: `paragraph`.
Parent: `data-source-connections`.
Ordered children: none.


### Reproduction commands

Run from the repository root with the project environment installed:
```sh
make upload-verification-joins
make upload-verification-joins REPRO=1
make upload-verification-joins REFRESH=1
```
Default builds reuse retained source data and rerun the validation and presentation steps. They do not query the warehouse. Missing or stale inputs stop the build; inspect the pipeline log before requesting refresh. REFRESH=1 is explicit and may change results.


### Inputs and dependencies

Generator batch: `diagrams`, defined in `shared/analysis/pipelines.yaml`. The batch is shared by related paragraphs and runs once per make invocation.
Existing generator commands (the batch explicitly sets CACHED=1 by default):
- `make data-source-diagrams CACHED=1`

Retained input folders and ownership:

Dates and cohort parameters are preserved from the source manifests and the existing generator defaults. Financial/contact defaults use May 1 through July 31, 2026, with follow-up observed through October 28; upload/prescription analyses retain their August 15 through October 14 study and documented upload/cancellation cutoffs. Do not mix source snapshots.
- `targets/upload-verification-joins/src/mermaid/connections.mmd`

Shared dependencies:
- `shared/analysis`
- `shared/artifact-ownership.yaml`
- `shared/paths.py`
- `shared/python/__init__.py`
- `shared/source-ownership.yaml`
- `shared/sql_templates.py`


### Outputs

Generated content: `targets/upload-verification-joins/outputs/latex/content.tex`.
Tables are exported to `outputs/tables/table.org` and read back to assemble LaTeX. The compatibility adapter retains cell formatting from the validated legacy renderer; `outputs/tables/provenance.json` records the source and Org fingerprints. Figures and diagrams are copied from their newly regenerated canonical exports. Logs are under the batch owner's `outputs/build/` folder.
Data and outputs are ignored by Git. `shared/artifact-ownership.yaml` maps historical dataset paths to target-owned locations. Existing legacy paths remain compatibility aliases.

## prescription-first-order-joins: How are prescriptions matched to first-order lines and upload evidence?



### Ownership

Target: `prescription-first-order-joins`. Level: `paragraph`.
Parent: `data-source-connections`.
Ordered children: none.


### Reproduction commands

Run from the repository root with the project environment installed:
```sh
make prescription-first-order-joins
make prescription-first-order-joins REPRO=1
make prescription-first-order-joins REFRESH=1
```
Default builds reuse retained source data and rerun the validation and presentation steps. They do not query the warehouse. Missing or stale inputs stop the build; inspect the pipeline log before requesting refresh. REFRESH=1 is explicit and may change results.


### Inputs and dependencies

Generator batch: `diagrams`, defined in `shared/analysis/pipelines.yaml`. The batch is shared by related paragraphs and runs once per make invocation.
Existing generator commands (the batch explicitly sets CACHED=1 by default):
- `make data-source-diagrams CACHED=1`

Retained input folders and ownership:

Dates and cohort parameters are preserved from the source manifests and the existing generator defaults. Financial/contact defaults use May 1 through July 31, 2026, with follow-up observed through October 28; upload/prescription analyses retain their August 15 through October 14 study and documented upload/cancellation cutoffs. Do not mix source snapshots.
- `targets/prescription-first-order-joins/src/mermaid/connections.mmd`

Shared dependencies:
- `shared/analysis`
- `shared/artifact-ownership.yaml`
- `shared/paths.py`
- `shared/python/__init__.py`
- `shared/source-ownership.yaml`
- `shared/sql_templates.py`


### Outputs

Generated content: `targets/prescription-first-order-joins/outputs/latex/content.tex`.
Tables are exported to `outputs/tables/table.org` and read back to assemble LaTeX. The compatibility adapter retains cell formatting from the validated legacy renderer; `outputs/tables/provenance.json` records the source and Org fingerprints. Figures and diagrams are copied from their newly regenerated canonical exports. Logs are under the batch owner's `outputs/build/` folder.
Data and outputs are ignored by Git. `shared/artifact-ownership.yaml` maps historical dataset paths to target-owned locations. Existing legacy paths remain compatibility aliases.

## financial-reorder-contact-joins: How are financial lines, later orders, and customer contacts connected?



### Ownership

Target: `financial-reorder-contact-joins`. Level: `paragraph`.
Parent: `data-source-connections`.
Ordered children: none.


### Reproduction commands

Run from the repository root with the project environment installed:
```sh
make financial-reorder-contact-joins
make financial-reorder-contact-joins REPRO=1
make financial-reorder-contact-joins REFRESH=1
```
Default builds reuse retained source data and rerun the validation and presentation steps. They do not query the warehouse. Missing or stale inputs stop the build; inspect the pipeline log before requesting refresh. REFRESH=1 is explicit and may change results.


### Inputs and dependencies

Generator batch: `diagrams`, defined in `shared/analysis/pipelines.yaml`. The batch is shared by related paragraphs and runs once per make invocation.
Existing generator commands (the batch explicitly sets CACHED=1 by default):
- `make data-source-diagrams CACHED=1`

Retained input folders and ownership:

Dates and cohort parameters are preserved from the source manifests and the existing generator defaults. Financial/contact defaults use May 1 through July 31, 2026, with follow-up observed through October 28; upload/prescription analyses retain their August 15 through October 14 study and documented upload/cancellation cutoffs. Do not mix source snapshots.
- `targets/financial-reorder-contact-joins/src/mermaid/connections.mmd`

Shared dependencies:
- `shared/analysis`
- `shared/artifact-ownership.yaml`
- `shared/paths.py`
- `shared/python/__init__.py`
- `shared/source-ownership.yaml`
- `shared/sql_templates.py`


### Outputs

Generated content: `targets/financial-reorder-contact-joins/outputs/latex/content.tex`.
Tables are exported to `outputs/tables/table.org` and read back to assemble LaTeX. The compatibility adapter retains cell formatting from the validated legacy renderer; `outputs/tables/provenance.json` records the source and Org fingerprints. Figures and diagrams are copied from their newly regenerated canonical exports. Logs are under the batch owner's `outputs/build/` folder.
Data and outputs are ignored by Git. `shared/artifact-ownership.yaml` maps historical dataset paths to target-owned locations. Existing legacy paths remain compatibility aliases.

## contact-matching-rules: How are customer contacts matched to aged orders and observation windows?



### Ownership

Target: `contact-matching-rules`. Level: `paragraph`.
Parent: `data-source-connections`.
Ordered children: none.


### Reproduction commands

Run from the repository root with the project environment installed:
```sh
make contact-matching-rules
make contact-matching-rules REPRO=1
make contact-matching-rules REFRESH=1
```
Default builds reuse retained source data and rerun the validation and presentation steps. They do not query the warehouse. Missing or stale inputs stop the build; inspect the pipeline log before requesting refresh. REFRESH=1 is explicit and may change results.


### Inputs and dependencies

Generator batch: `diagrams`, defined in `shared/analysis/pipelines.yaml`. The batch is shared by related paragraphs and runs once per make invocation.
Existing generator commands (the batch explicitly sets CACHED=1 by default):
- `make data-source-diagrams CACHED=1`

Retained input folders and ownership:

Dates and cohort parameters are preserved from the source manifests and the existing generator defaults. Financial/contact defaults use May 1 through July 31, 2026, with follow-up observed through October 28; upload/prescription analyses retain their August 15 through October 14 study and documented upload/cancellation cutoffs. Do not mix source snapshots.
- `targets/contact-matching-rules/src/mermaid/connections.mmd`

Shared dependencies:
- `shared/analysis`
- `shared/artifact-ownership.yaml`
- `shared/paths.py`
- `shared/python/__init__.py`
- `shared/source-ownership.yaml`
- `shared/sql_templates.py`


### Outputs

Generated content: `targets/contact-matching-rules/outputs/latex/content.tex`.
Tables are exported to `outputs/tables/table.org` and read back to assemble LaTeX. The compatibility adapter retains cell formatting from the validated legacy renderer; `outputs/tables/provenance.json` records the source and Org fingerprints. Figures and diagrams are copied from their newly regenerated canonical exports. Logs are under the batch owner's `outputs/build/` folder.
Data and outputs are ignored by Git. `shared/artifact-ownership.yaml` maps historical dataset paths to target-owned locations. Existing legacy paths remain compatibility aliases.

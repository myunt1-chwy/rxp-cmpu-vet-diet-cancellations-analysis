.DEFAULT_GOAL := setup

.PHONY: validate-analysis-sources
validate-analysis-sources:
	.venv/bin/python scripts/validate_analysis_sources.py

.PHONY: cohort-sql-review cohort-sql-check
cohort-sql-review:
	.venv/bin/python scripts/render_database_cohort_sql.py

cohort-sql-check:
	.venv/bin/python scripts/render_database_cohort_sql.py --lint

LATEXMK ?= latexmk
FINAL ?= 0

.PHONY: upload-data-verification
upload-data-verification:
	.venv/bin/python -m shared.python.create_upload_data_verification $(if $(filter 1,$(CACHED)),--cached)



.PHONY: legacy-report
legacy-report: report

# Replay the report's retained snapshots; these targets never refresh Snowflake.
.PHONY: reproduce-financial-section reproduce-contact-section reproduce-upload-delay-section reproduce-survival-section study-population-tables opportunity-contact-window-reorders
reproduce-financial-section:
	$(MAKE) --no-print-directory opportunity-order-cancellation-summary CACHED=1 WRITE_LATEX=1 DATE_BASIS=shipped-or-cancelled START_DATE=2026-05-01 END_DATE=2026-08-01
	$(MAKE) --no-print-directory opportunity-follow-up-sales CACHED=1 START_DATE=2026-05-01 END_DATE=2026-08-01 AS_OF_DATE=2026-10-28
	$(MAKE) --no-print-directory opportunity-new-upload-customer-follow-up CACHED=1 START_DATE=2026-05-01 END_DATE=2026-08-01 AS_OF_DATE=2026-10-28
	$(MAKE) --no-print-directory opportunity-new-vet-diet-customer-follow-up CACHED=1 START_DATE=2026-05-01 END_DATE=2026-08-01 AS_OF_DATE=2026-10-28
	$(MAKE) --no-print-directory combined-follow-up-table

reproduce-contact-section:
	$(MAKE) --no-print-directory opportunity-aged-customer-contacts CACHED=1 START_DATE=2026-05-01 END_DATE=2026-08-01 AS_OF_DATE=2026-10-28 HANDLED_ONLY=0
	$(MAKE) --no-print-directory opportunity-customer-contacts-by-cancel-reason CACHED=1 START_DATE=2026-05-01 END_DATE=2026-08-01 HANDLED_ONLY=0
	$(MAKE) --no-print-directory opportunity-contact-window-reorders

opportunity-contact-window-reorders:
	$(MAKE) --no-print-directory opportunity-contact-frequency-reorders CACHED=1 START_DATE=2026-05-01 END_DATE=2026-08-01 AS_OF_DATE=2026-10-28 FOLLOWUP_DAYS=14 HANDLED_ONLY=0
	.venv/bin/python -m shared.python.create_opportunity_contact_window_reorders

study-population-tables:
	.venv/bin/python scripts/summarize_study_population_uploaded_documents.py --export
	.venv/bin/python scripts/summarize_study_population_prescription_decisions.py
	.venv/bin/python -m shared.python.create_study_population_report_tables

.PHONY: study-population-refresh-inputs
study-population-refresh-inputs:
	.venv/bin/python targets/study-population-counts/src/python/refresh_study_population_inputs.py

reproduce-upload-delay-section:
	$(MAKE) --no-print-directory study-population-tables
	$(MAKE) --no-print-directory study-upload-tables
	$(MAKE) --no-print-directory cmpu-first-order-line-status CACHED=1 START_DATE=2026-08-15 END_DATE=2026-10-15 UPLOAD_START_DATE=2026-08-01
	$(MAKE) --no-print-directory cmpu-upload-entity-order-creation-distributions cmpu-upload-entity-state-change-distributions CACHED=1 START_DATE=2026-08-15 END_DATE=2026-10-15 UPLOAD_START_DATE=2026-08-01 AS_OF_DATE=2026-10-27
	$(MAKE) --no-print-directory cmpu-upload-to-approval-distribution CACHED=1 START_DATE=2026-08-15 END_DATE=2026-10-15 UPLOAD_START_DATE=2026-08-01

reproduce-survival-section:
	$(MAKE) --no-print-directory cmpu-first-order-line-survival START_DATE=2026-08-15 END_DATE=2026-10-15 UPLOAD_START_DATE=2026-08-01

.PHONY: study-upload-coverage-by-cancel-reason
study-upload-coverage-by-cancel-reason:
	.venv/bin/python -m shared.python.create_study_upload_coverage_by_cancel_reason

.PHONY: study-no-cancellation-upload-details
study-no-cancellation-upload-details:
	.venv/bin/python -m shared.python.create_study_no_cancellation_upload_details $(if $(filter 1,$(CACHED)),--cached)

# Run sequentially: both detail tables consume the regenerated coverage inputs.
# Always replay retained snapshots, including when CACHED=0 is passed by a caller.
.PHONY: study-upload-tables
study-upload-tables:
	$(MAKE) --no-print-directory study-upload-coverage-by-cancel-reason
	$(MAKE) --no-print-directory study-no-cancellation-upload-details CACHED=1
	$(MAKE) --no-print-directory study-aged-order-upload-coverage

.PHONY: study-aged-order-upload-coverage
study-aged-order-upload-coverage:
	.venv/bin/python -m shared.python.create_study_aged_order_upload_coverage


.PHONY: cmpu-upload-to-approval-distribution
cmpu-upload-to-approval-distribution:
	.venv/bin/python -m shared.python.create_cmpu_first_order_line_approval_distribution --endpoint upload-to-approval --exclude-negative --start-date "$(or $(START_DATE),2026-08-15)" --end-date "$(or $(END_DATE),2026-10-15)" --upload-start-date "$(or $(UPLOAD_START_DATE),2026-08-01)" $(if $(filter 1,$(PRINT_SQL)),--print-sql) $(if $(filter 1,$(CACHED)),--cached)

.PHONY: cmpu-first-order-line-upload-distribution
cmpu-first-order-line-upload-distribution:
	.venv/bin/python -m shared.python.create_cmpu_first_order_line_approval_distribution --endpoint upload --exclude-negative --start-date "$(or $(START_DATE),2026-08-15)" --end-date "$(or $(END_DATE),2026-10-15)" --upload-start-date "$(or $(UPLOAD_START_DATE),2026-08-01)" $(if $(filter 1,$(PRINT_SQL)),--print-sql) $(if $(filter 1,$(CACHED)),--cached)

.PHONY: cmpu-first-order-line-approval-distribution
cmpu-first-order-line-approval-distribution:
	.venv/bin/python -m shared.python.create_cmpu_first_order_line_approval_distribution --start-date "$(or $(START_DATE),2026-08-15)" --end-date "$(or $(END_DATE),2026-10-15)" $(if $(filter 1,$(WITH_UPLOAD)),--with-upload --upload-start-date "$(or $(UPLOAD_START_DATE),2026-08-01)") $(if $(filter 1,$(PRINT_SQL)),--print-sql) $(if $(filter 1,$(CACHED)),--cached)


.PHONY: cmpu-prescription-first-order-status cmpu-first-order-line-status
cmpu-prescription-first-order-status: cmpu-first-order-line-status

cmpu-first-order-line-status:
	.venv/bin/python -m shared.python.create_cmpu_first_order_line_status --start-date "$(or $(START_DATE),2026-08-15)" --end-date "$(or $(END_DATE),2026-10-15)" --upload-start-date "$(or $(UPLOAD_START_DATE),2026-08-01)" $(if $(filter 1,$(PRINT_SQL)),--print-sql) $(if $(filter 1,$(CACHED)),--cached)

.PHONY: setup init bootstrap setup-mattpocock-skills uninstall-mattpocock-skills

bootstrap:
	@command -v uv >/dev/null 2>&1 || { echo 'Error: uv is required. Install it from https://docs.astral.sh/uv/getting-started/installation/ and rerun make setup.' >&2; exit 1; }
	@test -x .venv/bin/python || uv venv --python 3.12 .venv

setup: bootstrap
	@.venv/bin/python scripts/setup.py

init: bootstrap
	@if test -f pyproject.toml; then uv sync --python 3.12 --group dev; fi
	@.venv/bin/python scripts/setup.py --init

setup-mattpocock-skills:
	@command -v npx >/dev/null 2>&1 || { echo 'Error: npx is required. Install Node.js with npm and rerun make setup-mattpocock-skills.' >&2; exit 1; }
	npx --yes skills@latest add mattpocock/skills --skill '*' --agent codex --yes

uninstall-mattpocock-skills:
	@command -v node >/dev/null 2>&1 && command -v npx >/dev/null 2>&1 || { echo 'Error: Node.js and npx are required. Install Node.js with npm and rerun make uninstall-mattpocock-skills.' >&2; exit 1; }
	node scripts/uninstall_mattpocock_skills.mjs

.PHONY: cmpu-first-order-line-event-times
cmpu-first-order-line-event-times:
	.venv/bin/python -m shared.python.create_cmpu_first_order_line_event_times --start-date "$(or $(START_DATE),2026-08-15)" --end-date "$(or $(END_DATE),2026-10-15)" --upload-start-date "$(or $(UPLOAD_START_DATE),2026-08-01)" $(if $(filter 1,$(PRINT_SQL)),--print-sql) $(if $(filter 1,$(CACHED)),--cached)

.PHONY: cmpu-first-order-line-survival
cmpu-first-order-line-survival:
	.venv/bin/python -m shared.python.create_cmpu_first_order_line_survival --start-date "$(or $(START_DATE),2026-08-15)" --end-date "$(or $(END_DATE),2026-10-15)" --upload-start-date "$(or $(UPLOAD_START_DATE),2026-08-01)"






.PHONY: aged-order-reorder-daily-customers
aged-order-reorder-daily-customers:
	.venv/bin/python -m shared.python.create_aged_order_reorder_daily_customers --start-date "$(or $(START_DATE),2026-08-15)" --end-date "$(or $(END_DATE),2026-10-15)" --as-of-date "$(or $(AS_OF_DATE),2026-10-27)" $(if $(filter 1,$(MATCH_PET)),--same-pet) --followup-days "$(or $(FOLLOWUP_DAYS),14)"

# Current reorder definition: match customer, product and pet; 0 reproduces the prior two-key analysis.
aged-order-reorder-windows aged-order-reorder-daily-customers: MATCH_PET ?= 1










.PHONY: cmpu-upload-entity-state-change-distributions
cmpu-upload-entity-state-change-distributions:
	.venv/bin/python -m shared.python.create_cmpu_upload_entity_state_change_distributions --start-date "$(or $(START_DATE),2026-08-15)" --end-date "$(or $(END_DATE),2026-10-15)" --upload-start-date "$(or $(UPLOAD_START_DATE),2026-08-01)" --as-of-date "$(or $(AS_OF_DATE),2026-10-27)" $(if $(filter 1,$(PRINT_SQL)),--print-sql) $(if $(filter 1,$(CACHED)),--cached)

.PHONY: cmpu-upload-entity-order-creation-distributions
cmpu-upload-entity-order-creation-distributions:
	.venv/bin/python -m shared.python.create_cmpu_upload_entity_order_creation_distributions --start-date "$(or $(START_DATE),2026-08-15)" --end-date "$(or $(END_DATE),2026-10-15)" --upload-start-date "$(or $(UPLOAD_START_DATE),2026-08-01)" --as-of-date "$(or $(AS_OF_DATE),2026-10-27)" $(if $(filter 1,$(PRINT_SQL)),--print-sql) $(if $(filter 1,$(CACHED)),--cached)

.PHONY: opportunity-order-cancellation-summary
opportunity-order-cancellation-summary:
	.venv/bin/python -m shared.python.create_opportunity_order_cancellation_summary --date-basis "$(or $(DATE_BASIS),placed)" --start-date "$(or $(START_DATE),2026-05-01)" --end-date "$(or $(END_DATE),2026-08-01)" $(if $(filter 1,$(PRINT_SQL)),--print-sql) $(if $(filter 1,$(CACHED)),--cached) $(if $(filter 1,$(WRITE_LATEX)),--write-latex)

.PHONY: prescription-cohort-order-comparison
prescription-cohort-order-comparison:
	.venv/bin/python scripts/summarize_prescription_cohort_order_comparison.py $(if $(filter 1,$(CACHED)),,--refresh) --write-latex


.PHONY: opportunity-follow-up-sales
opportunity-follow-up-sales:
	$(MAKE) --no-print-directory opportunity-aged-reorders ALL_WINDOWS=1 ALL_STUDIES=1 WRITE_LATEX=1
	$(MAKE) --no-print-directory opportunity-chewy-follow-up WRITE_LATEX=1

.PHONY: opportunity-chewy-follow-up
opportunity-chewy-follow-up:
	.venv/bin/python -m shared.python.create_opportunity_aged_reorders --all-chewy --all-windows --start-date "$(or $(START_DATE),2026-05-01)" --end-date "$(or $(END_DATE),2026-08-01)" --as-of-date "$(or $(AS_OF_DATE),2026-10-28)" $(if $(filter 1,$(WRITE_LATEX)),--write-latex) $(if $(filter 1,$(CACHED)),--cached) $(if $(filter 1,$(PRINT_SQL)),--print-sql)


.PHONY: opportunity-aged-new-vet-diet-customers
opportunity-aged-new-vet-diet-customers:
	.venv/bin/python -m shared.python.create_opportunity_aged_first_order_customers --scope vet-diet --start-date "$(or $(START_DATE),2026-05-01)" --end-date "$(or $(END_DATE),2026-08-01)" $(if $(filter 1,$(CACHED)),--cached) $(if $(filter 1,$(PRINT_SQL)),--print-sql)

.PHONY: opportunity-aged-new-customer-upload-vet-diet-customers
opportunity-aged-new-customer-upload-vet-diet-customers:
	.venv/bin/python -m shared.python.create_opportunity_aged_first_order_customers --scope vet-diet-customer-upload --start-date "$(or $(START_DATE),2026-05-01)" --end-date "$(or $(END_DATE),2026-08-01)" $(if $(filter 1,$(CACHED)),--cached) $(if $(filter 1,$(PRINT_SQL)),--print-sql)


.PHONY: opportunity-new-upload-customer-chewy-follow-up
opportunity-new-upload-customer-chewy-follow-up:
	.venv/bin/python -m shared.python.create_opportunity_new_upload_customer_follow_up --study any-chewy --write-latex --start-date "$(or $(START_DATE),2026-05-01)" --end-date "$(or $(END_DATE),2026-08-01)" --as-of-date "$(or $(AS_OF_DATE),2026-10-28)" $(if $(filter 1,$(CACHED)),--cached) $(if $(filter 1,$(PRINT_SQL)),--print-sql)

.PHONY: opportunity-new-vet-diet-customer-follow-up
opportunity-new-vet-diet-customer-follow-up:
	.venv/bin/python -m shared.python.create_opportunity_new_upload_customer_follow_up --cohort first-vet-diet --all-studies --write-latex --start-date "$(or $(START_DATE),2026-05-01)" --end-date "$(or $(END_DATE),2026-08-01)" --as-of-date "$(or $(AS_OF_DATE),2026-10-28)" $(if $(filter 1,$(CACHED)),--cached) $(if $(filter 1,$(PRINT_SQL)),--print-sql)
	$(MAKE) --no-print-directory opportunity-new-vet-diet-customer-chewy-follow-up

.PHONY: opportunity-new-vet-diet-customer-chewy-follow-up
opportunity-new-vet-diet-customer-chewy-follow-up:
	.venv/bin/python -m shared.python.create_opportunity_new_upload_customer_follow_up --cohort first-vet-diet --study any-chewy --write-latex --start-date "$(or $(START_DATE),2026-05-01)" --end-date "$(or $(END_DATE),2026-08-01)" --as-of-date "$(or $(AS_OF_DATE),2026-10-28)" $(if $(filter 1,$(CACHED)),--cached) $(if $(filter 1,$(PRINT_SQL)),--print-sql)

.PHONY: opportunity-aged-customer-contacts
opportunity-aged-customer-contacts:
	.venv/bin/python -m shared.python.create_opportunity_aged_customer_contacts --write-latex --start-date "$(or $(START_DATE),2026-05-01)" --end-date "$(or $(END_DATE),2026-08-01)" --as-of-date "$(or $(AS_OF_DATE),2026-10-28)" $(if $(filter 1,$(HANDLED_ONLY)),--handled-only) $(if $(filter 1,$(CACHED)),--cached) $(if $(filter 1,$(PRINT_SQL)),--print-sql)

.PHONY: opportunity-customer-contacts-by-cancel-reason
opportunity-customer-contacts-by-cancel-reason:
	.venv/bin/python -m shared.python.create_opportunity_contacts_by_cancel_reason --write-latex --start-date "$(or $(START_DATE),2026-05-01)" --end-date "$(or $(END_DATE),2026-08-01)" $(if $(filter 1,$(HANDLED_ONLY)),--handled-only) $(if $(filter 1,$(CACHED)),--cached) $(if $(filter 1,$(PRINT_SQL)),--print-sql)

.PHONY: opportunity-contact-frequency-reorders
opportunity-contact-frequency-reorders:
	.venv/bin/python -m shared.python.create_opportunity_contact_frequency_reorders --write-latex --start-date "$(or $(START_DATE),2026-05-01)" --end-date "$(or $(END_DATE),2026-08-01)" --as-of-date "$(or $(AS_OF_DATE),2026-10-28)" --followup-days "$(or $(FOLLOWUP_DAYS),14)" $(if $(filter 1,$(HANDLED_ONLY)),--handled-only) $(if $(filter 1,$(CACHED)),--cached) $(if $(filter 1,$(PRINT_SQL)),--print-sql)


SQL_PATH ?= targets
.PHONY: sql-lint sql-format
sql-lint:
	.venv/bin/sqlfluff lint --config .sqlfluff "$(SQL_PATH)"

sql-format:
	.venv/bin/sqlfluff format --config .sqlfluff "$(SQL_PATH)"

.PHONY: install-git-hooks sql-lint-staged
install-git-hooks:
	.venv/bin/python scripts/install_git_hooks.py

sql-lint-staged:
	.venv/bin/python scripts/check_staged_sql.py

.PHONY: validate-analysis-structure
validate-analysis-structure:
	.venv/bin/python scripts/validate_analysis_structure.py

# Temporary comparison build while generators are migrated; never publishes.
REPRO ?= 0
.PHONY: preview-target-report
preview-target-report:
	.venv/bin/python shared/python/analysis/preview.py --repro $(REPRO) --final $(FINAL)

# Question-led target graph. Legacy recipes above remain compatibility commands.
PYTHON ?= .venv/bin/python
REFRESH ?= 0
include shared/analysis/Makefile
include $(sort $(wildcard targets/*/Makefile))

PYTHON_PATH ?= .
.PHONY: python-lint python-format python-format-check python-lint-staged
python-lint:
	.venv/bin/ruff check "$(PYTHON_PATH)"

python-format:
	.venv/bin/ruff format "$(PYTHON_PATH)"

python-format-check:
	.venv/bin/ruff format --check "$(PYTHON_PATH)"

python-lint-staged:
	.venv/bin/python scripts/check_staged_python.py

.PHONY: study-upload-status-refresh study-upload-tables-refresh
study-upload-status-refresh:
	.venv/bin/python targets/no-recorded-cancellation-upload-statuses/src/python/refresh_study_upload_statuses.py

study-upload-tables-refresh:
	$(MAKE) --no-print-directory study-upload-coverage-by-cancel-reason
	$(MAKE) --no-print-directory study-upload-status-refresh
	$(MAKE) --no-print-directory study-no-cancellation-upload-details CACHED=1
	$(MAKE) --no-print-directory study-aged-order-upload-coverage

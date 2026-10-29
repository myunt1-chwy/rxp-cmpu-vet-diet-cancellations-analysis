.DEFAULT_GOAL := setup

LATEXMK ?= latexmk

.PHONY: report
report:
	@command -v "$(LATEXMK)" >/dev/null 2>&1 || { echo 'Error: latexmk is required. Install a TeX distribution with latexmk and pdflatex, or set LATEXMK=/path/to/latexmk.' >&2; exit 1; }
	mkdir -p build/latex outputs/pdf
	cd src/latex && "$(LATEXMK)" -pdf -interaction=nonstopmode -halt-on-error -file-line-error -outdir="$(CURDIR)/build/latex" main.tex
	cp build/latex/main.pdf outputs/pdf/cmpu-aged-order-analysis.pdf
	@echo "Report: outputs/pdf/cmpu-aged-order-analysis.pdf"

.PHONY: cmpu-upload-time-ratio-distribution
cmpu-upload-time-ratio-distribution:
	.venv/bin/python -m src.python.create_cmpu_upload_time_ratio_distribution --start-date "$(or $(START_DATE),2026-08-15)" --end-date "$(or $(END_DATE),2026-10-15)" --upload-start-date "$(or $(UPLOAD_START_DATE),2026-08-01)" $(if $(filter 1,$(PRINT_SQL)),--print-sql) $(if $(filter 1,$(CACHED)),--cached)

.PHONY: cmpu-upload-to-approval-distribution
cmpu-upload-to-approval-distribution:
	.venv/bin/python -m src.python.create_cmpu_first_order_line_approval_distribution --endpoint upload-to-approval --exclude-negative --start-date "$(or $(START_DATE),2026-08-15)" --end-date "$(or $(END_DATE),2026-10-15)" --upload-start-date "$(or $(UPLOAD_START_DATE),2026-08-01)" $(if $(filter 1,$(PRINT_SQL)),--print-sql) $(if $(filter 1,$(CACHED)),--cached)

.PHONY: cmpu-first-order-line-upload-distribution
cmpu-first-order-line-upload-distribution:
	.venv/bin/python -m src.python.create_cmpu_first_order_line_approval_distribution --endpoint upload --exclude-negative --start-date "$(or $(START_DATE),2026-08-15)" --end-date "$(or $(END_DATE),2026-10-15)" --upload-start-date "$(or $(UPLOAD_START_DATE),2026-08-01)" $(if $(filter 1,$(PRINT_SQL)),--print-sql) $(if $(filter 1,$(CACHED)),--cached)

.PHONY: cmpu-first-order-line-approval-distribution
cmpu-first-order-line-approval-distribution:
	.venv/bin/python -m src.python.create_cmpu_first_order_line_approval_distribution --start-date "$(or $(START_DATE),2026-08-15)" --end-date "$(or $(END_DATE),2026-10-15)" $(if $(filter 1,$(WITH_UPLOAD)),--with-upload --upload-start-date "$(or $(UPLOAD_START_DATE),2026-08-01)") $(if $(filter 1,$(PRINT_SQL)),--print-sql) $(if $(filter 1,$(CACHED)),--cached)

.PHONY: cmpu-order-to-approval-distributions
cmpu-order-to-approval-distributions:
	.venv/bin/python -m src.python.create_cmpu_order_to_approval_distributions --start-date "$(or $(START_DATE),2026-08-15)" --end-date "$(or $(END_DATE),2026-10-15)" --upload-start-date "$(or $(UPLOAD_START_DATE),2026-08-01)" $(if $(filter 1,$(PRINT_SQL)),--print-sql) $(if $(filter 1,$(CACHED)),--cached)

.PHONY: cmpu-prescription-first-order-status cmpu-first-order-line-status
cmpu-prescription-first-order-status: cmpu-first-order-line-status

cmpu-first-order-line-status:
	.venv/bin/python -m src.python.create_cmpu_first_order_line_status --start-date "$(or $(START_DATE),2026-08-15)" --end-date "$(or $(END_DATE),2026-10-15)" --upload-start-date "$(or $(UPLOAD_START_DATE),2026-08-01)" $(if $(filter 1,$(PRINT_SQL)),--print-sql) $(if $(filter 1,$(CACHED)),--cached)

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
	.venv/bin/python -m src.python.create_cmpu_first_order_line_event_times --start-date "$(or $(START_DATE),2026-08-15)" --end-date "$(or $(END_DATE),2026-10-15)" --upload-start-date "$(or $(UPLOAD_START_DATE),2026-08-01)" $(if $(filter 1,$(PRINT_SQL)),--print-sql) $(if $(filter 1,$(CACHED)),--cached)

.PHONY: cmpu-first-order-line-survival
cmpu-first-order-line-survival:
	.venv/bin/python -m src.python.create_cmpu_first_order_line_survival --start-date "$(or $(START_DATE),2026-08-15)" --end-date "$(or $(END_DATE),2026-10-15)" --upload-start-date "$(or $(UPLOAD_START_DATE),2026-08-01)"

.PHONY: aged-order-same-product-reorders
aged-order-same-product-reorders:
	.venv/bin/python -m src.python.create_aged_order_same_product_reorders --start-date "$(or $(START_DATE),2026-08-15)" --end-date "$(or $(END_DATE),2026-10-15)" $(if $(AS_OF_DATE),--as-of-date "$(AS_OF_DATE)") --approval-channel "$(or $(APPROVAL_CHANNEL),CUSTOMER_UPLOAD)" $(if $(filter 1,$(PRINT_SQL)),--print-sql) $(if $(filter 1,$(CACHED)),--cached)

.PHONY: aged-order-reorder-prescriptions
aged-order-reorder-prescriptions:
	.venv/bin/python -m src.python.create_aged_order_reorder_prescriptions --start-date "$(or $(START_DATE),2026-08-15)" --end-date "$(or $(END_DATE),2026-10-15)" --as-of-date "$(or $(AS_OF_DATE),2026-10-27)" $(if $(filter 1,$(PRINT_SQL)),--print-sql) $(if $(filter 1,$(CACHED)),--cached)

.PHONY: aged-order-reorder-approval-channels
aged-order-reorder-approval-channels:
	.venv/bin/python -m src.python.create_aged_order_reorder_approval_channels --start-date "$(or $(START_DATE),2026-08-15)" --end-date "$(or $(END_DATE),2026-10-15)" --as-of-date "$(or $(AS_OF_DATE),2026-10-27)" $(if $(filter 1,$(PRINT_SQL)),--print-sql) $(if $(filter 1,$(CACHED)),--cached)

.PHONY: aged-order-reorder-uploads
aged-order-reorder-uploads:
	.venv/bin/python -m src.python.create_aged_order_reorder_uploads --start-date "$(or $(START_DATE),2026-08-15)" --end-date "$(or $(END_DATE),2026-10-15)" --as-of-date "$(or $(AS_OF_DATE),2026-10-27)" $(if $(filter 1,$(PRINT_SQL)),--print-sql) $(if $(filter 1,$(CACHED)),--cached)

.PHONY: aged-order-reorder-windows
aged-order-reorder-windows:
	.venv/bin/python -m src.python.create_aged_order_reorder_windows --start-date "$(or $(START_DATE),2026-08-15)" --end-date "$(or $(END_DATE),2026-10-15)" --as-of-date "$(or $(AS_OF_DATE),2026-10-27)" $(if $(filter 1,$(PRINT_SQL)),--print-sql) $(if $(filter 1,$(CACHED)),--cached) $(if $(filter 1,$(MATCH_PET)),--same-pet) $(if $(filter 1,$(INCLUDE_21_DAYS)),--include-21-days)

.PHONY: aged-order-reorder-daily-customers
aged-order-reorder-daily-customers:
	.venv/bin/python -m src.python.create_aged_order_reorder_daily_customers --start-date "$(or $(START_DATE),2026-08-15)" --end-date "$(or $(END_DATE),2026-10-15)" --as-of-date "$(or $(AS_OF_DATE),2026-10-27)" $(if $(filter 1,$(MATCH_PET)),--same-pet) --followup-days "$(or $(FOLLOWUP_DAYS),14)"

# Current reorder definition: match customer, product and pet; 0 reproduces the prior two-key analysis.
aged-order-reorder-windows aged-order-reorder-daily-customers: MATCH_PET ?= 1

.PHONY: aged-order-reorder-prescription-sankeys
aged-order-reorder-prescription-sankeys:
	.venv/bin/python -m src.python.create_aged_order_reorder_prescription_sankeys --start-date "$(or $(START_DATE),2026-08-15)" --end-date "$(or $(END_DATE),2026-10-15)" --as-of-date "$(or $(AS_OF_DATE),2026-10-27)" $(if $(filter 1,$(PRINT_SQL)),--print-sql) $(if $(filter 1,$(CACHED)),--cached) $(if $(filter 1,$(WITH_EVIDENCE)),--with-evidence) $(if $(filter 1,$(WITH_WISMO)),--with-wismo) $(if $(CONTACT_TIMEZONE),--contact-timezone "$(CONTACT_TIMEZONE)") $(if $(filter 1,$(ALL_CONTACTS)),--all-contacts) $(if $(filter 1,$(ALL_ORDER_HISTORY)),--all-order-history)

.PHONY: aged-order-reorder-upload-approval-evidence
aged-order-reorder-upload-approval-evidence:
	.venv/bin/python -m src.python.create_aged_order_reorder_upload_approval_evidence --start-date "$(or $(START_DATE),2026-08-15)" --end-date "$(or $(END_DATE),2026-10-15)" --as-of-date "$(or $(AS_OF_DATE),2026-10-27)" $(if $(filter 1,$(PRINT_SQL)),--print-sql) $(if $(filter 1,$(CACHED)),--cached)

.PHONY: aged-order-reorder-wismo
aged-order-reorder-wismo:
	.venv/bin/python -m src.python.create_aged_order_reorder_wismo --start-date "$(or $(START_DATE),2026-08-15)" --end-date "$(or $(END_DATE),2026-10-15)" --as-of-date "$(or $(AS_OF_DATE),2026-10-27)" $(if $(CONTACT_TIMEZONE),--contact-timezone "$(CONTACT_TIMEZONE)") $(if $(filter 1,$(PRINT_SQL)),--print-sql) $(if $(filter 1,$(CACHED)),--cached) $(if $(filter 1,$(ALL_CONTACTS)),--all-contacts) $(if $(filter 1,$(ALL_ORDER_HISTORY)),--all-order-history)

.PHONY: aged-order-contact-cancellation-distribution
aged-order-contact-cancellation-distribution:
	.venv/bin/python -m src.python.create_aged_order_contact_cancellation_distribution --start-date "$(or $(START_DATE),2026-08-15)" --end-date "$(or $(END_DATE),2026-10-15)" --as-of-date "$(or $(AS_OF_DATE),2026-10-27)"

.PHONY: aged-order-all-contact-cancellation-distribution
aged-order-all-contact-cancellation-distribution:
	.venv/bin/python -m src.python.create_aged_order_all_contact_cancellation_distribution --start-date "$(or $(START_DATE),2026-08-15)" --end-date "$(or $(END_DATE),2026-10-15)" --as-of-date "$(or $(AS_OF_DATE),2026-10-27)" $(if $(filter 1,$(PRINT_SQL)),--print-sql) $(if $(filter 1,$(CACHED)),--cached)

.PHONY: aged-customer-prior-shipped-prescriptions
aged-customer-prior-shipped-prescriptions:
	.venv/bin/python -m src.python.create_aged_customer_prior_shipped_prescriptions --start-date "$(or $(START_DATE),2026-08-15)" --end-date "$(or $(END_DATE),2026-10-15)" --as-of-date "$(or $(AS_OF_DATE),2026-10-27)" $(if $(filter 1,$(PRINT_SQL)),--print-sql) $(if $(filter 1,$(CACHED)),--cached)

.PHONY: cmpu-customer-prior-shipped-prescriptions
cmpu-customer-prior-shipped-prescriptions:
	.venv/bin/python -m src.python.create_cmpu_customer_prior_shipped_prescriptions --start-date "$(or $(START_DATE),2026-08-15)" --end-date "$(or $(END_DATE),2026-10-15)" --as-of-date "$(or $(AS_OF_DATE),2026-10-27)" --approval-channel "$(or $(APPROVAL_CHANNEL),ALL)" $(if $(filter 1,$(PRINT_SQL)),--print-sql) $(if $(filter 1,$(CACHED)),--cached)

.PHONY: aged-customer-prior-same-clinic-shipments
aged-customer-prior-same-clinic-shipments:
	.venv/bin/python -m src.python.create_aged_customer_prior_same_clinic_shipments --start-date "$(or $(START_DATE),2026-08-15)" --end-date "$(or $(END_DATE),2026-10-15)" --as-of-date "$(or $(AS_OF_DATE),2026-10-27)" $(if $(filter 1,$(PRINT_SQL)),--print-sql) $(if $(filter 1,$(CACHED)),--cached)

.PHONY: aged-customer-21d-reorder-clinic-history
aged-customer-21d-reorder-clinic-history:
	.venv/bin/python -m src.python.create_aged_customer_21d_reorder_clinic_history --start-date "$(or $(START_DATE),2026-08-15)" --end-date "$(or $(END_DATE),2026-10-15)" --as-of-date "$(or $(AS_OF_DATE),2026-10-27)" $(if $(filter 1,$(PRINT_SQL)),--print-sql) $(if $(filter 1,$(CACHED)),--cached)

.PHONY: cmpu-upload-entity-state-change-distributions
cmpu-upload-entity-state-change-distributions:
	.venv/bin/python -m src.python.create_cmpu_upload_entity_state_change_distributions --start-date "$(or $(START_DATE),2026-08-15)" --end-date "$(or $(END_DATE),2026-10-15)" --upload-start-date "$(or $(UPLOAD_START_DATE),2026-08-01)" --as-of-date "$(or $(AS_OF_DATE),2026-10-27)" $(if $(filter 1,$(PRINT_SQL)),--print-sql) $(if $(filter 1,$(CACHED)),--cached)

.PHONY: cmpu-upload-entity-order-creation-distributions
cmpu-upload-entity-order-creation-distributions:
	.venv/bin/python -m src.python.create_cmpu_upload_entity_order_creation_distributions --start-date "$(or $(START_DATE),2026-08-15)" --end-date "$(or $(END_DATE),2026-10-15)" --upload-start-date "$(or $(UPLOAD_START_DATE),2026-08-01)" --as-of-date "$(or $(AS_OF_DATE),2026-10-27)" $(if $(filter 1,$(PRINT_SQL)),--print-sql) $(if $(filter 1,$(CACHED)),--cached)

.PHONY: opportunity-order-cancellation-summary
opportunity-order-cancellation-summary:
	.venv/bin/python -m src.python.create_opportunity_order_cancellation_summary --start-date "$(or $(START_DATE),2026-06-01)" --end-date "$(or $(END_DATE),2026-09-01)" $(if $(filter 1,$(PRINT_SQL)),--print-sql) $(if $(filter 1,$(CACHED)),--cached) $(if $(filter 1,$(WRITE_LATEX)),--write-latex)

.PHONY: prescription-cohort-order-comparison
prescription-cohort-order-comparison:
	.venv/bin/python scripts/summarize_prescription_cohort_order_comparison.py $(if $(filter 1,$(CACHED)),,--refresh) --write-latex

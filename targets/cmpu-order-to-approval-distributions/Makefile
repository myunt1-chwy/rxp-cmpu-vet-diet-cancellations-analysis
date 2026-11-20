# Retained analysis command; not included in the report hierarchy.
.PHONY: cmpu-order-to-approval-distributions
cmpu-order-to-approval-distributions:
	.venv/bin/python -m shared.python.create_cmpu_order_to_approval_distributions --start-date "$(or $(START_DATE),2026-08-15)" --end-date "$(or $(END_DATE),2026-10-15)" --upload-start-date "$(or $(UPLOAD_START_DATE),2026-08-01)" $(if $(filter 1,$(PRINT_SQL)),--print-sql) $(if $(filter 1,$(CACHED)),--cached)

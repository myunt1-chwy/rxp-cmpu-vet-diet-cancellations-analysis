# Retained analysis command; not included in the report hierarchy.
.PHONY: aged-order-reorder-approval-channels
aged-order-reorder-approval-channels:
	.venv/bin/python -m shared.python.create_aged_order_reorder_approval_channels --start-date "$(or $(START_DATE),2026-08-15)" --end-date "$(or $(END_DATE),2026-10-15)" --as-of-date "$(or $(AS_OF_DATE),2026-10-27)" $(if $(filter 1,$(PRINT_SQL)),--print-sql) $(if $(filter 1,$(CACHED)),--cached)

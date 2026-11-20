# Retained analysis command; not included in the report hierarchy.
.PHONY: aged-order-reorder-windows
aged-order-reorder-windows:
	.venv/bin/python -m shared.python.create_aged_order_reorder_windows --start-date "$(or $(START_DATE),2026-08-15)" --end-date "$(or $(END_DATE),2026-10-15)" --as-of-date "$(or $(AS_OF_DATE),2026-10-27)" $(if $(filter 1,$(PRINT_SQL)),--print-sql) $(if $(filter 1,$(CACHED)),--cached) $(if $(filter 1,$(MATCH_PET)),--same-pet) $(if $(filter 1,$(INCLUDE_21_DAYS)),--include-21-days)

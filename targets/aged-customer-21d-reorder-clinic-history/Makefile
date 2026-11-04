# Retained analysis command; not included in the report hierarchy.
.PHONY: aged-customer-21d-reorder-clinic-history
aged-customer-21d-reorder-clinic-history:
	.venv/bin/python -m shared.python.create_aged_customer_21d_reorder_clinic_history --start-date "$(or $(START_DATE),2026-08-15)" --end-date "$(or $(END_DATE),2026-10-15)" --as-of-date "$(or $(AS_OF_DATE),2026-10-27)" $(if $(filter 1,$(PRINT_SQL)),--print-sql) $(if $(filter 1,$(CACHED)),--cached)

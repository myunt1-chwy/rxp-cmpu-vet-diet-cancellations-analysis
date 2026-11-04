# Retained analysis command; not included in the report hierarchy.
.PHONY: opportunity-aged-new-customers
opportunity-aged-new-customers:
	.venv/bin/python -m $(if $(filter same-day,$(METHOD)),shared.python.create_opportunity_aged_new_customers,shared.python.create_opportunity_aged_first_order_customers) --start-date "$(or $(START_DATE),2026-05-01)" --end-date "$(or $(END_DATE),2026-08-01)" $(if $(filter 1,$(CACHED)),--cached) $(if $(filter 1,$(PRINT_SQL)),--print-sql)

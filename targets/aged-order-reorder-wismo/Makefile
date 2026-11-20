# Retained analysis command; not included in the report hierarchy.
.PHONY: aged-order-reorder-wismo
aged-order-reorder-wismo:
	.venv/bin/python -m shared.python.create_aged_order_reorder_wismo --start-date "$(or $(START_DATE),2026-08-15)" --end-date "$(or $(END_DATE),2026-10-15)" --as-of-date "$(or $(AS_OF_DATE),2026-10-27)" $(if $(CONTACT_TIMEZONE),--contact-timezone "$(CONTACT_TIMEZONE)") $(if $(filter 1,$(PRINT_SQL)),--print-sql) $(if $(filter 1,$(CACHED)),--cached) $(if $(filter 1,$(ALL_CONTACTS)),--all-contacts) $(if $(filter 1,$(ALL_ORDER_HISTORY)),--all-order-history)

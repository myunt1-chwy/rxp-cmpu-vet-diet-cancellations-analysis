# Retained analysis command; not included in the report hierarchy.
.PHONY: aged-order-same-product-reorders
aged-order-same-product-reorders:
	.venv/bin/python -m shared.python.create_aged_order_same_product_reorders --start-date "$(or $(START_DATE),2026-08-15)" --end-date "$(or $(END_DATE),2026-10-15)" $(if $(AS_OF_DATE),--as-of-date "$(AS_OF_DATE)") --approval-channel "$(or $(APPROVAL_CHANNEL),CUSTOMER_UPLOAD)" $(if $(filter 1,$(PRINT_SQL)),--print-sql) $(if $(filter 1,$(CACHED)),--cached)

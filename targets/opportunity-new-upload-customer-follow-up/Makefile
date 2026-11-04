# Existing batch command; outside the report hierarchy.
.PHONY: opportunity-new-upload-customer-follow-up
opportunity-new-upload-customer-follow-up:
	.venv/bin/python -m shared.python.create_opportunity_new_upload_customer_follow_up --all-studies --write-latex --start-date "$(or $(START_DATE),2026-05-01)" --end-date "$(or $(END_DATE),2026-08-01)" --as-of-date "$(or $(AS_OF_DATE),2026-10-28)" $(if $(filter 1,$(CACHED)),--cached) $(if $(filter 1,$(PRINT_SQL)),--print-sql)
	$(MAKE) --no-print-directory opportunity-new-upload-customer-chewy-follow-up

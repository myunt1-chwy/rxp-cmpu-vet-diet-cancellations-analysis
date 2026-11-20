# Existing batch command; outside the report hierarchy.
.PHONY: upload-data-verification-all
upload-data-verification-all:
	.venv/bin/python -m shared.python.recreate_upload_data_verification $(if $(filter 1,$(CACHED)),--cached)
	$(MAKE) --no-print-directory report-sql-listings

# Retained analysis command; not included in the report hierarchy.
.PHONY: cmpu-upload-time-ratio-distribution
cmpu-upload-time-ratio-distribution:
	.venv/bin/python -m shared.python.create_cmpu_upload_time_ratio_distribution --start-date "$(or $(START_DATE),2026-08-15)" --end-date "$(or $(END_DATE),2026-10-15)" --upload-start-date "$(or $(UPLOAD_START_DATE),2026-08-01)" $(if $(filter 1,$(PRINT_SQL)),--print-sql) $(if $(filter 1,$(CACHED)),--cached)

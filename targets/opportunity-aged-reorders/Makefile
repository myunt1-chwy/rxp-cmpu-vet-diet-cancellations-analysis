# Existing batch command; outside the report hierarchy.
.PHONY: opportunity-aged-reorders
opportunity-aged-reorders:
	.venv/bin/python -m shared.python.create_opportunity_aged_reorders --start-date "$(or $(START_DATE),2026-05-01)" --end-date "$(or $(END_DATE),2026-08-01)" --as-of-date "$(or $(AS_OF_DATE),2026-10-28)" --followup-days "$(or $(FOLLOWUP_DAYS),7)" $(if $(filter 1,$(ALL_WINDOWS)),--all-windows) $(if $(filter 1,$(ALL_STUDIES)),--all-studies) $(if $(filter 1,$(WRITE_LATEX)),--write-latex) $(if $(filter 1,$(CACHED)),--cached) $(if $(filter 1,$(PRINT_SQL)),--print-sql)

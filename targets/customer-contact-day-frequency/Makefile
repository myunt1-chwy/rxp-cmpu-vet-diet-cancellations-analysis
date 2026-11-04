# Included by the root Makefile. Child order is defined in target.yaml.
.PHONY: customer-contact-day-frequency
customer-contact-day-frequency: analysis-pipeline-contacts
	$(PYTHON) shared/python/analysis/build_target.py customer-contact-day-frequency --refresh $(REFRESH) --repro $(REPRO) --final $(FINAL)

# Included by the root Makefile. Child order is defined in target.yaml.
.PHONY: contact-frequency
contact-frequency: customer-contact-day-frequency
	$(PYTHON) shared/analysis/build_target.py contact-frequency --refresh $(REFRESH) --repro $(REPRO) --final $(FINAL)

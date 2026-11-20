# Included by the root Makefile. Child order is defined in target.yaml.
.PHONY: contact-frequency-and-returns
contact-frequency-and-returns: return-rates-by-contact-frequency
	$(PYTHON) shared/python/analysis/build_target.py contact-frequency-and-returns --refresh $(REFRESH) --repro $(REPRO) --final $(FINAL)

# Included by the root Makefile. Child order is defined in target.yaml.
.PHONY: contact-proximity-and-returns
contact-proximity-and-returns: return-rates-by-contact-window
	$(PYTHON) shared/analysis/build_target.py contact-proximity-and-returns --refresh $(REFRESH) --repro $(REPRO) --final $(FINAL)

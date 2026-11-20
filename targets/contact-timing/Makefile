# Included by the root Makefile. Child order is defined in target.yaml.
.PHONY: contact-timing
contact-timing: contact-days-relative-to-cancellation
	$(PYTHON) shared/python/analysis/build_target.py contact-timing --refresh $(REFRESH) --repro $(REPRO) --final $(FINAL)

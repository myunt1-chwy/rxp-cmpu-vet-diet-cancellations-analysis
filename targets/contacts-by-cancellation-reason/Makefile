# Included by the root Makefile. Child order is defined in target.yaml.
.PHONY: contacts-by-cancellation-reason
contacts-by-cancellation-reason: contact-cancellation-distribution
	$(PYTHON) shared/python/analysis/build_target.py contacts-by-cancellation-reason --refresh $(REFRESH) --repro $(REPRO) --final $(FINAL)

# Included by the root Makefile. Child order is defined in target.yaml.
.PHONY: first-order-event-free-survival
first-order-event-free-survival: first-order-survival-curve
	$(PYTHON) shared/python/analysis/build_target.py first-order-event-free-survival --refresh $(REFRESH) --repro $(REPRO) --final $(FINAL)

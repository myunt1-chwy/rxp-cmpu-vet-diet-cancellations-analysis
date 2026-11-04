# Included by the root Makefile. Child order is defined in target.yaml.
.PHONY: estimated-sales-loss
estimated-sales-loss: cancellation-sales-baseline
	$(PYTHON) shared/python/analysis/build_target.py estimated-sales-loss --refresh $(REFRESH) --repro $(REPRO) --final $(FINAL)

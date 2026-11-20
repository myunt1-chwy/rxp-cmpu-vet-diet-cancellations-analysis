# Included by the root Makefile. Child order is defined in target.yaml.
.PHONY: study-population-context
study-population-context: study-population-counts study-prescription-decisions study-order-cancellation-sales first-order-upload-status-flow
	$(PYTHON) shared/python/analysis/build_target.py study-population-context --refresh $(REFRESH) --repro $(REPRO) --final $(FINAL)

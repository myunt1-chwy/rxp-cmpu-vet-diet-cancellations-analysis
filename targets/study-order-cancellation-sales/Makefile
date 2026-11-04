# Included by the root Makefile. Child order is defined in target.yaml.
.PHONY: study-order-cancellation-sales
study-order-cancellation-sales: analysis-pipeline-study-population
	$(PYTHON) shared/python/analysis/build_target.py study-order-cancellation-sales --refresh $(REFRESH) --repro $(REPRO) --final $(FINAL)

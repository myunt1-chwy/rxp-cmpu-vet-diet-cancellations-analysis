# Included by the root Makefile. Child order is defined in target.yaml.
.PHONY: prescription-first-order-joins
prescription-first-order-joins: analysis-pipeline-diagrams
	$(PYTHON) shared/python/analysis/build_target.py prescription-first-order-joins --refresh $(REFRESH) --repro $(REPRO) --final $(FINAL)

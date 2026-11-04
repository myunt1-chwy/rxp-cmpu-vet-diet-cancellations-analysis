# Included by the root Makefile. Child order is defined in target.yaml.
.PHONY: first-order-survival-curve
first-order-survival-curve: analysis-pipeline-survival
	$(PYTHON) shared/analysis/build_target.py first-order-survival-curve --refresh $(REFRESH) --repro $(REPRO) --final $(FINAL)

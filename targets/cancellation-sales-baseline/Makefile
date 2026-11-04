# Included by the root Makefile. Child order is defined in target.yaml.
.PHONY: cancellation-sales-baseline
cancellation-sales-baseline: analysis-pipeline-financial-baseline
	$(PYTHON) shared/python/analysis/build_target.py cancellation-sales-baseline --refresh $(REFRESH) --repro $(REPRO) --final $(FINAL)

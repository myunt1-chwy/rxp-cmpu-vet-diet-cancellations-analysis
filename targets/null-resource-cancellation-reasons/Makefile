# Included by the root Makefile. Child order is defined in target.yaml.
.PHONY: null-resource-cancellation-reasons
null-resource-cancellation-reasons: analysis-pipeline-verification
	$(PYTHON) shared/python/analysis/build_target.py null-resource-cancellation-reasons --refresh $(REFRESH) --repro $(REPRO) --final $(FINAL)

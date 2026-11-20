# Included by the root Makefile. Child order is defined in target.yaml.
.PHONY: uploaded-order-cancellation-reasons
uploaded-order-cancellation-reasons: analysis-pipeline-verification
	$(PYTHON) shared/python/analysis/build_target.py uploaded-order-cancellation-reasons --refresh $(REFRESH) --repro $(REPRO) --final $(FINAL)

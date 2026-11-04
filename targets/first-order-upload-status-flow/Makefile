# Included by the root Makefile. Child order is defined in target.yaml.
.PHONY: first-order-upload-status-flow
first-order-upload-status-flow: analysis-pipeline-first-order-status
	$(PYTHON) shared/analysis/build_target.py first-order-upload-status-flow --refresh $(REFRESH) --repro $(REPRO) --final $(FINAL)

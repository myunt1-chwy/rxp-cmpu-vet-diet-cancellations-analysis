# Included by the root Makefile. Child order is defined in target.yaml.
.PHONY: first-order-upload-coverage
first-order-upload-coverage: analysis-pipeline-upload-coverage
	$(PYTHON) shared/analysis/build_target.py first-order-upload-coverage --refresh $(REFRESH) --repro $(REPRO) --final $(FINAL)

# Included by the root Makefile. Child order is defined in target.yaml.
.PHONY: customer-upload-rx-status-coverage
customer-upload-rx-status-coverage: analysis-pipeline-verification
	$(PYTHON) shared/python/analysis/build_target.py customer-upload-rx-status-coverage --refresh $(REFRESH) --repro $(REPRO) --final $(FINAL)

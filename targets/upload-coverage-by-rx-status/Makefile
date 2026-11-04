# Included by the root Makefile. Child order is defined in target.yaml.
.PHONY: upload-coverage-by-rx-status
upload-coverage-by-rx-status: customer-upload-rx-status-coverage
	$(PYTHON) shared/analysis/build_target.py upload-coverage-by-rx-status --refresh $(REFRESH) --repro $(REPRO) --final $(FINAL)

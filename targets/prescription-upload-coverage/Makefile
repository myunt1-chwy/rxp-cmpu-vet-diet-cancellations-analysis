# Included by the root Makefile. Child order is defined in target.yaml.
.PHONY: prescription-upload-coverage
prescription-upload-coverage: first-order-upload-coverage no-recorded-cancellation-upload-statuses aged-line-upload-statuses
	$(PYTHON) shared/python/analysis/build_target.py prescription-upload-coverage --refresh $(REFRESH) --repro $(REPRO) --final $(FINAL)

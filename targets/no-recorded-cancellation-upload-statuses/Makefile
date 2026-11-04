# Included by the root Makefile. Child order is defined in target.yaml.
.PHONY: no-recorded-cancellation-upload-statuses
no-recorded-cancellation-upload-statuses: analysis-pipeline-upload-coverage
	$(PYTHON) shared/analysis/build_target.py no-recorded-cancellation-upload-statuses --refresh $(REFRESH) --repro $(REPRO) --final $(FINAL)

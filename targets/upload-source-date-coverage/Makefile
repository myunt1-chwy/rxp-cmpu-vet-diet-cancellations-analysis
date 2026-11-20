# Included by the root Makefile. Child order is defined in target.yaml.
.PHONY: upload-source-date-coverage
upload-source-date-coverage: analysis-pipeline-verification
	$(PYTHON) shared/python/analysis/build_target.py upload-source-date-coverage --refresh $(REFRESH) --repro $(REPRO) --final $(FINAL)

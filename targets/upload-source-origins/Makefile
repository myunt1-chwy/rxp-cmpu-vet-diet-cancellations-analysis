# Included by the root Makefile. Child order is defined in target.yaml.
.PHONY: upload-source-origins
upload-source-origins: upload-resource-types upload-source-date-coverage
	$(PYTHON) shared/analysis/build_target.py upload-source-origins --refresh $(REFRESH) --repro $(REPRO) --final $(FINAL)

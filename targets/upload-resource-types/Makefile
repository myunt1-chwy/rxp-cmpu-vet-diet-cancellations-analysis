# Included by the root Makefile. Child order is defined in target.yaml.
.PHONY: upload-resource-types
upload-resource-types: analysis-pipeline-verification
	$(PYTHON) shared/analysis/build_target.py upload-resource-types --refresh $(REFRESH) --repro $(REPRO) --final $(FINAL)

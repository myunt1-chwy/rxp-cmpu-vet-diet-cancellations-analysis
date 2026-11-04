# Included by the root Makefile. Child order is defined in target.yaml.
.PHONY: upload-verification-joins
upload-verification-joins: analysis-pipeline-diagrams
	$(PYTHON) shared/analysis/build_target.py upload-verification-joins --refresh $(REFRESH) --repro $(REPRO) --final $(FINAL)

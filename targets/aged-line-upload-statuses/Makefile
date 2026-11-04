# Included by the root Makefile. Child order is defined in target.yaml.
.PHONY: aged-line-upload-statuses
aged-line-upload-statuses: analysis-pipeline-upload-coverage
	$(PYTHON) shared/python/analysis/build_target.py aged-line-upload-statuses --refresh $(REFRESH) --repro $(REPRO) --final $(FINAL)

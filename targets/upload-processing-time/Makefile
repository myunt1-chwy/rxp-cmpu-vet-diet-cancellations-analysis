# Included by the root Makefile. Child order is defined in target.yaml.
.PHONY: upload-processing-time
upload-processing-time: all-upload-state-change-delays aged-upload-state-change-delays
	$(PYTHON) shared/python/analysis/build_target.py upload-processing-time --refresh $(REFRESH) --repro $(REPRO) --final $(FINAL)

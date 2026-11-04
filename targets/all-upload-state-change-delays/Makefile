# Included by the root Makefile. Child order is defined in target.yaml.
.PHONY: all-upload-state-change-delays
all-upload-state-change-delays: analysis-pipeline-upload-state
	$(PYTHON) shared/analysis/build_target.py all-upload-state-change-delays --refresh $(REFRESH) --repro $(REPRO) --final $(FINAL)

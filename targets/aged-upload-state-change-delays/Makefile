# Included by the root Makefile. Child order is defined in target.yaml.
.PHONY: aged-upload-state-change-delays
aged-upload-state-change-delays: analysis-pipeline-upload-state
	$(PYTHON) shared/analysis/build_target.py aged-upload-state-change-delays --refresh $(REFRESH) --repro $(REPRO) --final $(FINAL)

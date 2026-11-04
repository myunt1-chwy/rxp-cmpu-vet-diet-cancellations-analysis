# Included by the root Makefile. Child order is defined in target.yaml.
.PHONY: uploaded-prescription-approval-channels
uploaded-prescription-approval-channels: analysis-pipeline-verification
	$(PYTHON) shared/python/analysis/build_target.py uploaded-prescription-approval-channels --refresh $(REFRESH) --repro $(REPRO) --final $(FINAL)

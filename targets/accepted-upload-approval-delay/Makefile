# Included by the root Makefile. Child order is defined in target.yaml.
.PHONY: accepted-upload-approval-delay
accepted-upload-approval-delay: analysis-pipeline-upload-approval
	$(PYTHON) shared/python/analysis/build_target.py accepted-upload-approval-delay --refresh $(REFRESH) --repro $(REPRO) --final $(FINAL)

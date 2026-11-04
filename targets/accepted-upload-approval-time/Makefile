# Included by the root Makefile. Child order is defined in target.yaml.
.PHONY: accepted-upload-approval-time
accepted-upload-approval-time: accepted-upload-approval-delay
	$(PYTHON) shared/python/analysis/build_target.py accepted-upload-approval-time --refresh $(REFRESH) --repro $(REPRO) --final $(FINAL)

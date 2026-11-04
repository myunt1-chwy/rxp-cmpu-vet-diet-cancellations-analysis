# Included by the root Makefile. Child order is defined in target.yaml.
.PHONY: upload-approval-channel-distribution
upload-approval-channel-distribution: uploaded-prescription-approval-channels
	$(PYTHON) shared/python/analysis/build_target.py upload-approval-channel-distribution --refresh $(REFRESH) --repro $(REPRO) --final $(FINAL)

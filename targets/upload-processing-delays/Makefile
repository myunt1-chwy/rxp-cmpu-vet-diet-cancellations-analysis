# Included by the root Makefile. Child order is defined in target.yaml.
.PHONY: upload-processing-delays
upload-processing-delays: study-population-context prescription-upload-coverage customer-upload-delay upload-processing-time accepted-upload-approval-time
	$(PYTHON) shared/python/analysis/build_target.py upload-processing-delays --refresh $(REFRESH) --repro $(REPRO) --final $(FINAL)

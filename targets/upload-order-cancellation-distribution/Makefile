# Included by the root Makefile. Child order is defined in target.yaml.
.PHONY: upload-order-cancellation-distribution
upload-order-cancellation-distribution: uploaded-order-cancellation-reasons
	$(PYTHON) shared/analysis/build_target.py upload-order-cancellation-distribution --refresh $(REFRESH) --repro $(REPRO) --final $(FINAL)

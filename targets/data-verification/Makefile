# Included by the root Makefile. Child order is defined in target.yaml.
.PHONY: data-verification
data-verification: upload-source-origins upload-approval-channel-distribution upload-coverage-by-rx-status upload-order-cancellation-distribution null-resource-order-cancellations data-source-connections
	$(PYTHON) shared/python/analysis/build_target.py data-verification --refresh $(REFRESH) --repro $(REPRO) --final $(FINAL)

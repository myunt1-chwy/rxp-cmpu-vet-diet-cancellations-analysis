# Included by the root Makefile. Child order is defined in target.yaml.
.PHONY: null-resource-order-cancellations
null-resource-order-cancellations: null-resource-cancellation-reasons
	$(PYTHON) shared/analysis/build_target.py null-resource-order-cancellations --refresh $(REFRESH) --repro $(REPRO) --final $(FINAL)

# Included by the root Makefile. Child order is defined in target.yaml.
.PHONY: customer-upload-delay
customer-upload-delay: upload-delay-from-order-creation
	$(PYTHON) shared/python/analysis/build_target.py customer-upload-delay --refresh $(REFRESH) --repro $(REPRO) --final $(FINAL)

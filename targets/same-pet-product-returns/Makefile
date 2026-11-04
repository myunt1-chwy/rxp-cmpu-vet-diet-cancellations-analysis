# Included by the root Makefile. Child order is defined in target.yaml.
.PHONY: same-pet-product-returns
same-pet-product-returns: same-pet-product-return-comparison
	$(PYTHON) shared/analysis/build_target.py same-pet-product-returns --refresh $(REFRESH) --repro $(REPRO) --final $(FINAL)

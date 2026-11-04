# Included by the root Makefile. Child order is defined in target.yaml.
.PHONY: same-pet-other-product-returns
same-pet-other-product-returns: same-pet-other-product-return-comparison
	$(PYTHON) shared/python/analysis/build_target.py same-pet-other-product-returns --refresh $(REFRESH) --repro $(REPRO) --final $(FINAL)

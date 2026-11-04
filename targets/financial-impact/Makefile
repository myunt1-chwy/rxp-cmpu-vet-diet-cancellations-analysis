# Included by the root Makefile. Child order is defined in target.yaml.
.PHONY: financial-impact
financial-impact: estimated-sales-loss same-pet-product-returns same-pet-other-product-returns any-vet-diet-returns any-chewy-returns
	$(PYTHON) shared/python/analysis/build_target.py financial-impact --refresh $(REFRESH) --repro $(REPRO) --final $(FINAL)

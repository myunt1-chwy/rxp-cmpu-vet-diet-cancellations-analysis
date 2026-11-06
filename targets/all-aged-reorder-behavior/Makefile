# Included by the root Makefile. Child order is defined in target.yaml.
.PHONY: all-aged-reorder-behavior
all-aged-reorder-behavior: same-pet-product-return-comparison non-autoship-all-aged-returns autoship-initiated-or-non-autoship-all-aged same-pet-other-product-return-comparison any-vet-diet-return-comparison any-chewy-return-comparison
	$(PYTHON) shared/python/analysis/build_target.py all-aged-reorder-behavior --refresh $(REFRESH) --repro $(REPRO) --final $(FINAL)

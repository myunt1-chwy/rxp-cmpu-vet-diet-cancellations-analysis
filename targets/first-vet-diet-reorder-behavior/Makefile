# Included by the root Makefile. Child order is defined in target.yaml.
.PHONY: first-vet-diet-reorder-behavior
first-vet-diet-reorder-behavior: same-pet-product-first-vet-diet-returns non-autoship-first-vet-diet-returns autoship-initiated-or-non-autoship-first-vet-diet same-pet-other-product-first-vet-diet-returns any-vet-diet-first-vet-diet-returns any-chewy-first-vet-diet-returns
	$(PYTHON) shared/python/analysis/build_target.py first-vet-diet-reorder-behavior --refresh $(REFRESH) --repro $(REPRO) --final $(FINAL)

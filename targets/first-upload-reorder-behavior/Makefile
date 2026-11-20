# Included by the root Makefile. Child order is defined in target.yaml.
.PHONY: first-upload-reorder-behavior
first-upload-reorder-behavior: same-pet-product-first-upload-returns non-autoship-first-upload-returns autoship-initiated-or-non-autoship-first-upload same-pet-other-product-first-upload-returns any-vet-diet-first-upload-returns any-chewy-first-upload-returns
	$(PYTHON) shared/python/analysis/build_target.py first-upload-reorder-behavior --refresh $(REFRESH) --repro $(REPRO) --final $(FINAL)

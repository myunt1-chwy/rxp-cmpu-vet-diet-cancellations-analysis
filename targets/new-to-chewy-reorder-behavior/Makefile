# Included by the root Makefile.
.PHONY: new-to-chewy-reorder-behavior
new-to-chewy-reorder-behavior: same-pet-product-first-chewy-returns non-autoship-first-chewy-returns autoship-initiated-or-non-autoship-first-chewy same-pet-other-product-first-chewy-returns any-vet-diet-first-chewy-returns any-chewy-first-chewy-returns
	$(PYTHON) shared/python/analysis/build_target.py new-to-chewy-reorder-behavior \
		--refresh $(REFRESH) --repro $(REPRO) --final $(FINAL)

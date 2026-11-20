.PHONY: same-pet-product-return-comparison
same-pet-product-return-comparison: analysis-pipeline-non-autoship-returns
	$(PYTHON) shared/python/analysis/build_target.py same-pet-product-return-comparison --refresh $(REFRESH) --repro $(REPRO) --final $(FINAL)

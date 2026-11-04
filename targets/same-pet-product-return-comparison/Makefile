# Included by the root Makefile. Child order is defined in target.yaml.
.PHONY: same-pet-product-return-comparison
same-pet-product-return-comparison: analysis-pipeline-financial-returns
	$(PYTHON) shared/python/analysis/build_target.py same-pet-product-return-comparison --refresh $(REFRESH) --repro $(REPRO) --final $(FINAL)

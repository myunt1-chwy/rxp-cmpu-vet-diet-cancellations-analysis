# Included by the root Makefile. Child order is defined in target.yaml.
.PHONY: same-pet-other-product-return-comparison
same-pet-other-product-return-comparison: analysis-pipeline-financial-returns
	$(PYTHON) shared/analysis/build_target.py same-pet-other-product-return-comparison --refresh $(REFRESH) --repro $(REPRO) --final $(FINAL)

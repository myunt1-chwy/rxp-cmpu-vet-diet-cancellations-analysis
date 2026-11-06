# Included by the root Makefile. Child order is defined in target.yaml.
.PHONY: medium-term-reorder-behavior
medium-term-reorder-behavior: all-aged-reorder-behavior first-upload-reorder-behavior first-vet-diet-reorder-behavior new-to-chewy-reorder-behavior
	$(PYTHON) shared/python/analysis/build_target.py medium-term-reorder-behavior --refresh $(REFRESH) --repro $(REPRO) --final $(FINAL)

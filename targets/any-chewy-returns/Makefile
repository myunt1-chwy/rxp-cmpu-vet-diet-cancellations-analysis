# Included by the root Makefile. Child order is defined in target.yaml.
.PHONY: any-chewy-returns
any-chewy-returns: any-chewy-return-comparison
	$(PYTHON) shared/python/analysis/build_target.py any-chewy-returns --refresh $(REFRESH) --repro $(REPRO) --final $(FINAL)

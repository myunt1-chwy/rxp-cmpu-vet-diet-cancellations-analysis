# Included by the root Makefile. Child order is defined in target.yaml.
.PHONY: any-chewy-return-comparison
any-chewy-return-comparison: analysis-pipeline-financial-returns
	$(PYTHON) shared/analysis/build_target.py any-chewy-return-comparison --refresh $(REFRESH) --repro $(REPRO) --final $(FINAL)

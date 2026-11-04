# Included by the root Makefile. Child order is defined in target.yaml.
.PHONY: any-vet-diet-return-comparison
any-vet-diet-return-comparison: analysis-pipeline-financial-returns
	$(PYTHON) shared/analysis/build_target.py any-vet-diet-return-comparison --refresh $(REFRESH) --repro $(REPRO) --final $(FINAL)

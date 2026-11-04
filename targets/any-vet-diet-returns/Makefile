# Included by the root Makefile. Child order is defined in target.yaml.
.PHONY: any-vet-diet-returns
any-vet-diet-returns: any-vet-diet-return-comparison
	$(PYTHON) shared/analysis/build_target.py any-vet-diet-returns --refresh $(REFRESH) --repro $(REPRO) --final $(FINAL)

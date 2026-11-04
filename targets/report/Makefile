# Included by the root Makefile. Child order is defined in target.yaml.
.PHONY: report
report: executive-summary next-steps appendix
	$(PYTHON) shared/analysis/build_target.py report --refresh $(REFRESH) --repro $(REPRO) --final $(FINAL)

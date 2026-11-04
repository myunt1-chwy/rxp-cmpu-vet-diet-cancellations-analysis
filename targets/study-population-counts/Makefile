# Included by the root Makefile. Child order is defined in target.yaml.
.PHONY: study-population-counts
study-population-counts: analysis-pipeline-study-population
	$(PYTHON) shared/analysis/build_target.py study-population-counts --refresh $(REFRESH) --repro $(REPRO) --final $(FINAL)

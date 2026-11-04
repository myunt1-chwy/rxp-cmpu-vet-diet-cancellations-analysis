# Included by the root Makefile. Child order is defined in target.yaml.
.PHONY: study-prescription-decisions
study-prescription-decisions: analysis-pipeline-study-population
	$(PYTHON) shared/analysis/build_target.py study-prescription-decisions --refresh $(REFRESH) --repro $(REPRO) --final $(FINAL)

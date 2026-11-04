# Included by the root Makefile. Child order is defined in target.yaml.
.PHONY: source-grains-and-counting
source-grains-and-counting: analysis-pipeline-diagrams
	$(PYTHON) shared/analysis/build_target.py source-grains-and-counting --refresh $(REFRESH) --repro $(REPRO) --final $(FINAL)

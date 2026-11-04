# Included by the root Makefile. Child order is defined in target.yaml.
.PHONY: report-source-overview
report-source-overview: analysis-pipeline-diagrams
	$(PYTHON) shared/python/analysis/build_target.py report-source-overview --refresh $(REFRESH) --repro $(REPRO) --final $(FINAL)

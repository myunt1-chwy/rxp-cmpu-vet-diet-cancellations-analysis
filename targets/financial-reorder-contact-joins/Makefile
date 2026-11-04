# Included by the root Makefile. Child order is defined in target.yaml.
.PHONY: financial-reorder-contact-joins
financial-reorder-contact-joins: analysis-pipeline-diagrams
	$(PYTHON) shared/analysis/build_target.py financial-reorder-contact-joins --refresh $(REFRESH) --repro $(REPRO) --final $(FINAL)

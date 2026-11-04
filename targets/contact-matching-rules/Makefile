# Included by the root Makefile. Child order is defined in target.yaml.
.PHONY: contact-matching-rules
contact-matching-rules: analysis-pipeline-diagrams
	$(PYTHON) shared/python/analysis/build_target.py contact-matching-rules --refresh $(REFRESH) --repro $(REPRO) --final $(FINAL)

# Included by the root Makefile. Child order is defined in target.yaml.
.PHONY: contact-days-relative-to-cancellation
contact-days-relative-to-cancellation: analysis-pipeline-contacts
	$(PYTHON) shared/python/analysis/build_target.py contact-days-relative-to-cancellation --refresh $(REFRESH) --repro $(REPRO) --final $(FINAL)

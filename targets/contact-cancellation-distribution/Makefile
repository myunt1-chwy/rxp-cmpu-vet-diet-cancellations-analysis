# Included by the root Makefile. Child order is defined in target.yaml.
.PHONY: contact-cancellation-distribution
contact-cancellation-distribution: analysis-pipeline-contact-reasons
	$(PYTHON) shared/analysis/build_target.py contact-cancellation-distribution --refresh $(REFRESH) --repro $(REPRO) --final $(FINAL)

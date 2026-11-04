# Included by the root Makefile. Child order is defined in target.yaml.
.PHONY: appendix
appendix: financial-impact customer-contact-patterns upload-processing-delays aged-order-risk data-verification
	$(PYTHON) shared/analysis/build_target.py appendix --refresh $(REFRESH) --repro $(REPRO) --final $(FINAL)

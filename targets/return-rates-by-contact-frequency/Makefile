# Included by the root Makefile. Child order is defined in target.yaml.
.PHONY: return-rates-by-contact-frequency
return-rates-by-contact-frequency: analysis-pipeline-contact-frequency
	$(PYTHON) shared/python/analysis/build_target.py return-rates-by-contact-frequency --refresh $(REFRESH) --repro $(REPRO) --final $(FINAL)

# Included by the root Makefile. Child order is defined in target.yaml.
.PHONY: return-rates-by-contact-window
return-rates-by-contact-window: analysis-pipeline-contact-window
	$(PYTHON) shared/python/analysis/build_target.py return-rates-by-contact-window --refresh $(REFRESH) --repro $(REPRO) --final $(FINAL)

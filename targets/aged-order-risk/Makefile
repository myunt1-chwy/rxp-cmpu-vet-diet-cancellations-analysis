# Included by the root Makefile. Child order is defined in target.yaml.
.PHONY: aged-order-risk
aged-order-risk: first-order-event-free-survival
	$(PYTHON) shared/python/analysis/build_target.py aged-order-risk --refresh $(REFRESH) --repro $(REPRO) --final $(FINAL)

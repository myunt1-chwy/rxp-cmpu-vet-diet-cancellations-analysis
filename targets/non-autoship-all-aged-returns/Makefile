.PHONY: non-autoship-all-aged-returns
non-autoship-all-aged-returns: analysis-pipeline-non-autoship-returns
	$(PYTHON) shared/python/analysis/build_target.py non-autoship-all-aged-returns --refresh $(REFRESH) --repro $(REPRO) --final $(FINAL)

.PHONY: first-shipped-or-non-autoship-70d
first-shipped-or-non-autoship-70d:
	PYTHONPATH=. $(PYTHON) targets/non-autoship-all-aged-returns/src/python/build_returns.py --refresh $(REFRESH)

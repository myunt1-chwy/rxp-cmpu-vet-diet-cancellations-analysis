.PHONY: autoship-initiated-or-non-autoship-all-aged
autoship-initiated-or-non-autoship-all-aged: analysis-pipeline-non-autoship-returns
	$(PYTHON) shared/python/analysis/build_target.py autoship-initiated-or-non-autoship-all-aged --refresh $(REFRESH) --repro $(REPRO) --final $(FINAL)

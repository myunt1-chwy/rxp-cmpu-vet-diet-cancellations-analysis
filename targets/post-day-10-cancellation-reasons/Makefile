# Included by the root Makefile.
.PHONY: post-day-10-cancellation-reasons post-day-10-cancellation-reasons-data
post-day-10-cancellation-reasons-data:
	PYTHONPATH=. $(PYTHON) targets/post-day-10-cancellation-reasons/src/python/build_post_day_10_cancellation_reasons.py --refresh $(REFRESH)

post-day-10-cancellation-reasons: post-day-10-cancellation-reasons-data
	$(PYTHON) shared/python/analysis/build_target.py post-day-10-cancellation-reasons \
		--refresh $(REFRESH) --repro $(REPRO) --final $(FINAL)

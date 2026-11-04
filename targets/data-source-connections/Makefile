# Included by the root Makefile. Child order is defined in target.yaml.
.PHONY: data-source-connections
data-source-connections: report-source-overview source-grains-and-counting upload-verification-joins prescription-first-order-joins financial-reorder-contact-joins contact-matching-rules
	$(PYTHON) shared/python/analysis/build_target.py data-source-connections --refresh $(REFRESH) --repro $(REPRO) --final $(FINAL)

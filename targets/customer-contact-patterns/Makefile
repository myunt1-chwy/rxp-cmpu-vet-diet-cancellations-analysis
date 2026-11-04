# Included by the root Makefile. Child order is defined in target.yaml.
.PHONY: customer-contact-patterns
customer-contact-patterns: contacts-by-cancellation-reason contact-timing contact-frequency contact-frequency-and-returns contact-proximity-and-returns
	$(PYTHON) shared/analysis/build_target.py customer-contact-patterns --refresh $(REFRESH) --repro $(REPRO) --final $(FINAL)

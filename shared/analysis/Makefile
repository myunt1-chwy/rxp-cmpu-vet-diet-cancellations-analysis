# Shared extraction/validation batches, run once per make invocation.
.PHONY: analysis-pipeline-financial-baseline
analysis-pipeline-financial-baseline:
	$(PYTHON) shared/analysis/run_pipeline.py financial-baseline --refresh $(REFRESH)

.PHONY: analysis-pipeline-financial-returns
analysis-pipeline-financial-returns:
	$(PYTHON) shared/analysis/run_pipeline.py financial-returns --refresh $(REFRESH)

.PHONY: analysis-pipeline-contacts
analysis-pipeline-contacts:
	$(PYTHON) shared/analysis/run_pipeline.py contacts --refresh $(REFRESH)

.PHONY: analysis-pipeline-contact-reasons
analysis-pipeline-contact-reasons:
	$(PYTHON) shared/analysis/run_pipeline.py contact-reasons --refresh $(REFRESH)

.PHONY: analysis-pipeline-contact-frequency
analysis-pipeline-contact-frequency:
	$(PYTHON) shared/analysis/run_pipeline.py contact-frequency --refresh $(REFRESH)

.PHONY: analysis-pipeline-contact-window
analysis-pipeline-contact-window: analysis-pipeline-contact-frequency
	$(PYTHON) shared/analysis/run_pipeline.py contact-window --refresh $(REFRESH)

.PHONY: analysis-pipeline-study-population
analysis-pipeline-study-population:
	$(PYTHON) shared/analysis/run_pipeline.py study-population --refresh $(REFRESH)

.PHONY: analysis-pipeline-upload-coverage
analysis-pipeline-upload-coverage: analysis-pipeline-study-population
	$(PYTHON) shared/analysis/run_pipeline.py upload-coverage --refresh $(REFRESH)

.PHONY: analysis-pipeline-first-order-status
analysis-pipeline-first-order-status:
	$(PYTHON) shared/analysis/run_pipeline.py first-order-status --refresh $(REFRESH)

.PHONY: analysis-pipeline-upload-creation
analysis-pipeline-upload-creation:
	$(PYTHON) shared/analysis/run_pipeline.py upload-creation --refresh $(REFRESH)

.PHONY: analysis-pipeline-upload-state
analysis-pipeline-upload-state:
	$(PYTHON) shared/analysis/run_pipeline.py upload-state --refresh $(REFRESH)

.PHONY: analysis-pipeline-upload-approval
analysis-pipeline-upload-approval:
	$(PYTHON) shared/analysis/run_pipeline.py upload-approval --refresh $(REFRESH)

.PHONY: analysis-pipeline-survival
analysis-pipeline-survival:
	$(PYTHON) shared/analysis/run_pipeline.py survival --refresh $(REFRESH)

.PHONY: analysis-pipeline-verification
analysis-pipeline-verification:
	$(PYTHON) shared/analysis/run_pipeline.py verification --refresh $(REFRESH)

.PHONY: analysis-pipeline-diagrams
analysis-pipeline-diagrams:
	$(PYTHON) shared/analysis/run_pipeline.py diagrams --refresh $(REFRESH)

.PHONY: analysis-howto
analysis-howto:
	$(PYTHON) shared/analysis/howto.py

report: analysis-howto

.PHONY: analysis-refresh-preflight
analysis-refresh-preflight:
	$(PYTHON) shared/analysis/refresh_preflight.py --refresh $(REFRESH) --targets $(MAKECMDGOALS)

analysis-pipeline-financial-baseline analysis-pipeline-financial-returns analysis-pipeline-contacts analysis-pipeline-contact-reasons analysis-pipeline-contact-frequency analysis-pipeline-contact-window analysis-pipeline-study-population analysis-pipeline-upload-coverage analysis-pipeline-first-order-status analysis-pipeline-upload-creation analysis-pipeline-upload-state analysis-pipeline-upload-approval analysis-pipeline-survival analysis-pipeline-verification analysis-pipeline-diagrams: analysis-refresh-preflight

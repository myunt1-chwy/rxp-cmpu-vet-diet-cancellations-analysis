# Included by the root Makefile. Child order is defined in target.yaml.
.PHONY: upload-delay-from-order-creation
upload-delay-from-order-creation: analysis-pipeline-upload-creation
	$(PYTHON) shared/analysis/build_target.py upload-delay-from-order-creation --refresh $(REFRESH) --repro $(REPRO) --final $(FINAL)

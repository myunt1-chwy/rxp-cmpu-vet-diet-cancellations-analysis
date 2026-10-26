.DEFAULT_GOAL := setup

.PHONY: cmpu-order-to-approval-distributions
cmpu-order-to-approval-distributions:
	.venv/bin/python -m src.python.create_cmpu_order_to_approval_distributions --start-date "$(or $(START_DATE),2026-08-15)" --end-date "$(or $(END_DATE),2026-10-15)" --upload-start-date "$(or $(UPLOAD_START_DATE),2026-08-01)" $(if $(filter 1,$(PRINT_SQL)),--print-sql) $(if $(filter 1,$(CACHED)),--cached)

.PHONY: cmpu-prescription-first-order-status
cmpu-prescription-first-order-status:
	.venv/bin/python -m src.python.create_cmpu_first_order_line_status --start-date "$(or $(START_DATE),2026-08-15)" --end-date "$(or $(END_DATE),2026-10-15)" --upload-start-date "$(or $(UPLOAD_START_DATE),2026-08-01)" $(if $(filter 1,$(PRINT_SQL)),--print-sql) $(if $(filter 1,$(CACHED)),--cached)

.PHONY: create-aged-upload-lifecycle-distribution
create-aged-upload-lifecycle-distribution:
	@test -n "$(START_DATE)" -a -n "$(END_DATE)" || { echo 'START_DATE and END_DATE are required (end exclusive).' >&2; exit 1; }
	.venv/bin/python -m src.python.create_aged_upload_lifecycle_distribution --start-date "$(START_DATE)" --end-date "$(END_DATE)" $(if $(filter 1,$(PRINT_SQL)),--print-sql) $(if $(filter 1,$(CACHED)),--cached)

.PHONY: create-vdam-upload-distribution
create-vdam-upload-distribution:
	@test -n "$(START_DATE)" -a -n "$(END_DATE)" || { echo 'START_DATE and END_DATE are required (end exclusive).' >&2; exit 1; }
	.venv/bin/python src/python/create_vdam_upload_distribution.py --start-date "$(START_DATE)" --end-date "$(END_DATE)" $(if $(filter 1,$(PRINT_SQL)),--print-sql) $(if $(filter 1,$(CACHED)),--cached)

.PHONY: setup init bootstrap setup-mattpocock-skills uninstall-mattpocock-skills

bootstrap:
	@command -v uv >/dev/null 2>&1 || { echo 'Error: uv is required. Install it from https://docs.astral.sh/uv/getting-started/installation/ and rerun make setup.' >&2; exit 1; }
	@test -x .venv/bin/python || uv venv --python 3.12 .venv

setup: bootstrap
	@.venv/bin/python scripts/setup.py

init: bootstrap
	@if test -f pyproject.toml; then uv sync --python 3.12 --group dev; fi
	@.venv/bin/python scripts/setup.py --init

setup-mattpocock-skills:
	@command -v npx >/dev/null 2>&1 || { echo 'Error: npx is required. Install Node.js with npm and rerun make setup-mattpocock-skills.' >&2; exit 1; }
	npx --yes skills@latest add mattpocock/skills --skill '*' --agent codex --yes

uninstall-mattpocock-skills:
	@command -v node >/dev/null 2>&1 && command -v npx >/dev/null 2>&1 || { echo 'Error: Node.js and npx are required. Install Node.js with npm and rerun make uninstall-mattpocock-skills.' >&2; exit 1; }
	node scripts/uninstall_mattpocock_skills.mjs

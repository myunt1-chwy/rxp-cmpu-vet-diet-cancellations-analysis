.DEFAULT_GOAL := setup

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

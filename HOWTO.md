# Setup

Install [uv](https://docs.astral.sh/uv/getting-started/installation/), then run:

```sh
make init
```

Enter a project name and description, or press Enter to use
the repository folder name and the existing description (or
`Add your description here` when absent). Names must start
and end with a letter or digit and contain only letters, digits, `.`, `_`, or
`-`. Ctrl-C or end-of-input cancels without writing project configuration.

`make init` creates `.venv` with Python 3.12 (uv may download Python) and
synchronizes dependencies before prompting when configuration exists. It edits
only the project name and description, preserving dependencies, other settings,
and TOML formatting, then synchronizes again to refresh `uv.lock`. Explicitly
running `make init` again prompts again. Cancellation leaves `pyproject.toml`
unchanged; the preliminary synchronization may already have updated the
environment and lockfile.

For subsequent dependency synchronization, run `make setup`. It preserves
existing `pyproject.toml` without prompting. If configuration is absent, either
command prompts for metadata and generates it.
The initial runtime dependencies are defined in `scripts/setup.py`; the
development dependency group includes `pytest>=9.1.1` and `tomlkit>=0.13.3`.
After initialization, edit
`pyproject.toml` to change either list and rerun `make setup`.
An internet connection may be required to download Python and packages.
If dependency resolution fails, the requested constraints remain unchanged;
resolve the reported issue and rerun `make setup`.

Keep `pyproject.toml` and `uv.lock` in version control. Run Python commands
through `.venv/bin/python`.

To run the setup behavior checks after setup:

```sh
.venv/bin/python -m unittest discover -s tests
```

## Matt Pocock skills

With Node.js and npm (which provides `npx`) installed, run:

```sh
make setup-mattpocock-skills
```

This runs `npx skills@latest add mattpocock/skills` with flags to install all
skills for Codex without prompts, locally under `.agents/skills/`. It requires
internet access and does not depend on the Python environment. The CLI records
installed sources in `skills-lock.json`; keep that file and the installed skills
in version control. Rerunning the target fetches the latest upstream skills and
may overwrite local edits to those skills.

To uninstall this collection:

```sh
make uninstall-mattpocock-skills
```

This selects only entries whose source is `mattpocock/skills` in
`skills-lock.json`, then uses the CLI to remove their shared files and agent
links in this project and update the lockfile. Other skills and global
installations are preserved. Missing lockfiles or no
matching entries produce a successful no-op; invalid lockfiles report an error.
Node.js, npm, and internet access for `npx skills@latest` are required.
Uninstalling removes local edits to these skills. Run the setup target to
install them again.

See the [skills CLI reference](https://github.com/vercel-labs/skills/blob/main/docs/commands.md)
for installation options.

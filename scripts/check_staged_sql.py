"""Lint staged SQL contents without changing the index or working tree."""

import posixpath
import subprocess
import sys
import tempfile
from pathlib import Path


def git(*args):
    return subprocess.check_output(["git", *args])


def is_sql(path):
    name = path.lower()
    return (
        name.endswith(".sql")
        or any(
            name.endswith(".sql" + suffix)
            for suffix in [
                ".j2",
                ".jinja",
                ".jinja2",
                ".tmpl",
                ".tpl",
                ".template",
            ]
        )
        or (
            "sql" in Path(name).parts[:-1]
            and name.endswith(
                (".j2", ".jinja", ".jinja2", ".tmpl", ".tpl", ".template")
            )
        )
    )


def staged_source(path, seen=None):
    """Read canonical SQL through compatibility links from the index only."""
    seen = set() if seen is None else seen
    if path in seen:
        raise ValueError(f"Cyclic staged SQL link: {path}")
    seen.add(path)
    entry = git("ls-files", "--stage", "--", path).decode()
    if not entry:
        raise ValueError(f"Stage the canonical SQL source as well: {path}")
    content = git("show", ":" + path)
    if entry.startswith("120000 "):
        destination = content.decode()
        resolved = posixpath.normpath(
            posixpath.join(posixpath.dirname(path), destination)
        )
        if (
            destination.startswith("/")
            or resolved == ".."
            or resolved.startswith("../")
        ):
            raise ValueError(f"SQL link leaves the repository: {path}")
        return staged_source(resolved, seen)
    return content


def main():
    changed = (
        git("diff", "--cached", "--name-only", "--diff-filter=ACMRT", "-z")
        .decode()
        .split("\0")
    )
    # AGENTS.md excludes the playground from maintained analysis code.
    # Keep ignores disabled for every other staged SQL/template file.
    paths = [
        p
        for p in changed
        if p and is_sql(p) and not p.startswith("playground/")
    ]
    if not paths:
        return 0
    root = Path(git("rev-parse", "--show-toplevel").decode().strip())
    sqlfluff = root / ".venv/bin/sqlfluff"
    if not sqlfluff.is_file():
        print(
            "SQLFluff is missing. Run make setup before committing SQL.",
            file=sys.stderr,
        )
        return 1
    tracked = git("ls-files", "-z").decode().split("\0")
    configs = [
        p
        for p in tracked
        if Path(p).name
        in {
            ".sqlfluff",
            ".sqlfluffignore",
            "pyproject.toml",
            "setup.cfg",
            "tox.ini",
        }
    ]
    # Reproduce the index snapshot, including configuration, so unstaged edits
    # cannot make failing staged SQL appear clean. Do not execute project code.
    with tempfile.TemporaryDirectory(prefix="staged-sql-") as directory:
        snapshot = Path(directory)
        for path in dict.fromkeys(paths + configs):
            target = snapshot / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(staged_source(path))
        if not (snapshot / ".sqlfluff").exists():
            print(
                (
                    "Stage the repository .sqlfluff configuration before "
                    "committing SQL."
                ),
                file=sys.stderr,
            )
            return 1
        result = 0
        for path in paths:
            print(f"Checking staged SQL: {path}", flush=True)
            # Explicit file paths also lint .sql.j2 and other template
            # suffixes.
            status = subprocess.run(
                [
                    str(sqlfluff),
                    "lint",
                    "--ignore-local-config",
                    "--config",
                    str(snapshot / ".sqlfluff"),
                    "--disregard-sqlfluffignores",
                    path,
                ],
                check=False,
                cwd=snapshot,
            ).returncode
            result = result or status
        if result:
            print(
                (
                    "SQLFluff blocked the commit. Fix the SQL/template errors "
                    "and stage the corrected files."
                ),
                file=sys.stderr,
            )
        return result


if __name__ == "__main__":
    sys.exit(main())

"""Check staged Python lint and formatting without altering partial staging."""

import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path


def git(*args):
    return subprocess.check_output(["git", *args])


def main():
    changed = (
        git("diff", "--cached", "--name-only", "--diff-filter=ACMRT", "-z")
        .decode()
        .split("\0")
    )
    paths = [path for path in changed if path.endswith((".py", ".pyi"))]
    if not paths:
        return 0
    root = Path(git("rev-parse", "--show-toplevel").decode().strip())
    ruff = root / ".venv/bin/ruff"
    if not ruff.is_file():
        print(
            "Ruff is missing. Run make setup before committing Python.",
            file=sys.stderr,
        )
        return 1
    with tempfile.TemporaryDirectory(prefix="staged-python-") as directory:
        snapshot = Path(directory)
        for path in ["pyproject.toml", *paths]:
            entry = git("ls-files", "--stage", "--", path)
            if not entry or entry.startswith(b"120000 "):
                print(
                    f"Stage a regular source/configuration file: {path}",
                    file=sys.stderr,
                )
                return 1
            target = snapshot / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(git("show", ":" + path))
        config = tomllib.loads((snapshot / "pyproject.toml").read_text())
        if "ruff" not in config.get("tool", {}):
            print(
                "Stage the Ruff configuration in pyproject.toml.",
                file=sys.stderr,
            )
            return 1
        result = 0
        for command in (["check"], ["format", "--check"]):
            status = subprocess.run(
                [
                    str(ruff),
                    *command,
                    "--no-cache",
                    "--config",
                    str(snapshot / "pyproject.toml"),
                    "--",
                    *paths,
                ],
                cwd=snapshot,
                check=False,
            ).returncode
            result = result or status
        if result:
            print(
                "Python checks blocked the commit. Run make python-format "
                "PYTHON_PATH=<file>, fix lint errors, and stage the fixes.",
                file=sys.stderr,
            )
        return result


if __name__ == "__main__":
    sys.exit(main())

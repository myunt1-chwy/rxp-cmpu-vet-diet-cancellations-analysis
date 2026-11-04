"""Install the repository hook without replacing an unrelated hook setup."""

import subprocess
import sys
from pathlib import Path


def main():
    configured = subprocess.run(
        ["git", "config", "--get", "core.hooksPath"],
        capture_output=True,
        check=False,
        text=True,
    )
    current = configured.stdout.strip()
    if current and current != ".githooks":
        print(
            f"Existing core.hooksPath={current}; "
            "reconcile it with .githooks before installing.",
            file=sys.stderr,
        )
        return 1
    if not current:
        old = Path(
            subprocess.check_output(
                ["git", "rev-parse", "--git-path", "hooks/pre-commit"],
                text=True,
            ).strip()
        )
        if old.exists():
            print(
                f"Existing hook at {old}; "
                "reconcile it with .githooks/pre-commit before installing.",
                file=sys.stderr,
            )
            return 1
    subprocess.run(
        ["git", "config", "--local", "core.hooksPath", ".githooks"], check=True
    )
    print("Installed staged Ruff and SQLFluff pre-commit checks.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Install the repository hook without replacing an unrelated hook setup."""
from pathlib import Path
import subprocess
import sys


def main():
    configured = subprocess.run(['git', 'config', '--get', 'core.hooksPath'], capture_output=True, text=True)
    current = configured.stdout.strip()
    if current and current != '.githooks':
        print(f'Existing core.hooksPath={current}; reconcile it with .githooks before installing.', file=sys.stderr)
        return 1
    if not current:
        old = Path(subprocess.check_output(['git', 'rev-parse', '--git-path', 'hooks/pre-commit'], text=True).strip())
        if old.exists():
            print(f'Existing hook at {old}; reconcile it with .githooks/pre-commit before installing.', file=sys.stderr)
            return 1
    subprocess.run(['git', 'config', '--local', 'core.hooksPath', '.githooks'], check=True)
    print('Installed staged SQLFluff pre-commit check.')
    return 0


if __name__ == '__main__':
    sys.exit(main())

"""Lint staged SQL contents without changing the index or working tree."""
from pathlib import Path
import subprocess
import sys
import tempfile


def git(*args):
    return subprocess.check_output(['git', *args])


def is_sql(path):
    name = path.lower()
    return (name.endswith('.sql') or any(name.endswith('.sql' + suffix) for suffix in
            ['.j2', '.jinja', '.jinja2', '.tmpl', '.tpl', '.template']) or
            (name.startswith('src/sql/') and name.endswith(('.j2', '.jinja', '.jinja2', '.tmpl', '.tpl', '.template'))))


def main():
    changed = git('diff', '--cached', '--name-only', '--diff-filter=ACMR', '-z').decode().split('\0')
    paths = [p for p in changed if p and is_sql(p)]
    if not paths:
        return 0
    root = Path(git('rev-parse', '--show-toplevel').decode().strip())
    sqlfluff = root / '.venv/bin/sqlfluff'
    if not sqlfluff.is_file():
        print('SQLFluff is missing. Run make setup before committing SQL.', file=sys.stderr)
        return 1
    tracked = git('ls-files', '-z').decode().split('\0')
    configs = [p for p in tracked if Path(p).name in
               {'.sqlfluff', '.sqlfluffignore', 'pyproject.toml', 'setup.cfg', 'tox.ini'}]
    # Reproduce the index snapshot, including configuration, so unstaged edits
    # cannot make failing staged SQL appear clean. Do not execute project code.
    with tempfile.TemporaryDirectory(prefix='staged-sql-') as directory:
        snapshot = Path(directory)
        for path in dict.fromkeys(paths + configs):
            target = snapshot / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(git('show', ':' + path))
        if not (snapshot / '.sqlfluff').exists():
            print('Stage the repository .sqlfluff configuration before committing SQL.', file=sys.stderr)
            return 1
        result = 0
        for path in paths:
            print(f'Checking staged SQL: {path}', flush=True)
            # Explicit file paths also lint .sql.j2 and other template suffixes.
            status = subprocess.run([str(sqlfluff), 'lint', '--ignore-local-config',
                                     '--config', str(snapshot / '.sqlfluff'),
                                     '--disregard-sqlfluffignores', path], cwd=snapshot).returncode
            result = result or status
        if result:
            print('SQLFluff blocked the commit. Fix the SQL/template errors and stage the corrected files.', file=sys.stderr)
        return result


if __name__ == '__main__':
    sys.exit(main())

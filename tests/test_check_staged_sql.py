"""The playground exception must not weaken maintained SQL checks."""

import subprocess
from pathlib import Path


def test_playground_exclusion_preserves_maintained_sql_gate(tmp_path):
    root = Path(__file__).resolve().parents[1]

    def git(*args):
        return subprocess.check_output(["git", *args], cwd=tmp_path)

    def check():
        before = git("diff", "--cached", "--binary")
        result = subprocess.run(
            [
                str(root / ".venv/bin/python"),
                str(root / "scripts/check_staged_sql.py"),
            ],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            check=False,
        )
        assert git("diff", "--cached", "--binary") == before
        return result

    git("init", "-q")
    binary = tmp_path / ".venv/bin/sqlfluff"
    binary.parent.mkdir(parents=True)
    binary.symlink_to(root / ".venv/bin/sqlfluff")
    (tmp_path / ".sqlfluff").write_text("[sqlfluff]\ndialect = snowflake\n")
    (tmp_path / ".sqlfluffignore").write_text("*\n")
    scratch = tmp_path / "playground/scratch.sql"
    scratch.parent.mkdir()
    scratch.write_text("this is not SQL!\n")
    git("add", "-f", ".sqlfluff", ".sqlfluffignore", "playground")
    assert check().returncode == 0
    (tmp_path / "maintained.sql").write_text("this is not SQL!\n")
    git("add", "-f", "maintained.sql")
    result = check()
    assert result.returncode != 0
    assert "Checking staged SQL: maintained.sql" in result.stdout

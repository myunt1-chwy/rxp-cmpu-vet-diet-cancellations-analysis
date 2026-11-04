"""Exercise the Python commit gate against isolated Git index snapshots."""

import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CHECKER = ROOT / "scripts/check_staged_python.py"
CONFIG = (ROOT / "pyproject.toml").read_text()


def git(repo, *args):
    return subprocess.check_output(["git", *args], cwd=repo)


@pytest.fixture
def repo(tmp_path):
    git(tmp_path, "init", "-q")
    (tmp_path / "pyproject.toml").write_text(CONFIG)
    git(tmp_path, "add", "pyproject.toml")
    binary = tmp_path / ".venv/bin"
    binary.mkdir(parents=True)
    (binary / "ruff").symlink_to(ROOT / ".venv/bin/ruff")
    return tmp_path


def check(repo):
    before = git(repo, "diff", "--cached", "--binary")
    contents = {path: path.read_bytes() for path in repo.rglob("*.py")}
    result = subprocess.run(
        [str(ROOT / ".venv/bin/python"), str(CHECKER)],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )
    assert git(repo, "diff", "--cached", "--binary") == before
    assert {path: path.read_bytes() for path in contents} == contents
    return result


def stage(repo, text, filename="example.py"):
    path = repo / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    git(repo, "add", filename)
    return path


def test_good_index_ignores_unstaged_errors(repo):
    path = stage(repo, "value = 1\n")
    path.write_text("this is not valid Python!\n")
    assert check(repo).returncode == 0


@pytest.mark.parametrize(
    ("source", "diagnostic"),
    [("value=1\n", "reformatted"), ("print(missing)\n", "F821")],
)
def test_bad_index_cannot_be_hidden_by_worktree(repo, source, diagnostic):
    path = stage(repo, source)
    path.write_text("value = 1\n")
    result = check(repo)
    assert result.returncode != 0
    assert diagnostic in result.stdout + result.stderr


def test_staged_79_column_configuration_is_authoritative(repo):
    stage(repo, 'message = "' + "words " * 13 + 'end"\n')
    (repo / "pyproject.toml").write_text(
        CONFIG.replace("line-length = 79", "line-length = 120")
    )
    result = check(repo)
    assert result.returncode != 0
    assert "E501" in result.stdout


def test_playground_is_excluded(repo):
    stage(repo, "this is not valid Python!\n", "src/ignore/scratch.py")
    assert check(repo).returncode == 0


def test_missing_ruff_reports_setup_command(repo):
    stage(repo, "value = 1\n")
    (repo / ".venv/bin/ruff").unlink()
    result = check(repo)
    assert result.returncode != 0
    assert "make setup" in result.stderr


def test_missing_staged_config_cannot_use_worktree_config(repo):
    git(repo, "rm", "--cached", "pyproject.toml")
    stage(repo, "value = 1\n")
    assert check(repo).returncode != 0


def test_project_imports_do_not_depend_on_other_staged_files(repo):
    stage(
        repo,
        "import pandas as pd\n\n"
        "from shared.paths import artifact_path\n"
        "from src.python import analysis\n"
        "from tests import fixtures\n\n"
        "print(pd, artifact_path, analysis, fixtures)\n",
    )
    result = check(repo)
    assert result.returncode == 0, result.stdout + result.stderr

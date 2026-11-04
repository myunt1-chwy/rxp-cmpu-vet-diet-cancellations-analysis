"""Scaffolds attach to the real graph and build without warehouse access."""

import runpy
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).parents[1]


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "shared/analysis"))
    module = runpy.run_path(str(ROOT / "shared/analysis/scaffold.py"))
    shutil.copy(ROOT / "analysis.yaml", tmp_path)
    shutil.copytree(
        ROOT / "shared",
        tmp_path / "shared",
        ignore=shutil.ignore_patterns("__pycache__"),
    )
    for source in (ROOT / "targets").iterdir():
        if not (source / "target.yaml").exists():
            continue
        for name in (
            "target.yaml",
            "Makefile",
            "README.org",
            "src/latex/body.tex",
        ):
            path = source / name
            if path.exists():
                destination = tmp_path / "targets" / source.name / name
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy(path, destination)
    (tmp_path / "Makefile").write_text(
        f"PYTHON := {sys.executable}\nREFRESH := 0\nREPRO := 0\nFINAL := 0\n"
        "include $(wildcard targets/*/Makefile)\n"
    )
    return tmp_path, module["scaffold"]


def snapshot(root):
    return {
        str(path.relative_to(root)): path.read_bytes()
        for path in (root / "targets").rglob("*")
        if path.is_file()
    }


def test_scaffold_all_levels_and_build(workspace):
    root, scaffold = workspace
    parent = "appendix"
    for level, target in (
        ("subsection", "example-topic"),
        ("subsubsection", "example-detail"),
        ("paragraph", "example-result"),
    ):
        question = f"What does {target} show?"
        directory = scaffold(root, level, target, parent, question)
        metadata = yaml.safe_load((directory / "target.yaml").read_text())
        assert metadata["question"] == question
        assert metadata["parent"] == parent
        assert question in (directory / "README.org").read_text()
        owner = root / "targets" / parent
        assert (
            yaml.safe_load((owner / "target.yaml").read_text())["children"][-1]
            == target
        )
        assert f"{parent}: {target}" in (owner / "Makefile").read_text()
        assert (
            f"\\AnalysisChild{{{target}}}"
            in (owner / "src/latex/body.tex").read_text()
        )
        parent = target
    result = subprocess.run(
        ["make", "example-topic"],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    for target in ("example-topic", "example-detail", "example-result"):
        assert (
            root / "targets" / target / "outputs/latex/content.tex"
        ).exists()
    assert not list(root.rglob("*.parquet"))


@pytest.mark.parametrize(
    "level,target,parent,question",
    [
        ("section", "example", "report", "Why?"),
        ("paragraph", "../escape", "estimated-sales-loss", "Why?"),
        ("paragraph", "example", "appendix", "Why?"),
        ("subsection", "example", "next-steps", "Why?"),
        ("paragraph", "example", "missing", "Why?"),
        ("paragraph", "example", "estimated-sales-loss", ""),
        ("paragraph", "example", "estimated-sales-loss", "Not a question"),
        ("paragraph", "example", "estimated-sales-loss", "Why\nnow?"),
        ("paragraph", "financial-impact", "estimated-sales-loss", "Why?"),
    ],
)
def test_rejects_invalid_input_without_changes(
    workspace, level, target, parent, question
):
    root, scaffold = workspace
    before = snapshot(root)
    with pytest.raises(ValueError):
        scaffold(root, level, target, parent, question)
    assert snapshot(root) == before


def test_failed_write_restores_parent_and_removes_scaffold(
    workspace, monkeypatch
):
    root, scaffold = workspace
    before = snapshot(root)
    original = Path.write_text
    failed = False

    def fail_once(path, content, *args, **kwargs):
        nonlocal failed
        if path == root / "targets/appendix/Makefile" and not failed:
            failed = True
            raise OSError("Simulated write failure")
        return original(path, content, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", fail_once)
    with pytest.raises(OSError, match="Simulated"):
        scaffold(root, "subsection", "example", "appendix", "Why?")
    assert snapshot(root) == before
    assert not (root / "targets/example").exists()

import runpy
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]


@pytest.fixture
def format_markdown(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "shared/python/analysis"))
    return runpy.run_path(str(ROOT / "shared/python/analysis/howto.py"))[
        "format_markdown"
    ]


def test_wrapped_heading_keeps_question_and_target_together(format_markdown):
    title = "What happens when " + "the question is long " * 5 + "(`target`)"
    result = format_markdown(f"## {title}\n\n\nBody.\n")
    heading, body = result.split("\n---\n\n")
    assert " ".join(heading.splitlines()) == title
    assert body == "Body.\n"
    assert max(map(len, result.splitlines())) <= 80


def test_fenced_commands_and_blank_lines_are_preserved(format_markdown):
    code = "```sh\nmake report REFRESH=1\n\nmake report\n```"
    result = format_markdown("Before.\n\n\n" + code + "\nAfter.\n")
    assert result == "Before.\n\n" + code + "\n\nAfter.\n"


def test_long_path_keeps_filename_and_directory_intact(format_markdown):
    directory = "targets/no-recorded-cancellation-upload-statuses/src/python"
    filename = "create_study_no_cancellation_upload_details.py"
    result = format_markdown(f"Sources:\n- `{directory}/{filename}`\n")
    assert f"`{filename}`" in result
    assert f"`{directory}/`" in result
    assert result.startswith("Sources:\n\n- ")
    assert max(map(len, result.splitlines())) <= 80


def test_fenced_commands_are_never_silently_wrapped(format_markdown):
    with pytest.raises(ValueError, match="exceeds 80 columns"):
        format_markdown("```sh\nmake " + "a" * 80 + "\n```\n")

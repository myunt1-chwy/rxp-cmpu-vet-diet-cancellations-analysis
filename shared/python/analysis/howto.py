"""
Assemble root reproduction instructions from target READMEs in document
order.
"""

import re
import sys
import textwrap
from pathlib import Path

from graph import load_graph

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from shared.python.markdown_tables import write_text


def format_markdown(text):
    """Wrap prose while preserving headings, list items and fenced code."""
    output, paragraph = [], []
    prefix = ""
    code = False

    def paths(match):
        value = match[1]
        if len(value) > 76 and "/" in value and not re.search(r"\s", value):
            path = Path(value)
            return f"`{path.name}` (in `{path.parent}/`)"
        return match[0]

    def wrapped(value, first="", rest=""):
        return textwrap.wrap(
            re.sub(r"`([^`]+)`", paths, value),
            width=80,
            initial_indent=first,
            subsequent_indent=rest,
            break_long_words=False,
            break_on_hyphens=False,
        )

    def flush():
        if paragraph:
            output.extend(
                wrapped(" ".join(paragraph), prefix, " " * len(prefix))
            )
            paragraph.clear()

    def blank():
        if output and output[-1] != "":
            output.append("")

    for line in text.splitlines():
        if line.startswith("```"):
            flush()
            prefix = ""
            if not code:
                blank()
            output.append(line)
            code = not code
            if not code:
                blank()
        elif code:
            output.append(line)
        elif not line.strip():
            flush()
            prefix = ""
            blank()
        elif line.startswith("#"):
            flush()
            prefix = ""
            blank()
            if line.startswith("## "):
                # Setext headings support soft wrapping; ATX headings do not.
                output.extend(wrapped(line[3:]))
                output.append("---")
            else:
                output.append(line)
            blank()
        elif match := re.match(r"^(\s*(?:[-*+] |\d+\. ))(.*)$", line):
            flush()
            if not prefix:
                blank()
            prefix = match[1]
            paragraph.append(match[2])
        else:
            paragraph.append(line.strip())
    flush()
    result = "\n".join(output).strip() + "\n"
    for number, line in enumerate(result.splitlines(), 1):
        if len(line) > 80:
            raise ValueError(f"HOWTO line {number} exceeds 80 columns: {line}")
    return result


def main():
    targets, order = load_graph(ROOT)
    parts = [
        (
            "# Reproducing the analysis\n\nRun `make setup` to "
            "install the project environment and commit hooks. "
            "All commands below run from the repository root. "
            "Default target builds reuse cached data; "
            "`REFRESH=1` explicitly requests refresh where "
            "supported.\n\nChecks: `make validate-analysis-"
            "structure`, `make validate-analysis-sources`, "
            "`make sql-lint`, and `make sql-lint-staged`. SQL "
            "formatting is available through `make sql-format "
            "SQL_PATH=<file>`. Warehouse queries use Snowflake; "
            "local audit templates declare their DuckDB dialect. "
            "No lint rules are disabled.\n\nRetained "
            "standalone computations: `make opportunity-same-"
            "pet-part-auto-reorder CACHED=1`; `make opportunity-"
            "reorder-customer-counts` reproduces the retained "
            "42-day order-frequency exports. These command "
            "sources and instructions are under their "
            "corresponding `targets/<command>/` directories.\n"
        )
    ]
    for key in order:
        metadata = targets[key]
        title = metadata.get("question") or metadata["title"]
        parts.append(f"\n## {title} (`{key}`)\n\n")
        code = False
        for line in (
            (ROOT / "targets" / key / "README.org").read_text().splitlines()
        ):
            if line.startswith("#+TITLE:"):
                continue
            if line.startswith("#+begin_src"):
                code = True
                parts.append("```" + line.partition("src")[2].strip() + "\n")
            elif line.startswith("#+end_src"):
                code = False
                parts.append("```\n")
            elif code:
                parts.append(line + "\n")
            elif line.startswith("* "):
                parts.append("\n### " + line[2:] + "\n\n")
            else:
                parts.append(
                    re.sub(
                        r"(?<![\w=])=(\S(?:.*?\S)?)=(?=$|[\s.,;:)])",
                        r"`\1`",
                        line,
                    )
                    + "\n"
                )
    text = format_markdown("".join(parts))
    if len(text.encode()) > 1_000_000:
        raise ValueError("HOWTO exceeds the repository Markdown size limit")
    write_text(ROOT / "HOWTO.md", text)
    print(f"Assembled HOWTO.md from {len(order)} target READMEs.")


if __name__ == "__main__":
    main()

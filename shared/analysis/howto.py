"""
Assemble root reproduction instructions from target READMEs in document
order.
"""

import re
import sys
from pathlib import Path

from graph import load_graph

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from shared.python.markdown_tables import write_text


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
        parts.append("\n## " + key + ": " + title + "\n\n")
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
    text = "".join(parts)
    if len(text.encode()) > 1_000_000:
        raise ValueError("HOWTO exceeds the repository Markdown size limit")
    write_text(ROOT / "HOWTO.md", text)
    print(f"Assembled HOWTO.md from {len(order)} target READMEs.")


if __name__ == "__main__":
    main()

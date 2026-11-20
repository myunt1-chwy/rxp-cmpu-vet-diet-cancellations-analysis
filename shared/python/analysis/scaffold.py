"""Create and attach a question-led analysis unit without extracting data."""

import argparse
import re
import shutil
from pathlib import Path

import yaml
from graph import load_graph

PARENTS = {
    "paragraph": "subsubsection",
    "subsubsection": "subsection",
    "subsection": "section",
}


def scaffold(root, level, target_id, parent, question):
    """Validate first; restore parent files if creation fails."""
    root = Path(root)
    if level not in PARENTS:
        raise ValueError("Choose paragraph, subsubsection or subsection")
    if not re.fullmatch(r"[a-z][a-z0-9]*(?:-[a-z0-9]+)*", target_id):
        raise ValueError("ID must use lowercase words separated by hyphens")
    question = question.strip()
    if (
        len(question) < 2
        or not question.endswith("?")
        or any(ord(char) < 32 for char in question)
    ):
        raise ValueError("Provide a single-line question ending in ?")
    targets, _ = load_graph(root)
    directory = root / "targets" / target_id
    if directory.exists() or directory.is_symlink():
        raise ValueError(f"Target path already exists: {directory}")
    makefiles = [root / "Makefile", *root.glob("targets/*/Makefile")]
    makefiles.extend(root.glob("shared/**/Makefile"))
    for path in makefiles:
        if re.search(
            rf"^{re.escape(target_id)}\s*:", path.read_text(), re.MULTILINE
        ):
            raise ValueError(f"Make target already exists: {target_id}")
    if parent not in targets or targets[parent]["level"] != PARENTS[level]:
        raise ValueError(f"{level} requires a {PARENTS[level]} parent")
    if level == "subsection" and parent != "appendix":
        raise ValueError("Analysis subsections belong under appendix")

    owner = root / "targets" / parent
    originals = {
        owner / name: (owner / name).read_text()
        for name in ("target.yaml", "Makefile", "src/latex/body.tex")
    }
    body_path = owner / "src/latex/body.tex"
    children = targets[parent]["children"]
    if re.findall(r"\\AnalysisChild\{([^}]+)\}", originals[body_path]) != (
        children
    ):
        raise ValueError("Parent LaTeX child order differs from metadata")
    metadata = {
        "id": target_id,
        "level": level,
        "parent": parent,
        "children": [],
        "question": question,
        "shared_dependencies": ["analysis", "python/analysis"],
        "data_dependencies": [],
    }
    files = {
        "target.yaml": yaml.safe_dump(metadata, sort_keys=False),
        "Makefile": (
            "# Included by the root Makefile.\n"
            f".PHONY: {target_id}\n{target_id}:\n"
            "\t$(PYTHON) shared/python/analysis/build_target.py "
            f"{target_id} \\\n"
            "\t\t--refresh $(REFRESH) --repro $(REPRO) --final $(FINAL)\n"
        ),
        "README.org": (
            f"#+TITLE: {question}\n\n"
            "* Question\n" + question + "\n\n"
            "* Inputs and dependencies\n"
            "Scaffold only: no data or extraction pipeline yet.\n"
            f"Parent: ={parent}=. "
            "Shared renderer: =shared/python/analysis/=.\n\n"
            "* Build\n"
            "Run from the repository root; it includes this target Makefile.\n"
            "#+begin_src sh\n"
            f"make {target_id} \\\n  REFRESH=0 REPRO=0 FINAL=0\n"
            f"make {target_id} \\\n  REFRESH=1 REPRO=0 FINAL=0\n"
            "#+end_src\n"
            "REFRESH currently performs no extraction. Add validated cached\n"
            "and refresh paths before adding data. REPRO includes these\n"
            "instructions; FINAL controls the report draft setting.\n\n"
            "* Outputs\n"
            "Generated LaTeX: =outputs/latex/content.tex= in this target.\n\n"
            "* Remaining work\n"
            "Replace placeholder prose and document inputs and parameters.\n"
            "Paragraphs allow at most one visual; parents assemble children.\n"
        ),
        "src/latex/body.tex": (
            "% TODO: Replace this scaffold before publishing results.\n"
            "Analysis pending.\n"
        ),
    }
    if level == "paragraph":
        files["src/latex/visual.tex"] = ""
    updated_parent = dict(targets[parent], children=[*children, target_id])
    updates = {
        owner / "target.yaml": yaml.safe_dump(updated_parent, sort_keys=False),
        owner / "Makefile": originals[owner / "Makefile"].rstrip()
        + f"\n\n{parent}: {target_id}\n",
        body_path: originals[body_path].rstrip()
        + f"\n\n\\AnalysisChild{{{target_id}}}\n",
    }
    directory.mkdir()
    try:
        for name, content in files.items():
            path = directory / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)
        for path, content in updates.items():
            path.write_text(content)
        load_graph(root)
    except Exception:
        for path, content in originals.items():
            path.write_text(content)
        shutil.rmtree(directory)
        raise
    return directory


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("level", choices=PARENTS)
    parser.add_argument("--id", required=True, dest="target_id")
    parser.add_argument("--parent", required=True)
    parser.add_argument("--question", required=True)
    args = parser.parse_args()
    try:
        directory = scaffold(
            Path(__file__).resolve().parents[3],
            args.level,
            args.target_id,
            args.parent,
            args.question,
        )
    except (ValueError, OSError) as error:
        parser.exit(1, f"Scaffold failed: {error}\n")
    print(f"Created {directory}; appended to {args.parent}.")
    print("Edit the placeholder prose, then run make analysis-howto.")


if __name__ == "__main__":
    main()

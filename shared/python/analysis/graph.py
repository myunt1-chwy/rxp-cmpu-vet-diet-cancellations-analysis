"""Validate and traverse the explicit analysis document hierarchy."""

from pathlib import Path

import yaml

LEVELS = ["document", "section", "subsection", "subsubsection", "paragraph"]
FIXED = {"executive-summary": "Executive summary", "appendix": "Appendix"}


def load_graph(root):
    root = Path(root)
    document = yaml.safe_load((root / "analysis.yaml").read_text())
    targets = {}
    for path in sorted((root / "targets").glob("*/target.yaml")):
        item = yaml.safe_load(path.read_text())
        key = item["id"]
        if key != path.parent.name or key in targets:
            raise ValueError(f"Duplicate or misplaced target: {key}")
        if item["level"] not in LEVELS:
            raise ValueError(f"Invalid level: {key}")
        if not isinstance(item["children"], list) or len(
            set(item["children"])
        ) != len(item["children"]):
            raise ValueError(f"Invalid or repeated children: {key}")
        if key in FIXED:
            if item["title"] != FIXED[key] or item["question"] is not None:
                raise ValueError(f"Invalid fixed heading: {key}")
        elif item["level"] != "document" and (
            not isinstance(item["question"], str)
            or not item["question"].rstrip().endswith("?")
        ):
            raise ValueError(f"Target needs an agreed question: {key}")
        for name in ["Makefile", "README.org"]:
            if not (path.parent / name).is_file():
                raise ValueError(f"Missing {name}: {key}")
        for shared in item.get("shared_dependencies", []):
            resolved = (root / "shared" / shared).resolve()
            if (
                not resolved.is_relative_to((root / "shared").resolve())
                or not resolved.exists()
            ):
                raise ValueError(f"Invalid shared dependency: {key}: {shared}")
        targets[key] = item
    if document["document"] != "report" or document["sections"] != [
        "executive-summary",
        "next-steps",
        "appendix",
    ]:
        raise ValueError("Unexpected main-document structure")
    if (
        targets["report"]["parent"] is not None
        or targets["report"]["children"] != document["sections"]
    ):
        raise ValueError("Report metadata differs from analysis.yaml")
    visited = set()
    ordered = []

    def visit(key, parent, level):
        if key in visited:
            raise ValueError(f"Cycle or multiple ownership: {key}")
        if key not in targets:
            raise ValueError(f"Missing child: {key}")
        item = targets[key]
        if item["parent"] != parent or item["level"] != LEVELS[level]:
            raise ValueError(f"Parent/level mismatch: {key}")
        if item["level"] == "paragraph" and item["children"]:
            raise ValueError(f"Paragraph cannot have children: {key}")
        visited.add(key)
        ordered.append(key)
        for child in item["children"]:
            visit(child, key, level + 1)

    visit("report", None, 0)
    if visited != set(targets):
        raise ValueError(f"Orphan targets: {sorted(set(targets) - visited)}")
    return targets, ordered

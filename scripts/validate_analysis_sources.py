"""
Check canonical source ownership and compatibility without accessing data.
"""

import ast
import re
import sys
from pathlib import Path

import yaml
from jinja2 import Environment, StrictUndefined

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from shared.python.paths import (
    artifact_ownership,
    artifact_path,
    canonical_sql_path,
    source_ownership,
)


def main():
    for retired in (
        "src",
        "data",
        "shared/retained",
        "shared/sql",
        "targets/report/src/latex/retained",
    ):
        if (ROOT / retired).exists():
            raise ValueError(
                f"Retired source/data directory was recreated: {retired}"
            )
    for source in (ROOT / "shared").rglob("*.py"):
        if not source.is_relative_to(ROOT / "shared/python"):
            raise ValueError(
                f"Shared Python belongs under shared/python: {source}"
            )
    registry = source_ownership()
    for shared_source in (ROOT / "shared/python").glob("*.py"):
        if shared_source.name.startswith(("create_", "recreate_")):
            raise ValueError(
                f"Generator must have a target owner: {shared_source}"
            )
        tree = ast.parse(shared_source.read_text())
        if any(
            isinstance(node, ast.FunctionDef) and node.name == "main"
            for node in tree.body
        ):
            raise ValueError(
                f"Analysis CLI belongs in a target: {shared_source}"
            )
    templates = set()
    for name, relative in registry["modules"].items():
        path = ROOT / relative
        if not relative.startswith(("targets/", "shared/python/")):
            raise ValueError(
                f"Module needs a target or shared helper owner: {relative}"
            )
        if path.stem != name:
            raise ValueError(f"Module name differs from source: {relative}")
        tree = ast.parse(path.read_text(), filename=relative)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not isinstance(
                node.func, ast.Name
            ):
                continue
            if node.func.id == "module_sql":
                filename = ast.literal_eval(node.args[1])
                template = path.parent.parent / "sql" / filename
                Environment(undefined=StrictUndefined).parse(
                    template.read_text()
                )
                templates.add(template)
            elif node.func.id == "canonical_sql_path" and isinstance(
                node.args[0], ast.Constant
            ):
                if not canonical_sql_path(node.args[0].value).is_file():
                    raise ValueError(f"Missing query: {node.args[0].value}")
    for name, relative in registry["queries"].items():
        canonical = ROOT / relative
        if not relative.startswith("targets/"):
            raise ValueError(f"SQL needs a target owner: {relative}")
        if not canonical.is_file():
            raise ValueError(f"Missing canonical SQL source: {name}")
        if canonical.name.endswith(".sql.j2"):
            Environment(undefined=StrictUndefined).parse(canonical.read_text())
            templates.add(canonical)
        if re.search(
            r"PARSE_JSON\s*\(\s*[\'\"]?\s*(?:\{\{|__RX_IDS_JSON__)",
            canonical.read_text(),
            re.IGNORECASE,
        ):
            raise ValueError(
                f"External JSON query input is forbidden; derive a "
                f"database CTE: {name}"
            )
        if re.search(
            r"\{\{\s*(?:requested_keys|upload_sql)\s*\}\}",
            canonical.read_text(),
        ):
            raise ValueError(
                f"Host-generated SQL fragment is forbidden: {name}"
            )
    for metadata in (ROOT / "targets").glob("*/target.yaml"):
        target = yaml.safe_load(metadata.read_text())
        references = [target.get("migration", {}).get("source")]
        references += [a["source"] for a in target.get("images", [])]
        for reference in filter(None, references):
            if not reference.startswith("targets/"):
                raise ValueError(f"Source needs a target owner: {reference}")
        for source in target.get("sources", []) + target.get(
            "code_dependencies", []
        ):
            if not (ROOT / source).is_file():
                raise ValueError(
                    f"Missing declared source for {target['id']}: {source}"
                )
    ownership = artifact_ownership()
    for old_path, destination in ownership.get("path_prefixes", {}).items():
        if old_path.startswith("src/latex/") and (
            not destination.startswith("targets/")
            or not (ROOT / destination).is_file()
        ):
            raise ValueError(f"Missing target-owned LaTeX: {destination}")
    for dataset, owner in ownership["datasets"].items():
        if not (ROOT / "targets" / owner / "Makefile").is_file():
            raise ValueError(f"Unknown data owner: {owner}")
        expected = (
            ROOT / "targets" / owner / "data" / dataset / "source.parquet"
        )
        if (
            artifact_path(ROOT / "data" / dataset / "source.parquet")
            != expected
        ):
            raise ValueError(f"Incorrect dataset routing: {dataset}")
    print(
        f"Verified {len(registry['modules'])} Python modules, "
        f"{len(registry['queries'])} canonical queries and {len(templates)} "
        f"extracted templates."
    )


if __name__ == "__main__":
    main()

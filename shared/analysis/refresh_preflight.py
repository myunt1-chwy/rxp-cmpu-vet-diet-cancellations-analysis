"""Reject unsupported graph refreshes before any extraction batch starts."""

import argparse
from pathlib import Path

import yaml
from graph import load_graph


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh", choices=["0", "1"], default="0")
    parser.add_argument("--targets", nargs="*", default=[])
    args = parser.parse_args()
    if args.refresh == "0":
        return
    root = Path(__file__).resolve().parents[2]
    targets, _ = load_graph(root)
    pipelines = yaml.safe_load(
        (root / "shared/analysis/pipelines.yaml").read_text()
    )
    selected = set()

    def visit(key):
        if key not in targets:
            return
        metadata = targets[key]
        if metadata.get("pipeline"):
            selected.add(metadata["pipeline"])
        for child in metadata["children"]:
            visit(child)

    for key in args.targets:
        visit(key)
    errors = [
        key + ": " + pipelines[key]["refresh_error"]
        for key in sorted(selected)
        if pipelines[key].get("refresh_error")
    ]
    if errors:
        parser.exit(
            1,
            "Refresh stopped before warehouse access:\n"
            + "\n".join(errors)
            + "\n",
        )


if __name__ == "__main__":
    main()

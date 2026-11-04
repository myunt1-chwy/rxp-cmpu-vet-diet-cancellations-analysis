"""
Build one question-led unit after Make has built its declared
prerequisites.
"""

import argparse
import shutil
from pathlib import Path

from graph import load_graph
from paragraph_artifacts import generate
from preview import preview


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("target")
    parser.add_argument("--refresh", choices=["0", "1"], default="0")
    parser.add_argument("--repro", choices=["0", "1"], default="0")
    parser.add_argument("--final", choices=["0", "1"], default="0")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    targets, _ = load_graph(root)
    metadata = targets[args.target]
    for child in metadata["children"]:
        if not (
            root / "targets" / child / "outputs/latex/content.tex"
        ).is_file():
            parser.error(
                f"Missing child output: make {child} before assembling "
                f"{args.target}"
            )
    if metadata["level"] == "paragraph":
        generate(metadata)
    preview(
        int(args.repro),
        int(args.final),
        args.target == "report",
        only={args.target},
        live=True,
    )
    if args.target == "report":
        source = root / (
            "targets/report/outputs/reports/pdf/phds-cmpu-aged-"
            "orders-analysis.pdf"
        )
        destination = root / "outputs/reports/pdf" / source.name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        print("Report:", destination)


if __name__ == "__main__":
    main()

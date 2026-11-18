"""Accept reviewed figures as the results a target's authored prose describes.

Records each image's sha256 in target.yaml with a line edit, so the file's
formatting is preserved. Images with generated prose values need no record.
"""

import argparse
import hashlib
from pathlib import Path

import yaml


def record(lines, source, digest):
    start = lines.index("- source: " + source)
    end = start + 1
    while end < len(lines) and lines[end].startswith("  "):
        end += 1
    entry = [
        line for line in lines[start:end] if not line.startswith("  sha256:")
    ]
    return lines[:start] + entry + ["  sha256: " + digest] + lines[end:]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("targets", nargs="+")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[3]
    for key in args.targets:
        path = root / "targets" / key / "target.yaml"
        lines = path.read_text().splitlines()
        for asset in yaml.safe_load(path.read_text()).get("images", []):
            if "prose_values" in asset:
                continue
            digest = hashlib.sha256(
                (root / asset["source"]).read_bytes()
            ).hexdigest()
            try:
                lines = record(lines, asset["source"], digest)
            except ValueError:
                parser.error(f"{key}: cannot locate {asset['source']}")
            print(f"{key}: {asset['source']} {digest}")
        path.write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()

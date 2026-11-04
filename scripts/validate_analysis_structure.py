"""Check target metadata without building or refreshing any analysis."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "shared/analysis"))
from graph import load_graph

if __name__ == "__main__":
    targets, ordered = load_graph(ROOT)
    active = sum(
        t.get("migration", {}).get("status") == "active"
        for t in targets.values()
    )
    paragraphs = sum(
        t["level"] == "paragraph" and bool(t.get("pipeline"))
        for t in targets.values()
    )
    print(
        f"Valid hierarchy: {len(ordered)} targets; {active} active; "
        f"{paragraphs} paragraph pipelines."
    )

"""Import target-owned analytical modules by their stable module names."""

from pathlib import Path

import yaml

_root = Path(__file__).resolve().parents[2]
_registry = yaml.safe_load(
    (_root / "shared/source-ownership.yaml").read_text()
)
__path__ = sorted(
    {str((_root / path).parent) for path in _registry["modules"].values()}
)

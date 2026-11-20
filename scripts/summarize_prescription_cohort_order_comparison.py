"""
Compatibility entry point; implementation is owned by its analysis target.
"""

import runpy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
if __name__ == "__main__":
    runpy.run_module(
        "shared.python.summarize_prescription_cohort_order_comparison",
        run_name="__main__",
    )
else:
    import importlib

    _implementation = importlib.import_module(
        "shared.python.summarize_prescription_cohort_order_comparison"
    )

    sys.modules[__name__] = _implementation

    def __getattr__(name):
        """Support callers retaining an importlib-created module object."""
        return getattr(_implementation, name)

"""
Compatibility entry point; implementation is owned by its analysis target.
"""

import runpy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
if __name__ == "__main__":
    runpy.run_module(
        "shared.python.summarize_study_population_uploaded_documents",
        run_name="__main__",
    )
else:
    import importlib

    sys.modules[__name__] = importlib.import_module(
        "shared.python.summarize_study_population_uploaded_documents"
    )

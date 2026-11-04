"""Common repository paths and file fingerprints for analysis commands."""

import hashlib

from shared.python.paths import repository_root

ROOT = repository_root()
RUNNER = ROOT / ".agents/skills/rxp-sql/scripts/run_snowflake_query.py"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

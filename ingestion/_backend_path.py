"""Make backend/app importable from the ingestion package.

Ingestion has no database code of its own by design — it writes into the
schema backend/app/models owns, so it depends on backend rather than the
other way round. Rather than adding packaging (setup.py/poetry workspace)
for a hackathon-scale monorepo, this just adds backend/ to sys.path.

Run ingestion using backend's virtualenv (backend/.venv), which already
has SQLAlchemy/GeoAlchemy2/psycopg2 installed — ingestion adds no new
Python dependencies of its own.
"""

import sys
from pathlib import Path

_BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

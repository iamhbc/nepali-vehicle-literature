#!/usr/bin/env python3
"""Create tables, seed reference data and (re)import the processed corpus.

    backend/.venv/bin/python scripts/seed_db.py [--force]

--force also overwrites entries a researcher has edited (normally skipped).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.db import SessionLocal, init_db  # noqa: E402
from app.services.corpus import import_corpus, seed_reference_data  # noqa: E402

init_db()
with SessionLocal() as db:
    seed_reference_data(db)
    print(import_corpus(db, force="--force" in sys.argv))

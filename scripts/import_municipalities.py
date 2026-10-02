#!/usr/bin/env python3
"""Import Nepal's local levels (municipalities / rural municipalities) from an authoritative CSV.

CSV columns: district, name_en, name_ne (optional), kind (optional:
metropolitan city | sub-metropolitan city | municipality | rural municipality).

    backend/.venv/bin/python scripts/import_municipalities.py local_levels.csv --source "MoFAGA 2024"
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.db import SessionLocal, init_db  # noqa: E402
from app.services.corpus import seed_reference_data  # noqa: E402
from app.services.geo import import_municipalities  # noqa: E402

parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
parser.add_argument("csv", type=Path)
parser.add_argument("--source", required=True, help="Where the file came from (kept on every record)")
args = parser.parse_args()

init_db()
with SessionLocal() as db:
    seed_reference_data(db)
    print(import_municipalities(db, args.csv.read_text(encoding="utf-8-sig"), args.source))

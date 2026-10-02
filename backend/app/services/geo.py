"""Import of the municipal / rural-municipal directory from an authoritative CSV."""

from __future__ import annotations

import csv
import io

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import District, Municipality

KINDS = {"metropolitan city", "sub-metropolitan city", "municipality", "rural municipality"}


def import_municipalities(db: Session, csv_text: str, source: str) -> dict:
    """CSV columns: district (English name or alias), name_en, name_ne (optional), kind (optional)."""
    districts = db.scalars(select(District)).all()
    lookup: dict[str, District] = {}
    for d in districts:
        for name in [d.name_en, d.name_ne, *(d.aliases or [])]:
            lookup[name.strip().lower()] = d
    created, skipped, unknown = 0, 0, []
    existing = {(m.district_id, m.name_en.lower()) for m in db.scalars(select(Municipality))}
    for row in csv.DictReader(io.StringIO(csv_text)):
        dname = (row.get("district") or "").strip()
        d = lookup.get(dname.lower())
        name = (row.get("name_en") or "").strip()
        if not d:
            unknown.append(dname)
            continue
        if not name or (d.id, name.lower()) in existing:
            skipped += 1
            continue
        kind = (row.get("kind") or "").strip().lower() or None
        db.add(Municipality(district_id=d.id, name_en=name, name_ne=(row.get("name_ne") or "").strip() or None,
                            kind=kind if kind in KINDS else kind, source=source))
        existing.add((d.id, name.lower()))
        created += 1
    db.commit()
    return {"created": created, "skipped": skipped, "unknown_districts": sorted(set(unknown))}

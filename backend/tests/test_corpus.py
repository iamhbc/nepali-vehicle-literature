import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_original_workbook_is_preserved_and_matches_manifest():
    manifest = json.loads((ROOT / "data/processed/manifest.json").read_text())
    raw = (ROOT / manifest["source_file"]).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == manifest["source_sha256"]


def test_processed_corpus_shape():
    records = json.loads((ROOT / "data/processed/corpus.json").read_text())
    assert len(records) == 61
    by_id = {r["id"]: r for r in records}
    # Known QC issues are carried, not silently fixed.
    assert by_id[52]["status"] == "text_missing"
    assert by_id[52]["text"]["nepali"] == "gem"
    assert by_id[52]["text"]["nepali_candidate"]
    assert by_id[9]["variant"]["group"] == by_id[47]["variant"]["group"]
    assert by_id[1]["review"]["priority"].startswith("High")
    # Original translation is never overwritten.
    assert by_id[1]["text"]["translation_original"] != by_id[1]["text"]["translation_normalized"]
    assert "Critique" in by_id[2]["coding"]["power_hierarchy"]["stances"]


def test_geo_directory_has_7_provinces_and_77_districts():
    geo = json.loads((ROOT / "data/geo/nepal_admin.json").read_text())
    assert len(geo["provinces"]) == 7
    assert sum(len(p["districts"]) for p in geo["provinces"]) == 77

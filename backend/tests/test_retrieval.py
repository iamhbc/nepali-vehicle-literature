from app.retrieval.search import get_corpus_index


def test_semantic_search_finds_migration_entries(client):
    hits = get_corpus_index().search("phrases about migration and homesickness", k=5)
    assert hits and all("MIGRATION" in h.meta.codes for h in hits[:3])
    assert any("Migration" in r for r in hits[0].reasons)


def test_nepali_query_matches_inflected_forms(client):
    hits = get_corpus_index().search("आमा", k=5)
    assert any(h.meta.corpus_id in ("NVL-029", "NVL-058", "NVL-042") for h in hits)


def test_find_match_tolerates_spelling_variants(client):
    meta, score = get_corpus_index().find_match("ढिला हुन्छ तर सबै राम्रो हुन्छ समय खराब हो जिन्दगी हैन साथी")
    assert meta.corpus_id == "NVL-047" and score == 1.0


def test_related_prefers_shared_themes(client):
    idx = get_corpus_index()
    hits = idx.related(idx.meta[11].text, k=3, codes=idx.meta[11].codes, exclude={11})
    assert hits[0].meta.corpus_id == "NVL-012"

# API

Interactive OpenAPI docs: `GET /api/docs` (schema at `/api/openapi.json`).

## Public (no authentication)

| Method & path | Purpose |
|---|---|
| `GET /api/health` | Status, active engine, OCR provider, corpus size, embedding model, taxonomy version |
| `GET /api/meta` | Capabilities and taxonomy for the UI |
| `POST /api/analyze` | Analyse a phrase. Body: `{text, context?: {vehicle_type, province_id, district_id, municipality_id, locality}, contribute?, ocr_text?, ocr_provider?}` → `AnalysisResult` |
| `POST /api/analyze/stream` | Same, as server-sent events: `stage`*, `preliminary` (AI mode), `result` or `error` |
| `GET /api/analyses/{id}` | A saved analysis (shareable link) |
| `POST /api/ocr` | Multipart `file`. Returns `{text, lines[], legibility, uncertain_segments[], other_text[], suggestions[], image: {stored: false}}`. The image is never stored. |
| `POST /api/analyze-image` | OCR, plus analysis when `auto_analyze=true` (the UI always corrects OCR first) |
| `GET /api/phrases` | Corpus list. Filters: `theme`, `cluster`, `valence`, `needs_review`, `limit`, `offset` |
| `GET /api/phrases/{id}` | Full record: coding, themes with status, labels, QC flags, variants, related entries, cultural map |
| `GET /api/related/{id}` | Related corpus entries with scores and reasons |
| `GET /api/search?q=` | Semantic search (English or Nepali), with interpreted themes and per-result reasons |
| `GET /api/themes`, `GET /api/themes/{code}` | Codebook themes with counts / a theme's entries and references |
| `GET /api/clusters`, `GET /api/stats` | Emergent clusters / distributions, co-occurrence, geography, vehicles |
| `GET /api/locations` | Provinces → districts |
| `GET /api/locations/districts/{id}/municipalities` | Imported local levels |
| `GET /api/vehicles` | Vehicle types |
| `GET /api/taxonomy`, `/api/concepts`, `/api/references`, `/api/examples` | Knowledge layer |

AI analyses are rate-limited per client (`RATE_LIMIT_ANALYZE_PER_HOUR`); OCR has its own limit. Errors use `{"detail": "..."}` with plain-language messages.

### `AnalysisResult` (abridged)

```json
{
  "id": "…", "input_text": "…", "normalized_text": "…",
  "language": {"script": "devanagari", "language": "ne", "confidence": 1.0},
  "engine": {"mode": "llm|baseline", "model": "claude-opus-5-5", "taxonomy_version": "1.0.0", "cached": false},
  "payload": {
    "transliteration": "…", "literal_translation": "…", "contextual_translation": "…",
    "key_terms": [{"term": "इष्ट", "gloss": "…", "culturally_specific": true}],
    "emotion": {"valence": "mixed", "findings": [{"label": "Longing", "family": "longing",
                "evidence": ["सम्झना"], "confidence": "medium", "kind": "interpretation", "explanation": "…"}]},
    "love": {}, "relationships": {}, "social": {}, "economic": {}, "political": {},
    "gender_power": {"power_stance": "critique", "findings": []},
    "cultural": {}, "philosophical": {}, "rhetoric": {},
    "implied": {"literal": "…", "implied": "…", "cultural_reading": "…", "alternatives": [], "confidence": "low"},
    "themes": [{"code": "FARE_LIVELIHOOD", "confidence": "high", "rationale": "…"}],
    "ambiguity": {"is_ambiguous": false, "note": ""}, "overall_confidence": "medium"
  },
  "corpus_match": {"corpus_id": "NVL-001", "similarity": 1.0, "coding": {}, "needs_review": true},
  "related": [{"corpus_id": "NVL-021", "score": 0.38, "reasons": ["Shared theme: Fare & livelihood"]}],
  "concepts": [], "lexical_signals": [], "references": [{"id": "connell-messerschmidt-2005", "matched_topics": ["MASCULINITY"]}],
  "verification": {"quotes_checked": 12, "quotes_verified": 12, "issues": []},
  "graph": {"nodes": [], "edges": []},
  "warnings": []
}
```

## Researcher (Bearer JWT from `POST /api/admin/login`)

| Method & path | Purpose |
|---|---|
| `POST /api/admin/login` | `{username, password}` → `{token, expires_at}` (rate-limited) |
| `GET /api/admin/review-queue` | Entries needing review, meaning-changing first |
| `GET/POST /api/admin/phrases`, `GET/PUT/DELETE /api/admin/phrases/{id}` | Create, edit (audited), archive (soft delete; restore with `status: active`) |
| `PUT /api/admin/phrases/{id}/themes` | Approve / reject / add a theme for a given source |
| `POST /api/admin/phrases/{id}/approve` | Approve all proposed labels; clear the review flag |
| `POST /api/admin/phrases/{id}/reanalyze` | Run the engine; attach its themes as `ai` / `proposed` |
| `GET /api/admin/submissions`, `POST …/{id}/accept`, `POST …/{id}/reject` | Public contributions, with OCR correction on accept |
| `POST /api/admin/themes`, `POST /api/admin/references` | Add categories and references |
| `GET/POST /api/admin/taxonomy/versions` | List versions / store a proposed version |
| `POST /api/admin/municipalities/import?source=` | CSV import of local levels |
| `POST /api/admin/import-corpus?force=` | Re-import `data/processed/corpus.json` |
| `GET /api/admin/export?format=json|csv` | Dataset export with decisions and provenance |
| `GET /api/admin/analytics`, `GET /api/admin/audit` | Usage and the audit log |

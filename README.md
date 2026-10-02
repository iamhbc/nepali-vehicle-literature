# Nepali Vehicle Literature · सवारी साहित्य

**A digital cultural microscope for the words painted on Nepal's buses, trucks, jeeps and tempos.**

Type a Nepali phrase, or photograph a vehicle, and the platform returns a multidimensional reading of it:

- what it says
- what it feels and implies
- the relationships and power it represents
- its social, economic, political, cultural and gender dimensions
- related inscriptions from a research corpus

Every claim carries its evidence, a confidence level, and an epistemic label: *evidence*, *interpretation* or *hypothesis*.

> सडकमा लेखिएका शब्दहरू समाजको ऐना पनि हुन सक्छन्।
> Words painted on the road can also be a mirror of society.

## What's here

| | |
|---|---|
| **Public app** (no login) | Phrase analysis with live progress, an interactive cultural map, photo → OCR → *correct* → analyse, corpus search and browsing, data exploration, method & privacy pages. |
| **Analysis engine** | Normalization → corpus retrieval → lexical & cultural cues → Claude structured analysis (or the corpus-grounded baseline) → evidence verification → cultural graph. |
| **Research corpus** | The original workbook, preserved byte-for-byte, plus a normalized version that carries every QC flag, review note, variant group and cluster. |
| **Researcher area** | Review queue, editing with an audit trail, per-theme approve/reject, re-analysis, submissions inbox, exports, analytics, categories, references, municipality import. |

## Quick start (local)

Requirements: Python 3.11+, Node 20+.

```bash
python3 -m venv backend/.venv && backend/.venv/bin/pip install -r backend/requirements.txt pytest httpx
```

```bash
cd frontend && npm install
```

Optional: `cp .env.example .env` and set `ANTHROPIC_API_KEY` to enable AI interpretation and photo reading. Without it the app runs on the **baseline engine**, and the UI says so.

Run the API (port 8000; on first start it creates `backend/nvl.db` and imports the corpus):

```bash
backend/.venv/bin/uvicorn app.main:app --app-dir backend --reload --port 8000
```

Run the web app at http://localhost:5173. It proxies `/api` to port 8000:

```bash
npm --prefix frontend run dev
```

API docs are at http://localhost:8000/api/docs.

### Researcher login

```bash
backend/.venv/bin/python scripts/hash_password.py --random
```

Put the printed hash in `ADMIN_PASSWORD_HASH`, set a long random `JWT_SECRET`, and restart the API. Then open `/admin`.

### Tests

```bash
cd backend && .venv/bin/python -m pytest
```

```bash
npm --prefix frontend test
```

## Repository layout

```
backend/            FastAPI app (analysis engine, retrieval, OCR, admin API) + tests
frontend/           React + TypeScript + Vite app (design system, pages, cultural map)
data/raw/           Original research workbook — never modified
data/processed/     Normalized corpus, codebook, clusters, manifest (with source checksum)
data/geo/           Provinces & districts of Nepal
data/reference/     Vehicle types
knowledge-base/     Cultural-concept glossary, lexicon, curated references
taxonomy/           Versioned multi-label taxonomy (the single source of truth)
scripts/            Corpus processing, seeding, password hashing, municipality import
docs/               Architecture, data audit, design system, API, deployment
```

## Documentation

- [Architecture](docs/ARCHITECTURE.md): information architecture, pipeline, data model, reliability, privacy, scaling
- [Data & taxonomy](docs/DATA.md): dataset audit, normalization, taxonomy schema
- [Design system](docs/DESIGN.md): visual research, tokens, ornaments, accessibility
- [API](docs/API.md): public and researcher endpoints
- [Deployment](docs/DEPLOYMENT.md): Netlify frontend, Docker/Render API, PostgreSQL + pgvector

## Honest status

- The AI path (Claude structured analysis and vision OCR) is implemented and unit-tested against a stubbed client. Run a live check with your own API key before relying on it.
- The corpus coding is a **first pass** (61 entries, 27 flagged for native-speaker review). The platform shows that status everywhere it matters.
- Municipality records are not bundled. Import them from an authoritative source (`scripts/import_municipalities.py`).
- The pgvector backend is implemented but was not exercised in this environment. The default in-memory index is fine up to roughly 100k entries.

## Licence

GPL-3.0 (see `LICENSE`). The research corpus remains the property of its collectors; check with them before reusing it.

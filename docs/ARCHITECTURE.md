# Architecture

## Guiding decision

The LLM is not the brain. The research corpus is:

```
collected corpus → taxonomy → structured database → retrieval → LLM reasoning
                → evidence verification → confidence → cultural graph
```

The model reads every new phrase *alongside comparable, researcher-coded inscriptions*. Its output must fit a fixed JSON schema, and a deterministic verifier checks every quoted word against the phrase before anything reaches the user. As the corpus grows, the readings grow more grounded in actual Nepali usage.

## Information architecture

```
/                     Landing: hero, live truck with corpus phrases, phrase input, examples, categories
/analyze              Phrase input → streaming analysis
/analysis/:id         Shareable result page
/scan                 Photograph → OCR → correct → optional context & contribution → analyse
/corpus               Semantic search + filters (theme, valence, review status)
/corpus/:id           Researcher-coded record, cultural map, variants, QC notes, related entries
/explore              Theme map, emotion distribution, valence, co-occurrence network, clusters, geography, vehicles
/method               How analysis works, labels, privacy, limitations, references
/admin/*              Researcher area (protected)
```

Result page order: phrase → cultural map → emotional, gender & power, love, relationship, social, economic, political, cultural, philosophical and linguistic readings → implied meaning → themes → related expressions → references → "How this reading was made".

## System overview

```
┌──────────────── Netlify ────────────────┐      ┌──────────── Python API (Docker) ─────────────┐
│ React + TS (Vite)                       │ HTTPS│ FastAPI                                       │
│ • code-split routes                     │─────▶│ • public router   (no auth, rate-limited)     │
│ • SSE reader for streaming analysis     │      │ • admin router    (JWT, audit log)            │
│ • client-side image compression         │      │ • AnalysisEngine  • CorpusIndex  • OCR        │
└─────────────────────────────────────────┘      └───────────────┬───────────────────────────────┘
                                                                 │ SQLAlchemy
                                                 ┌───────────────▼───────────────┐   ┌────────────┐
                                                 │ PostgreSQL (+ pgvector)        │   │ Anthropic  │
                                                 │ SQLite in development          │   │ Claude API │
                                                 └────────────────────────────────┘   └────────────┘
```

The frontend and API deploy independently. API keys live only on the server.

## Analysis pipeline (`backend/app/analysis/engine.py`)

| Stage | Component | Notes |
|---|---|---|
| Normalize | `nlp/normalize.py` | NFC, quotes, danda, markdown escapes. A separate lossy **match key** folds ि/ी, ु/ू, ँ/ं, ब/व, श/ष/स for spelling-tolerant matching. |
| Detect language | `nlp/language.py` | Devanagari / romanized Nepali / English / mixed. |
| Transliterate | `nlp/transliterate.py` | Rule-based IAST with Nepali schwa deletion (final, medial, conjunct, छ-endings, negatives). |
| Retrieve | `retrieval/search.py` | Exact or near-duplicate corpus match, plus nearest neighbours as exemplars. |
| Cues | `knowledge.py` | Lexicon signals (with case-suffix-aware matching) and cultural-concept glossary hits. |
| Interpret | `analysis/llm.py`, `prompts.py` | Claude `claude-opus-5-5`, adaptive thinking, JSON-schema output, cached system prompt, server-side refusal fallback. |
| Baseline | `analysis/baseline.py`, `rhetoric.py` | Without an LLM: corpus coding if matched, otherwise lexicon cues, neighbour themes (as hypotheses), and deterministic rhetoric detection (rhyme incl. रदिफ–काफिया, antithesis by negation, anaphora, parallelism, rhetorical questions, code-mixing, reported speech). |
| Verify | `analysis/verify.py` | Removes quotes not found in the phrase and lowers confidence. Sensitive labels without verified evidence become low-confidence hypotheses. Unknown theme codes are dropped. |
| Graph | `analysis/graph.py` | phrase → dimensions → findings, plus themes, concepts and related entries. |
| Persist | `models.Analysis` | Cached by content, model, effort, taxonomy, prompt version **and corpus revision**, so corpus edits invalidate stale readings. |

`POST /api/analyze/stream` emits `stage` events, then in AI mode an instant **preliminary** baseline reading, then the final `result`. If the LLM fails, refuses, or truncates, the engine falls back to the baseline and says so in `warnings`.

### Why one structured call rather than one call per dimension
A single schema-constrained call lets the model weigh dimensions against each other (e.g. humour that softens a gender stereotype). It also costs one round-trip and caches one system prompt. The per-dimension classes from the brief (EmotionAnalyzer, GenderAnalyzer…) exist as **schema sections plus verifier rules** rather than separate model calls; the deterministic analyzers (lexicon, rhetoric, concepts) cross-check the model's output.

## Data model (`backend/app/models.py`)

```
Province 1─* District 1─* Municipality          VehicleType
Theme (codebook)         TaxonomyVersion          Reference
Phrase ─* PhraseTheme   (source: corpus|ai|researcher, status: proposed|approved|rejected)
       ─* PhraseLabel   (dimension, label, evidence, confidence, source, status)
       ─* PhraseEmbedding (model, vector, content_hash)
       ─ vehicle_type, province, district, municipality   ← where it was SEEN
       ─ places_mentioned (JSON)                          ← places the TEXT names
Analysis (cache_key, result JSON, engine, model, taxonomy_version, phrase_id?)
Submission (text only; optional context; status pending|accepted|rejected)
ReviewEvent (append-only audit: before/after, reviewer, note)
```

A phrase's full researcher coding is stored intact in `Phrase.coding` (JSON), so no field from the workbook is lost. The queryable parts (themes, labels) are normalized and carry human-in-the-loop status.

## Human-in-the-loop

```
AI / corpus classification → confidence → evidence → researcher review → approved classification
```

- Corpus codes import as `proposed` (the codebook says they're an unvalidated first pass).
- Researchers approve or reject each theme per source; re-analysis adds AI codes as `proposed`.
- Original translations are never overwritten; corrections go to `translation_normalized`.
- Re-importing the corpus skips researcher-edited entries unless forced.
- Archiving replaces deletion; every action is logged in `ReviewEvent`.

## Retrieval

The embedder and vector index are both replaceable (`retrieval/embeddings.py`, `retrieval/index.py`).

- **HashingEmbedder** (default): Devanagari char n-grams over the match key, plus English terms from translations and researcher interpretations. Deterministic, no download, handles inflection and spelling variation. It is not a paraphrase model.
- **SentenceTransformerEmbedder**: multilingual-e5 for cross-lingual semantics (`EMBEDDING_PROVIDER=sentence-transformers`).
- **MemoryVectorIndex** (default) or **PgVectorIndex** (`VECTOR_BACKEND=pgvector`, HNSW cosine).
- Search blends vector similarity with codebook theme overlap. English or Nepali queries are mapped to theme codes ("homesickness" → MIGRATION), and every result states *why* it matched.

## Reliability & safety

- Structured output only. Free-form model text never drives application logic.
- Evidence verification, plus sensitive-label demotion (misogyny, patriarchy, caste, ethnicity, party, religious identity).
- Hedged language is required by the prompt ("may suggest", "a possible reading").
- "Implied / secondary meaning" replaces "hidden meaning": literal, implied, cultural reading, alternatives, confidence.
- Refusal, truncation, auth, rate-limit and network errors are typed; each falls back to the baseline engine.

## Privacy

- No accounts for the public. No personal data requested.
- Photos are compressed on the device (EXIF/GPS dropped), then re-encoded in server memory, read once, and never written to disk or the database.
- Analyses store only text and are not linked to a person. Contributions store text plus the optional vehicle and place the user chose.
- Admin tokens live in `sessionStorage` and expire.

## Performance

- Baseline analysis runs in ~10 ms. LLM analysis streams progress and shows a preliminary reading immediately.
- Content-addressed result cache; prompt caching on the stable system prompt.
- Embeddings are cached per content hash in the DB (matters for transformer models).
- Frontend: route-level code splitting, ~94 KB gzipped core, on-device image compression, a truck animation that pauses offscreen and under reduced-motion.

## Scaling notes

- The rate limiter and in-memory index are per process. For several API instances, move rate limiting to Redis and use `VECTOR_BACKEND=pgvector`.
- Tables are created with `create_all`. Adopt Alembic before the first schema change in production.
- OCR and LLM calls are async. For heavy batch re-analysis, use the Message Batches API from a worker.

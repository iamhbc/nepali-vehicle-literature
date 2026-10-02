# Research data & taxonomy

## The source dataset

`data/raw/Vehicle_Inscriptions_Master_Dataset.xlsx` is the original workbook. It is copied into the repository byte-for-byte; its SHA-256 is recorded in `data/processed/manifest.json`, and a test checks that the file still matches. **Never edit it.** Correct data through the researcher area or the processor.

### Structure found

| Sheet | Contents |
|---|---|
| `Master_Dataset` | 61 inscriptions × 34 fields: original Nepali, transliteration, original & normalized translation, text type, domains, emotion (+intensity, target), relationship, love type, cultural concepts, economic/political/religious/gender/identity themes, power hierarchy, aspiration, agency, humour, rhetorical devices, valence, temporal orientation, deeper meaning, evidence, confidence, alternative interpretation, review flag & reason, theme codes |
| `Codebook` | 23 theme codes (15 deductive, 8 emergent) with definitions, plus coding rules |
| `Clusters` | 14 emergent clusters with member ids |
| `Human_Review` | 27 entries needing review, with priority (6 *High — meaning changes*) |
| `QC_Log` | Data-quality findings |
| `Code_Matrix`, `Frequencies`, `Co_occurrence`, `Dashboard*` | Formula-driven views (recomputed by the platform, not imported) |

### Quality findings (carried onto every affected record)

- **#52 text missing**: the Nepali cell reads "gem". The transliteration survives, so a reconstructed candidate is stored *separately* (`nepali_candidate`) and flagged for verification against the photo.
- **Duplicates / variants**: #9 and #47 are near-duplicates (होइन/हैन); #20 and #23 share the fare-and-love template; #14 and #54 share the कतार/हतार rhyme formula. Each pair is recorded as a `variant_group`.
- **Mistranslations** (meaning-changing): #1, #5, #10, #11, #15, #55. Originals are kept; corrections live in `translation_normalized`.
- **Contaminated field**: #13's translation has an unrelated English line appended.
- **Transliteration errors**: "-pardcha" for पर्छ (#2, #17, #35, #45, #48) is corrected in `transliteration` with a note, and the original is kept in `transliteration_original`. An automatic transliteration is generated for every entry.
- **Probable transcription errors**: #43 (भोलि → बोली?), #49 (पठाएको → पटाएको?).
- **No observation context**: no row has a vehicle type, location, date or photo reference, so the platform keeps *places mentioned in the text* (e.g. मुगाली → Mugu, चौरजहारी → Rukum West) separate from *where the inscription was seen*.
- **Mixed separators**: the theme column mixes commas and semicolons; multi-label fields use `|`.
- **Time-sensitive claim**: #55's coding attributes "चुपचाप घण्टी छाप" to a 2026 campaign slogan. It is preserved as coded; verify before publication.

## Processing

```bash
backend/.venv/bin/python scripts/process_corpus.py
```

The script opens the workbook read-only and writes `data/processed/{corpus,codebook,clusters,manifest}.json`. Per record it:

- splits multi-label fields
- maps "Not evident" / "N/A" / "—" to empty (this means *no textual basis*, not a negative finding)
- parses power-hierarchy stances in the coder's order
- splits evidence quotes
- attaches review priority, QC flags, clusters, variant group and provenance (sheet, row, checksum)

Then load it into the database. The API also does this automatically on first start:

```bash
backend/.venv/bin/python scripts/seed_db.py
```

## Taxonomy (`taxonomy/taxonomy.v1.json`)

A versioned, multi-label scheme. It is the single source of truth for the LLM prompt, the baseline engine, the graph and the UI.

| Section | Purpose |
|---|---|
| `dimensions` | Emotion, Love, Relationship, Social, Economic, Political, Gender & Power, Cultural, Philosophical, Rhetoric & Humour (EN + NE labels) |
| `themes` | The 23 codebook codes, each with a group (dimension), EN/NE labels, definition, origin, and EN/NE keywords used for query expansion |
| `emotion_families` | 12 families that group the coders' free-text emotions (e.g. *longing*: Longing, Melancholy, Wounded love…) |
| `love_types` | माया, विरह, eros, ludus, storge, वात्सल्य, philia, agape, भक्ति, unrequited, conditional (Greek terms are a lens, not a claim) |
| `power_stances` | reproduction / reflection / critique / resistance / ambiguous |
| `dimension_vocabularies` | Preferred labels per dimension (from the project brief) |
| `sensitive_labels` | Labels that need verified evidence or are demoted to hypotheses |
| `confidence_levels`, `epistemic_kinds` | Definitions shown to users |

Researchers can add theme categories at runtime (stored in the DB and merged at startup). Propose new versions with `POST /api/admin/taxonomy/versions`, and deploy them by committing a new file.

## Knowledge base (`knowledge-base/`)

- `cultural_concepts.json`: working glosses for माया, प्रेम, स्नेह, करुणा, भक्ति, धर्म, कर्म, भाग्य, इज्जत, मान, लाज, दुःख, सुख, विरह, याद, इष्ट, माइती, औकात, परदेश, खाडी, जलन, घमण्ड, कठैबरा, आशीर्वाद. Each says why the term resists one-to-one translation.
- `lexicon.json`: surface cues for the baseline engine. A match is evidence that a word is present, never proof of a reading. Ambiguous words (हार = necklace/defeat, मान = respect/accept) are marked weak.
- `references.json`: level-2 curated sources. Only real, published works are listed (Turner 1931; Ahearn 2001; Liechty 2003; Seddon, Adhikari & Gurung 2002; Bista 1991; Kandiyoti 1988; Connell & Messerschmidt 2005; Scott 1990; Lee 1973; Lewis 1960; Plutchik 1980; Lakoff & Johnson 1980; Myers-Scotton 1993; Braun & Clarke 2006; Elias 2011). URLs are given only where stable (DOI / DSAL). **Verify details before citing.** A reference is shown only when one of its topics appears in a reading, and the UI says which topic triggered it.

## Geography (`data/geo/nepal_admin.json`)

7 provinces and 77 districts (2015 constitution) with Nepali names and aliases (e.g. Nawalpur = Nawalparasi (Bardaghat Susta East)). The 753 local levels are intentionally **not** typed by hand. Import them from MoFAGA or the OCHA/HDX administrative dataset:

```bash
backend/.venv/bin/python scripts/import_municipalities.py local_levels.csv --source "MoFAGA <year>"
```

The CSV columns are `district, name_en, name_ne, kind`; districts match on English name, Nepali name or alias.

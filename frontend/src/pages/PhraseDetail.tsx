import { Link, useNavigate, useParams } from "react-router-dom";
import { api } from "../api/client";
import { NepaliPhrase, RelatedList, ThemeBadge } from "../components/analysis-ui";
import { useMeta } from "../components/Layout";
import { MindMap } from "../components/MindMap";
import { NumberPlate, PaintedFrame } from "../components/ornaments";
import { useAsync } from "../lib/useAsync";

const FIELDS: [string, string][] = [
  ["text_types", "Form"],
  ["primary_domain", "Primary domain"],
  ["secondary_domains", "Secondary domains"],
  ["emotions", "Emotions"],
  ["emotion_intensity", "Intensity"],
  ["emotional_targets", "Emotional target"],
  ["relationship_types", "Relationship"],
  ["love_types", "Love type"],
  ["cultural_concepts", "Cultural concepts"],
  ["economic_theme", "Economic"],
  ["political_theme", "Political"],
  ["religious_theme", "Religious"],
  ["gender_theme", "Gender"],
  ["identity_theme", "Identity"],
  ["aspiration", "Aspiration"],
  ["agency", "Agency"],
  ["humor_irony", "Humour / irony"],
  ["rhetorical_devices", "Rhetorical devices"],
  ["valence", "Valence"],
  ["temporal_orientation", "Time orientation"],
  ["deeper_meaning", "Deeper meaning"],
  ["evidence", "Evidence"],
  ["confidence", "Confidence"],
  ["alternative_interpretation", "Alternative reading"],
];

function show(v: unknown): string | null {
  if (v === null || v === undefined || v === "") return null;
  if (Array.isArray(v)) return v.length ? v.join(" · ") : null;
  if (typeof v === "object") return (v as { raw?: string }).raw ?? null;
  return String(v);
}

export default function PhraseDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { themes } = useMeta();
  const { data: p, error, loading } = useAsync(() => api.phrase(id!), [id]);

  if (loading && !p) return <div className="container page"><div className="skeleton" style={{ height: 300 }} /></div>;
  if (error || !p)
    return (
      <div className="container page">
        <p className="notice notice-error">{error ?? "Not found."}</p>
        <Link to="/corpus">← Back to the corpus</Link>
      </div>
    );

  const coding = p.coding ?? {};
  const power = show(coding.power_hierarchy);
  return (
    <div className="container page">
      <p>
        <Link to="/corpus">← Corpus</Link>
      </p>
      <PaintedFrame tone="indigo" className="phrase-hero" as="section" aria-label="Inscription">
        <div className="row phrase-hero-meta">
          <NumberPlate corpusId={p.corpus_id} />
          {p.needs_review && <span className="tag tag-review">Coding needs review{p.review_priority ? ` · ${p.review_priority}` : ""}</span>}
          {p.variant_group && <span className="tag">Variant group</span>}
        </div>
        {p.text_is_candidate && (
          <p className="notice notice-warn">
            The original Nepali cell is unusable (“{p.text_original}”). The text below is reconstructed from the transliteration and must be verified
            against the source photograph.
          </p>
        )}
        <NepaliPhrase text={p.text} />
        {p.transliteration && <p className="translit phrase-translit">{p.transliteration}</p>}
        <dl className="translations">
          {p.translation_normalized && (
            <>
              <dt>Corrected translation</dt>
              <dd className="translation-main">{p.translation_normalized}</dd>
            </>
          )}
          <dt>{p.translation_normalized ? "Original translation (kept for the record)" : "Translation"}</dt>
          <dd className={p.translation_normalized ? "muted" : "translation-main"}>{p.translation_original}</dd>
        </dl>
        <div className="row">
          <button className="btn btn-primary btn-sm" onClick={() => navigate("/analyze", { state: { text: p.text } })}>
            Run a fresh analysis
          </button>
        </div>
      </PaintedFrame>

      {p.review_reason && (
        <p className="notice notice-warn">
          <strong>Reviewer note:</strong> {p.review_reason}
        </p>
      )}

      {p.graph && (
        <section className="map-section" aria-labelledby="map-h">
          <h2 id="map-h">Cultural map from the researcher coding</h2>
          <MindMap graph={p.graph} />
        </section>
      )}

      <div className="grid-2">
        <section aria-labelledby="coding-h">
          <h2 id="coding-h">Researcher coding</h2>
          <dl className="coding-table">
            {FIELDS.map(([key, label]) => {
              const v = show(coding[key]);
              return v ? (
                <div key={key}>
                  <dt>{label}</dt>
                  <dd lang={/[ऀ-ॿ]/.test(v) ? "ne" : undefined}>{v}</dd>
                </div>
              ) : null;
            })}
            {power && (
              <div>
                <dt>Power stance</dt>
                <dd>{power}</dd>
              </div>
            )}
          </dl>
          <p className="subtle">Fields left out were coded “not evident”: no textual basis, which is not a negative finding.</p>
        </section>
        <section aria-labelledby="themes-h" className="stack">
          <h2 id="themes-h">Themes</h2>
          <ul className="theme-list">
            {p.themes.map((t) => (
              <li key={`${t.code}-${t.source}`}>
                <ThemeBadge code={t.code} themes={themes} to={`/corpus?theme=${t.code}`} />
                <span className={`tag status-${t.status}`}>{t.status}</span>
                <span className="subtle">source: {t.source}</span>
              </li>
            ))}
          </ul>
          {p.original_theme.length > 0 && <p className="subtle">Collector's original theme note: {p.original_theme.join(", ")}</p>}
          {p.clusters.length > 0 && <p className="subtle">Clusters: {p.clusters.join(" · ")}</p>}
          {p.places_mentioned.length > 0 && (
            <p className="subtle">Places mentioned in the text: {p.places_mentioned.map((m) => `${m.district} (${m.surface})`).join(", ")}</p>
          )}
          <p className="subtle">
            Where it was seen: {[p.vehicle_type, p.district].filter(Boolean).join(", ") || "not recorded"}
          </p>
          {p.qc_flags.length > 0 && (
            <details>
              <summary>Data-quality notes ({p.qc_flags.length})</summary>
              <ul>
                {p.qc_flags.map((f, i) => (
                  <li key={i}>
                    <strong>{f.check}:</strong> {f.finding}
                  </li>
                ))}
              </ul>
            </details>
          )}
          {p.variants.length > 0 && (
            <div>
              <h3>Variants</h3>
              <ul>
                {p.variants.map((v) => (
                  <li key={v.id}>
                    <Link to={`/corpus/${v.id}`}>{v.corpus_id}</Link> <span lang="ne">{v.text}</span> <span className="subtle">({v.relation})</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </section>
      </div>

      {p.concepts.length > 0 && (
        <section aria-labelledby="concepts-h">
          <h2 id="concepts-h">Cultural concepts</h2>
          <ul className="concepts">
            {p.concepts.map((c) => (
              <li key={c.slug} className="concept">
                <span className="concept-term" lang="ne">
                  {c.term}
                </span>{" "}
                <span className="translit">{c.translit}</span>
                <p>
                  <strong>{c.gloss}.</strong> {c.explanation}
                </p>
              </li>
            ))}
          </ul>
        </section>
      )}

      <section aria-labelledby="related-h">
        <h2 id="related-h">Related expressions</h2>
        <RelatedList items={p.related} themes={themes} />
      </section>

      <details className="transparency">
        <summary>Provenance</summary>
        <pre className="provenance">{JSON.stringify(p.provenance, null, 2)}</pre>
      </details>
    </div>
  );
}

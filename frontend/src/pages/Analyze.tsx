import { useEffect, useRef, useState, type ReactNode } from "react";
import { Link, useLocation, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { ApiError, analyzeStream, api, type AnalyzeInput } from "../api/client";
import type { AnalysisResult, DimensionReading, Finding, GraphNode, StageEvent } from "../api/types";
import { ConfidenceIndicator, FindingItem, NepaliPhrase, ReferenceCard, RelatedList, ThemeBadge } from "../components/analysis-ui";
import { AnalysisProgress, PhraseInput } from "../components/inputs";
import { useMeta } from "../components/Layout";
import { MindMap } from "../components/MindMap";
import { NumberPlate, PaintedFrame, RoadDivider } from "../components/ornaments";
import { DIMENSION_LABELS, dimColor } from "../lib/format";

type NavState = { text?: string; input?: AnalyzeInput; result?: AnalysisResult } | null;

function Section({ id, dim, title, ne, children, summary }: { id: string; dim: string; title: string; ne: string; children?: ReactNode; summary?: string }) {
  return (
    <section className="reading" id={id} aria-labelledby={`${id}-h`} style={{ ["--dim" as string]: dimColor(dim) }}>
      <h2 id={`${id}-h`} className="reading-title">
        <span>{title}</span>
        <span lang="ne" className="reading-ne">
          {ne}
        </span>
      </h2>
      {summary && <p className="reading-summary">{summary}</p>}
      {children}
    </section>
  );
}

function Findings({ findings, dim, onFocus }: { findings: Finding[]; dim: string; onFocus: (q: string[]) => void }) {
  if (!findings.length) return null;
  return (
    <ul className="findings">
      {findings.map((f, i) => (
        <FindingItem key={i} finding={f} dimension={dim} onFocus={onFocus} />
      ))}
    </ul>
  );
}

const READINGS: { key: keyof AnalysisResult["payload"]; dim: string; title: string }[] = [
  { key: "love", dim: "love", title: "Love reading" },
  { key: "relationships", dim: "relationship", title: "Relationship reading" },
  { key: "social", dim: "social", title: "Social reading" },
  { key: "economic", dim: "economic", title: "Economic reading" },
  { key: "political", dim: "political", title: "Political reading" },
  { key: "cultural", dim: "cultural", title: "Cultural reading" },
  { key: "philosophical", dim: "philosophical", title: "Philosophical reading" },
];

export function AnalysisView({ result, preliminary = false }: { result: AnalysisResult; preliminary?: boolean }) {
  const { themes } = useMeta();
  const p = result.payload;
  const [focus, setFocus] = useState<string[]>([]);
  const onNode = (n: GraphNode | null) => setFocus(n && Array.isArray(n.detail.evidence) ? (n.detail.evidence as string[]) : []);
  const notEvident = READINGS.filter((r) => !(p[r.key] as DimensionReading).findings.length).map((r) => DIMENSION_LABELS[r.dim].en);
  if (!p.gender_power.findings.length) notEvident.push("Gender & Power");
  const translation = p.contextual_translation || p.literal_translation;
  const unreflected = result.lexical_signals.filter((s) => !s.reflected_in_reading);

  return (
    <div className={`analysis ${preliminary ? "is-preliminary" : ""}`}>
      <PaintedFrame tone="vermilion" className="phrase-hero" as="section" aria-label="The phrase">
        <div className="row phrase-hero-meta">
          <span className={`engine-badge engine-${result.engine.mode}`}>
            {result.engine.mode === "llm" ? "AI-assisted reading" : "Baseline reading"}
          </span>
          {result.engine.cached && <span className="tag">Saved result</span>}
          <span className="subtle">Overall</span>
          <ConfidenceIndicator value={p.overall_confidence} />
        </div>
        <NepaliPhrase text={result.normalized_text} highlight={focus} />
        {p.transliteration && <p className="translit phrase-translit">{p.transliteration}</p>}
        {translation ? (
          <dl className="translations">
            {p.literal_translation && p.literal_translation !== p.contextual_translation && (
              <>
                <dt>Literal</dt>
                <dd>{p.literal_translation}</dd>
              </>
            )}
            <dt>{p.literal_translation && p.literal_translation !== p.contextual_translation ? "In context" : "Translation"}</dt>
            <dd className="translation-main">{translation}</dd>
          </dl>
        ) : (
          <p className="subtle">Translation needs the AI engine, which isn't available for this reading.</p>
        )}
        {result.corpus_match && (
          <div className="corpus-match">
            <NumberPlate corpusId={result.corpus_match.corpus_id} />
            <div>
              <strong>{result.corpus_match.exact ? "This inscription is in the research corpus." : "A near-identical inscription is in the research corpus."}</strong>{" "}
              <Link to={`/corpus/${result.corpus_match.id}`}>See the researcher-coded record →</Link>
              {result.corpus_match.needs_review && (
                <p className="subtle">Its coding is a first pass awaiting native-speaker review{result.corpus_match.review_reason ? `: ${result.corpus_match.review_reason}` : "."}</p>
              )}
            </div>
          </div>
        )}
      </PaintedFrame>

      {(result.warnings.length > 0 || p.ambiguity.is_ambiguous) && (
        <div className="stack notices">
          {p.ambiguity.is_ambiguous && p.ambiguity.note && (
            <p className="notice notice-warn">
              <strong>More than one plausible reading.</strong> {p.ambiguity.note}
            </p>
          )}
          {result.warnings.map((w, i) => (
            <p key={i} className="notice notice-warn">
              {w}
            </p>
          ))}
        </div>
      )}

      <section className="map-section" aria-labelledby="map-h">
        <h2 id="map-h">
          Cultural map <span lang="ne" className="h-ne">सांस्कृतिक नक्सा</span>
        </h2>
        <MindMap graph={result.graph} references={result.references} onSelect={onNode} />
      </section>

      <div className="readings">
        <Section id="emotion" dim="emotion" title="Emotional reading" ne="भावनात्मक पठन" summary={p.emotion.summary}>
          <div className="row reading-facts">
            <span className={`valence valence-${p.emotion.valence}`}>Valence: {p.emotion.valence}</span>
            <span className="tag">Intensity: {p.emotion.overall_intensity}</span>
            {p.emotion.direction && p.emotion.direction !== "not determined" && p.emotion.direction !== "not evident" && (
              <span className="tag">Direction: {p.emotion.direction}</span>
            )}
          </div>
          <Findings findings={p.emotion.findings} dim="emotion" onFocus={setFocus} />
        </Section>

        <Section id="gender" dim="gender_power" title="Gender & power" ne="लैङ्गिकता र शक्ति" summary={p.gender_power.summary}>
          {p.gender_power.power_stance !== "not_applicable" && (
            <p className="stance">
              <span className="tag tag-strong">Power stance: {p.gender_power.power_stance}</span> {p.gender_power.stance_explanation}
            </p>
          )}
          <Findings findings={p.gender_power.findings} dim="gender_power" onFocus={setFocus} />
          <p className="subtle">
            Gender readings are analytical interpretations. A phrase is not labelled misogynistic merely for mentioning women; sensitive labels need
            quoted evidence or are shown as low-confidence hypotheses.
          </p>
        </Section>

        {READINGS.filter((r) => (p[r.key] as DimensionReading).findings.length).map((r) => {
          const reading = p[r.key] as DimensionReading;
          return (
            <Section key={r.key} id={r.key} dim={r.dim} title={r.title} ne={DIMENSION_LABELS[r.dim].ne} summary={reading.summary}>
              <Findings findings={reading.findings} dim={r.dim} onFocus={setFocus} />
              {r.key === "cultural" && result.concepts.length > 0 && (
                <ul className="concepts">
                  {result.concepts.map((c) => (
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
              )}
            </Section>
          );
        })}

        <Section id="linguistic" dim="rhetoric" title="Linguistic reading" ne="भाषिक पठन" summary={p.rhetoric.summary}>
          {p.text_types.length > 0 && <p className="subtle">Form: {p.text_types.join(", ")}</p>}
          <Findings findings={p.rhetoric.findings} dim="rhetoric" onFocus={setFocus} />
          {p.key_terms.length > 0 && (
            <table className="data-table key-terms">
              <caption className="visually-hidden">Key terms</caption>
              <thead>
                <tr>
                  <th scope="col">Term</th>
                  <th scope="col">Gloss</th>
                  <th scope="col">Note</th>
                </tr>
              </thead>
              <tbody>
                {p.key_terms.map((k, i) => (
                  <tr key={i}>
                    <td>
                      <span lang="ne">{k.term}</span>
                      <br />
                      <span className="translit">{k.transliteration}</span>
                    </td>
                    <td>
                      {k.gloss}
                      {k.culturally_specific && <span className="tag tag-ne" title="No exact English equivalent">no exact equivalent</span>}
                    </td>
                    <td className="subtle">{k.note}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Section>

        <Section id="implied" dim="philosophical" title="Implied meaning" ne="निहित अर्थ">
          {p.implied.literal || p.implied.implied || p.implied.cultural_reading ? (
            <dl className="implied">
              {p.implied.literal && (
                <>
                  <dt>Literal meaning</dt>
                  <dd>{p.implied.literal}</dd>
                </>
              )}
              {p.implied.implied && (
                <>
                  <dt>Implied / secondary meaning</dt>
                  <dd>{p.implied.implied}</dd>
                </>
              )}
              {p.implied.cultural_reading && (
                <>
                  <dt>Cultural reading</dt>
                  <dd>{p.implied.cultural_reading}</dd>
                </>
              )}
            </dl>
          ) : (
            <p className="muted">An implied-meaning reading needs the AI engine or a matching corpus entry.</p>
          )}
          {p.implied.alternatives.length > 0 && (
            <>
              <h3>Alternative readings</h3>
              <ul className="alternatives">
                {p.implied.alternatives.map((a, i) => (
                  <li key={i}>{a}</li>
                ))}
              </ul>
            </>
          )}
          <p className="row">
            <span className="subtle">Confidence in this reading:</span> <ConfidenceIndicator value={p.implied.confidence} />
          </p>
          <p className="subtle">These are possible readings of the words, not claims about what the author intended.</p>
        </Section>
      </div>

      {notEvident.length > 0 && (
        <p className="not-evident subtle">
          <strong>Not evident in the wording:</strong> {notEvident.join(", ")}. “Not evident” means no textual basis was found; it is not a negative
          finding.
        </p>
      )}

      {p.themes.length > 0 && (
        <section className="themes-section" aria-labelledby="themes-h">
          <h2 id="themes-h">Codebook themes</h2>
          <ul className="theme-list">
            {p.themes.map((t) => (
              <li key={t.code}>
                <ThemeBadge code={t.code} themes={themes} to={`/corpus?theme=${t.code}`} />
                <ConfidenceIndicator value={t.confidence} compact />
                <span className="subtle">{t.rationale}</span>
              </li>
            ))}
          </ul>
        </section>
      )}

      <RoadDivider />

      <section aria-labelledby="related-h">
        <h2 id="related-h">
          Related expressions <span lang="ne" className="h-ne">सम्बन्धित अभिव्यक्ति</span>
        </h2>
        <RelatedList items={result.related} themes={themes} />
      </section>

      {result.references.length > 0 && (
        <section aria-labelledby="refs-h" className="refs-section">
          <h2 id="refs-h">References</h2>
          <ul className="references">
            {result.references.map((r) => (
              <ReferenceCard key={r.id} reference={r} />
            ))}
          </ul>
          <p className="subtle">Curated scholarly sources linked to the concepts in this reading. Verify details before citing.</p>
        </section>
      )}

      <details className="transparency">
        <summary>How this reading was made</summary>
        <ul>
          <li>
            Engine: {result.engine.mode === "llm" ? `AI-assisted (${result.engine.model}, effort ${result.engine.effort})` : "baseline (corpus + lexicon + rules)"};
            taxonomy v{result.engine.taxonomy_version}; prompt {result.engine.prompt_version}
            {result.engine.duration_ms !== null && `; ${(result.engine.duration_ms / 1000).toFixed(1)} s`}.
          </li>
          <li>
            Evidence check: {result.verification.quotes_verified} of {result.verification.quotes_checked} quotes found in the phrase across{" "}
            {result.verification.findings_checked} findings.
            {result.verification.issues.length > 0 && (
              <ul>
                {result.verification.issues.map((i, k) => (
                  <li key={k}>
                    {i.label} ({i.dimension}){i.quote && <> — “<span lang="ne">{i.quote}</span>”</>}: {i.action}
                  </li>
                ))}
              </ul>
            )}
          </li>
          {unreflected.length > 0 && (
            <li>
              Lexical cues not reflected in the reading:{" "}
              {unreflected.map((s, i) => (
                <span key={`${s.token}-${i}`}>
                  <span lang="ne">{s.token}</span> ({s.gloss}){" "}
                </span>
              ))}
            </li>
          )}
          {p.context_note && <li>Context: {p.context_note}</li>}
          {result.engine.notes.map((n, i) => (
            <li key={i}>{n}</li>
          ))}
        </ul>
      </details>
    </div>
  );
}

export default function Analyze() {
  const { id } = useParams();
  const location = useLocation();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const { meta } = useMeta();
  const state = location.state as NavState;

  const [text, setText] = useState(state?.text ?? state?.input?.text ?? params.get("q") ?? "");
  const [result, setResult] = useState<AnalysisResult | null>(state?.result ?? null);
  const [prelim, setPrelim] = useState<AnalysisResult | null>(null);
  const [stages, setStages] = useState<StageEvent[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const abort = useRef<AbortController | null>(null);
  const started = useRef(false);

  const run = async (input: AnalyzeInput) => {
    abort.current?.abort();
    const ctrl = new AbortController();
    abort.current = ctrl;
    setBusy(true);
    setError(null);
    setResult(null);
    setPrelim(null);
    setStages([]);
    try {
      const r = await analyzeStream(input, { onStage: (s) => setStages((x) => [...x, s]), onPreliminary: setPrelim }, ctrl.signal);
      setResult(r);
      if (r.id && r.id !== "preliminary") navigate(`/analysis/${r.id}`, { replace: true, state: { result: r } });
    } catch (e) {
      if ((e as Error).name !== "AbortError") setError((e as ApiError).message);
    } finally {
      setBusy(false);
    }
  };

  useEffect(() => {
    if (id) {
      if (result?.id === id) return;
      setBusy(true);
      api
        .analysis(id)
        .then((r) => {
          setResult(r);
          setText(r.input_text);
        })
        .catch((e: Error) => setError(e.message))
        .finally(() => setBusy(false));
      return;
    }
    const initial = state?.input ?? (text ? { text } : null);
    if (initial && !started.current) {
      started.current = true;
      run(initial);
    }
    return () => {
      // Abort on unmount; reset so a remount (e.g. React StrictMode) starts again.
      abort.current?.abort();
      started.current = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  const shown = result ?? prelim;
  return (
    <div className="container page">
      {shown ? (
        <p>
          <button
            className="btn btn-ghost btn-sm"
            onClick={() => {
              setResult(null);
              setPrelim(null);
              setText("");
              navigate("/analyze");
            }}
          >
            ← Analyse another phrase
          </button>
        </p>
      ) : (
        <>
          <h1>
            Analyse a phrase <span lang="ne" className="h-ne">वाक्य विश्लेषण</span>
          </h1>
          <PaintedFrame tone="peacock" className="input-panel">
            <PhraseInput
              value={text}
              onChange={setText}
              onSubmit={() => run({ text })}
              busy={busy}
              autoFocus
              maxChars={meta?.max_phrase_chars ?? 600}
              secondary={
                <Link to="/scan" className="btn btn-teal">
                  <span aria-hidden="true">📷</span> Photograph instead
                </Link>
              }
            />
          </PaintedFrame>
        </>
      )}

      {error && (
        <p className="notice notice-error" role="alert">
          {error}
        </p>
      )}

      {busy && !result && (
        <div className="analysis-wait">
          <AnalysisProgress stages={stages} engine={meta?.engine ?? "baseline"} />
          {!prelim && <div className="skeleton" style={{ height: 180 }} />}
        </div>
      )}
      {prelim && !result && (
        <p className="notice" role="status">
          Showing a preliminary reading from the research corpus and lexicon while the full analysis finishes…
        </p>
      )}
      {shown && <AnalysisView result={shown} preliminary={!result} />}
    </div>
  );
}

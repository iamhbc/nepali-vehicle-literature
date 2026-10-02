import { Fragment, type ReactNode } from "react";
import { Link } from "react-router-dom";
import type { Confidence, Finding, Kind, PhraseSummary, Reference, RelatedEntry, Theme } from "../api/types";
import { KIND_LABELS, dimColor } from "../lib/format";
import { NumberPlate } from "./ornaments";

const LEVEL: Record<Confidence, number> = { low: 1, medium: 2, high: 3 };

/** Three painted bars, like a signal-strength meter. Always paired with a word. */
export function ConfidenceIndicator({ value, compact = false }: { value: Confidence; compact?: boolean }) {
  const n = LEVEL[value] ?? 1;
  return (
    <span className={`confidence conf-${value}`} title={`Confidence: ${value}`}>
      <span className="conf-bars" aria-hidden="true">
        {[1, 2, 3].map((i) => (
          <span key={i} className={i <= n ? "on" : ""} />
        ))}
      </span>
      <span className={compact ? "visually-hidden" : "conf-word"}>
        {compact ? `Confidence: ${value}` : value[0].toUpperCase() + value.slice(1)}
      </span>
    </span>
  );
}

export function KindBadge({ kind }: { kind: Kind }) {
  const meta = KIND_LABELS[kind];
  return (
    <span className={`kind kind-${kind}`} title={meta.hint}>
      {meta.en}
    </span>
  );
}

export function ThemeBadge({ code, themes, to }: { code: string; themes?: Record<string, Theme>; to?: string }) {
  const t = themes?.[code];
  const body = (
    <>
      <span className="theme-dot" style={{ background: dimColor(t?.group === "rhetorical" ? "rhetoric" : t?.group) }} />
      <span>{t?.label_en ?? code}</span>
      {t?.label_ne && (
        <span className="theme-ne" lang="ne">
          {t.label_ne}
        </span>
      )}
    </>
  );
  return to ? (
    <Link to={to} className="theme-badge" title={t?.definition}>
      {body}
    </Link>
  ) : (
    <span className="theme-badge" title={t?.definition}>
      {body}
    </span>
  );
}

/** Renders a Nepali phrase and marks any evidence quotes that occur in it. */
export function NepaliPhrase({ text, highlight = [], size = "lg" }: { text: string; highlight?: string[]; size?: "lg" | "md" | "sm" }) {
  const quotes = highlight.filter((q) => q && text.includes(q)).sort((a, b) => b.length - a.length);
  let parts: ReactNode[] = [text];
  if (quotes.length) {
    const pattern = new RegExp(`(${quotes.map((q) => q.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).join("|")})`, "g");
    parts = text.split(pattern).map((part, i) =>
      quotes.includes(part) ? (
        <mark key={i} className="evidence-mark">
          {part}
        </mark>
      ) : (
        <Fragment key={i}>{part}</Fragment>
      ),
    );
  }
  return (
    <p className={`nepali-phrase np-${size}`} lang="ne">
      {parts}
    </p>
  );
}

export function PhraseCard({ phrase, themes, extra }: { phrase: PhraseSummary | RelatedEntry; themes?: Record<string, Theme>; extra?: ReactNode }) {
  const summary = phrase as PhraseSummary;
  return (
    <article className="phrase-card">
      <header className="phrase-card-head">
        <NumberPlate corpusId={phrase.corpus_id} size="sm" />
        {summary.needs_review && <span className="tag tag-review" title="First-pass coding awaiting native-speaker review">Needs review</span>}
        {summary.text_is_candidate && <span className="tag tag-warn" title="Text reconstructed from transliteration">Reconstructed text</span>}
      </header>
      <Link to={`/corpus/${phrase.id}`} className="phrase-card-link">
        <span className="phrase-card-text" lang="ne">
          {phrase.text}
        </span>
      </Link>
      {phrase.translation && <p className="phrase-card-translation">{phrase.translation}</p>}
      {extra}
      {phrase.codes.length > 0 && (
        <div className="badge-row">
          {phrase.codes.slice(0, 4).map((c) => (
            <ThemeBadge key={c} code={c} themes={themes} />
          ))}
        </div>
      )}
    </article>
  );
}

export function FindingItem({ finding, dimension, onFocus }: { finding: Finding; dimension: string; onFocus?: (quotes: string[]) => void }) {
  const focus = () => onFocus?.(finding.evidence);
  const blur = () => onFocus?.([]);
  return (
    <li
      className={`finding finding-${finding.kind}`}
      style={{ ["--dim" as string]: dimColor(dimension) }}
      onMouseEnter={focus}
      onMouseLeave={blur}
      onFocus={focus}
      onBlur={blur}
      tabIndex={finding.evidence.length ? 0 : undefined}
    >
      <div className="finding-head">
        <strong className="finding-label">{finding.label}</strong>
        <KindBadge kind={finding.kind} />
        <ConfidenceIndicator value={finding.confidence} />
      </div>
      {finding.explanation && <p className="finding-expl">{finding.explanation}</p>}
      {finding.evidence.length > 0 && (
        <p className="finding-evidence">
          <span className="subtle">Evidence: </span>
          {finding.evidence.map((q, i) => (
            <q key={i} lang="ne">
              {q}
            </q>
          ))}
        </p>
      )}
      {(finding.parties?.length || (finding.power_relation && finding.power_relation !== "not evident")) && (
        <p className="subtle">
          {finding.parties?.length ? <>Between: {finding.parties.join(" · ")}. </> : null}
          {finding.power_relation && finding.power_relation !== "not evident" ? <>Power: {finding.power_relation}</> : null}
        </p>
      )}
    </li>
  );
}

export function ReferenceCard({ reference }: { reference: Reference }) {
  return (
    <li className="reference">
      <p className="reference-title">
        {reference.url ? (
          <a href={reference.url} target="_blank" rel="noreferrer noopener">
            {reference.title}
          </a>
        ) : (
          reference.title
        )}
      </p>
      <p className="subtle">
        {reference.authors} ({reference.year ?? "n.d."}). {reference.source}.
      </p>
      {reference.matched_topics?.length > 0 && (
        <p className="subtle">Shown because the reading mentions: {reference.matched_topics.join(", ")}</p>
      )}
      {reference.note && <p className="subtle">{reference.note}</p>}
    </li>
  );
}

export function RelatedList({ items, themes }: { items: RelatedEntry[]; themes?: Record<string, Theme> }) {
  if (!items.length) {
    return <p className="muted">We couldn't find a strongly related expression in the current corpus.</p>;
  }
  return (
    <div className="card-grid">
      {items.map((r) => (
        <PhraseCard
          key={r.id}
          phrase={r}
          themes={themes}
          extra={
            <p className="related-why">
              <span className="score" title="Similarity score (wording + shared themes)">
                {Math.round(r.score * 100)}%
              </span>{" "}
              {r.reasons.join(" · ") || "Similar wording"}
            </p>
          }
        />
      ))}
    </div>
  );
}

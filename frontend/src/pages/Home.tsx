import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../api/client";
import { PhraseInput } from "../components/inputs";
import { useMeta } from "../components/Layout";
import { NumberPlate, PaintedFrame, RoadDivider, Rosette } from "../components/ornaments";
import { TruckAnimation } from "../components/TruckAnimation";
import { useAsync } from "../lib/useAsync";

export const CATEGORIES = [
  { key: "love", en: "Love", ne: "माया", theme: "LOVE_ROMANCE", tone: "rose" },
  { key: "family", en: "Family", ne: "परिवार", theme: "FAMILY", tone: "marigold" },
  { key: "humour", en: "Humour", ne: "हास्य", theme: "HUMOR", tone: "turmeric" },
  { key: "politics", en: "Politics", ne: "राजनीति", theme: "INSTITUTION_CRITIQUE", tone: "ink" },
  { key: "money", en: "Money", ne: "पैसा", theme: "MONEY_MATERIALISM", tone: "turmeric" },
  { key: "migration", en: "Migration", ne: "परदेश", theme: "MIGRATION", tone: "indigo" },
  { key: "religion", en: "Religion", ne: "धर्म", theme: "RELIGION_FATE", tone: "peacock" },
  { key: "gender", en: "Gender", ne: "लैङ्गिकता", theme: "WOMEN_REPRESENTATION", tone: "plum" },
  { key: "philosophy", en: "Philosophy", ne: "दर्शन", theme: "HOPE_RESILIENCE", tone: "leaf" },
  { key: "critique", en: "Social criticism", ne: "समाज आलोचना", theme: "CLASS_INEQUALITY_CRITIQUE", tone: "vermilion" },
] as const;

export default function Home() {
  const navigate = useNavigate();
  const { meta } = useMeta();
  const [text, setText] = useState("");
  const examples = useAsync(() => api.examples(), []);
  const ex = examples.data ?? [];

  const analyze = (t = text) => navigate("/analyze", { state: { text: t } });

  return (
    <>
      <section className="hero">
        <div className="container hero-inner">
          <p className="eyebrow">
            <Rosette size={16} /> A digital cultural microscope
          </p>
          <h1 className="hero-title" lang="ne">
            <span>सडकमा लेखिएका शब्दहरू</span>
            <span className="hero-title-2">समाजको ऐना पनि हुन सक्छन्।</span>
          </h1>
          <p className="hero-sub">
            Words painted on the road can also be a mirror of society. Explore the emotions, relationships, culture, politics and
            social meanings inside Nepali expressions.
          </p>
        </div>
        <TruckAnimation phrases={ex.length ? ex : [{ text: "फेरि भेटौंला" }]} />
      </section>

      <section className="container section-tight" aria-labelledby="analyse-heading">
        <PaintedFrame tone="peacock" className="input-panel">
          <h2 id="analyse-heading" className="panel-title">
            Analyse a phrase <span lang="ne">वाक्य विश्लेषण</span>
          </h2>
          <PhraseInput
            value={text}
            onChange={setText}
            onSubmit={() => analyze()}
            maxChars={meta?.max_phrase_chars ?? 600}
            secondary={
              <Link to="/scan" className="btn btn-teal">
                <span aria-hidden="true">📷</span> Photograph a vehicle
              </Link>
            }
          />
          <div className="examples">
            <p className="subtle">Try an inscription from the research corpus:</p>
            {examples.loading && <div className="skeleton" style={{ height: 44 }} />}
            {examples.error && <p className="subtle">Examples are unavailable right now.</p>}
            <ul className="example-list">
              {ex.map((e) => (
                <li key={e.id}>
                  <button className="example" onClick={() => analyze(e.text)} title={e.translation ?? undefined}>
                    <NumberPlate corpusId={e.corpus_id} size="sm" />
                    <span lang="ne">{e.text}</span>
                  </button>
                </li>
              ))}
            </ul>
          </div>
        </PaintedFrame>
      </section>

      <RoadDivider />

      <section className="container section" aria-labelledby="explore-heading">
        <h2 id="explore-heading">
          Explore the corpus <span lang="ne" className="h-ne">संग्रह हेर्नुहोस्</span>
        </h2>
        <p className="muted">Inscriptions collected from Nepali vehicles, coded across many dimensions at once.</p>
        <ul className="category-grid">
          {CATEGORIES.map((c) => (
            <li key={c.key}>
              <Link to={`/corpus?theme=${c.theme}`} className={`category tone-${c.tone}`}>
                <span className="category-ne" lang="ne">
                  {c.ne}
                </span>
                <span className="category-en">{c.en}</span>
              </Link>
            </li>
          ))}
        </ul>
      </section>

      <section className="container section how" aria-labelledby="how-heading">
        <h2 id="how-heading">What the analysis asks</h2>
        <ol className="how-steps">
          <li>
            <strong>What does it say?</strong> Transliteration, literal and contextual translation, key cultural terms.
          </li>
          <li>
            <strong>What does it feel and imply?</strong> Emotions, love, relationships, and implied or secondary meaning.
          </li>
          <li>
            <strong>What does it reflect?</strong> Social, economic, political, cultural, gender and power dimensions.
          </li>
          <li>
            <strong>How sure are we?</strong> Every reading cites its evidence, carries a confidence, and is marked as evidence,
            interpretation or hypothesis.
          </li>
        </ol>
        <p className="subtle">
          {meta?.engine === "llm"
            ? "Readings combine the research corpus, a cultural lexicon and an AI language model, checked against the phrase."
            : "This server currently runs the baseline engine: research-corpus coding, a cultural lexicon and rule-based rhetoric. AI interpretation is not configured."}{" "}
          <Link to="/method">How analysis works →</Link>
        </p>
      </section>
    </>
  );
}

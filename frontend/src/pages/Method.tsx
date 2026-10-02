import { useEffect } from "react";
import { useLocation } from "react-router-dom";
import { api } from "../api/client";
import { ConfidenceIndicator, KindBadge, ReferenceCard } from "../components/analysis-ui";
import { useMeta } from "../components/Layout";
import { PaintedFrame } from "../components/ornaments";
import { useAsync } from "../lib/useAsync";

export default function Method() {
  const { meta } = useMeta();
  const refs = useAsync(() => api.references(), []);
  const { hash } = useLocation();
  useEffect(() => {
    if (hash) document.getElementById(hash.slice(1))?.scrollIntoView();
  }, [hash]);

  return (
    <div className="container page prose">
      <h1>
        How analysis works <span lang="ne" className="h-ne">विधि</span>
      </h1>
      <p className="lead">
        This platform reads Nepali expressions as cultural documents. It does not decide what a phrase “really” means or what its author intended. It
        offers structured, evidenced readings that researchers can check, correct and build on.
      </p>

      <h2>The pipeline</h2>
      <ol className="pipeline">
        <li>
          <strong>Reading the text.</strong> Unicode normalization, script and language detection, and an automatic transliteration with Nepali
          vowel-deletion rules.
        </li>
        <li>
          <strong>The research corpus first.</strong> The phrase is matched against the collected inscriptions using spelling-tolerant matching and
          similarity search. If it is already in the corpus, the researcher-coded record is shown alongside any new reading.
        </li>
        <li>
          <strong>Cultural cues.</strong> A curated lexicon and glossary flag words like माया, इज्जत, कर्म or खाडी that carry cultural weight, and
          rule-based detectors identify rhyme, antithesis, rhetorical questions, code-mixing and reported speech.
        </li>
        <li>
          <strong>Interpretation.</strong>{" "}
          {meta?.engine === "llm"
            ? "An AI language model writes a structured reading across every dimension, guided by the codebook and comparable corpus entries. Its output must fit a fixed schema; free text never drives the application."
            : "On this server the AI interpretation step is not configured, so readings come from the corpus, lexicon and rules only, and say so."}
        </li>
        <li>
          <strong>Verification.</strong> Every quoted piece of evidence is checked against the phrase. Quotes that are not there are removed and
          confidence is lowered. Sensitive labels (misogyny, patriarchy, caste, political affiliation, religious identity) without verified evidence
          become low-confidence hypotheses.
        </li>
        <li>
          <strong>The cultural map.</strong> The reading becomes a graph: phrase → dimensions → findings, plus themes, concepts and related
          expressions.
        </li>
      </ol>

      <h2>Reading the labels</h2>
      <PaintedFrame tone="peacock" ornate={false}>
        <dl className="legend-list">
          <dt>
            <KindBadge kind="evidence" />
          </dt>
          <dd>What the words literally say.</dd>
          <dt>
            <KindBadge kind="interpretation" />
          </dt>
          <dd>What the analysis infers from the wording.</dd>
          <dt>
            <KindBadge kind="hypothesis" />
          </dt>
          <dd>What may be implied: plausible, not established.</dd>
          <dt>
            <ConfidenceIndicator value="high" />
          </dt>
          <dd>The reading is explicit in the wording.</dd>
          <dt>
            <ConfidenceIndicator value="medium" />
          </dt>
          <dd>It needs contextual or cultural inference.</dd>
          <dt>
            <ConfidenceIndicator value="low" />
          </dt>
          <dd>Several readings are plausible.</dd>
        </dl>
      </PaintedFrame>
      <p>
        <strong>Multi-label by design.</strong> One inscription can be romantic, nostalgic, patriarchal, humorous and class-conscious at once. Nothing is
        reduced to positive / negative / neutral. “Not evident” means no textual basis was found, not that a dimension is absent from the culture.
      </p>
      <p>
        <strong>Implied meaning, not hidden intent.</strong> We separate the literal meaning, a possible implied meaning, a cultural reading and
        alternative readings, each with a confidence. These are readings of words, not claims about people.
      </p>
      <p>
        <strong>Culturally specific concepts</strong> such as माया, विरह, इज्जत and भाग्य are kept in Nepali and explained, because English has no exact
        equivalent. Greek love categories (eros, storge, philia, agape) are used only as an analytical lens.
      </p>

      <h2>The research corpus</h2>
      <p>
        The corpus began with inscriptions collected and multi-label coded by the project. The original workbook is preserved unchanged; a separate
        normalized version carries every correction, flag and review note. The initial coding is a first pass and is marked <em>needs review</em> wherever a
        native-speaker check is still required. Researchers review, approve or correct every label in the protected researcher area, and every change is
        logged.
      </p>

      <h2 id="privacy">Privacy and photographs</h2>
      <ul>
        <li>No account is needed and no personal information is requested.</li>
        <li>
          Photos are shrunk on your device before upload, which also removes location and camera metadata. The server re-encodes the image in memory,
          reads it once, and <strong>never stores it</strong>.
        </li>
        <li>
          The text of an analysis is saved so results can be shared by link and so repeated analyses are fast. It is not linked to you.
        </li>
        <li>
          If you choose to share an inscription with the researchers, only its text and the optional vehicle and place you selected are kept.
        </li>
        <li>Your theme and sound preferences are stored only in your own browser.</li>
      </ul>

      <h2>Limitations</h2>
      <ul>
        <li>AI readings can be wrong, especially for slang, regional dialects, wordplay and recent political references.</li>
        <li>Painted lettering is hard to read; always check the OCR text before analysing.</li>
        <li>The corpus is small and has no location or vehicle data yet, so comparisons across regions and vehicles are not possible yet.</li>
        <li>References are curated topic guides, not citations of the specific phrase.</li>
      </ul>

      <h2>Curated references</h2>
      {refs.data && (
        <ul className="references">
          {refs.data.map((r) => (
            <ReferenceCard key={r.id} reference={{ ...r, matched_topics: [], level: 2 }} />
          ))}
        </ul>
      )}
      <p className="subtle">Taxonomy version {meta?.taxonomy_version ?? "…"}.</p>
    </div>
  );
}

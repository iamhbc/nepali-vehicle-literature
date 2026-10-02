import { Link } from "react-router-dom";
import { api } from "../api/client";
import { BarList, CooccurrenceNetwork } from "../components/charts";
import { useMeta } from "../components/Layout";
import { PaintedFrame } from "../components/ornaments";
import { dimColor, toNepaliDigits } from "../lib/format";
import { useAsync } from "../lib/useAsync";

const FAMILY_COLOURS: Record<string, string> = {
  longing: "var(--rose)",
  sorrow: "var(--indigo)",
  disillusionment: "var(--plum)",
  anger: "var(--vermilion)",
  fear: "var(--dim-rhetoric)",
  joy: "var(--marigold)",
  pride: "var(--dim-economic)",
  hope: "var(--leaf)",
  devotion: "var(--peacock)",
  compassion: "var(--dim-concepts)",
  irony: "var(--ink-2)",
  ambivalence: "var(--ink-3)",
};

export default function Explore() {
  const { data: s, error, loading } = useAsync(() => api.stats(), []);
  const clusters = useAsync(() => api.clusters(), []);
  const { themes } = useMeta();

  return (
    <div className="container page">
      <h1>
        Explore the patterns <span lang="ne" className="h-ne">ढाँचा अन्वेषण</span>
      </h1>
      <p className="muted">
        How emotions, themes and relationships are distributed across the research corpus. Every figure is computed live from the coded entries.
      </p>
      {error && <p className="notice notice-error">{error}</p>}
      {loading && !s && <div className="skeleton" style={{ height: 320 }} />}
      {s && (
        <>
          <ul className="stat-tiles">
            <li>
              <span className="stat-n" lang="ne">{toNepaliDigits(s.total)}</span>
              <span>inscriptions</span>
            </li>
            <li>
              <span className="stat-n" lang="ne">{toNepaliDigits(s.themes.filter((t) => t.count).length)}</span>
              <span>themes in use</span>
            </li>
            <li>
              <span className="stat-n" lang="ne">{toNepaliDigits(s.valence.find((v) => v.label === "Mixed")?.count ?? 0)}</span>
              <span>with mixed feelings</span>
            </li>
            <li>
              <span className="stat-n" lang="ne">{toNepaliDigits(s.needs_review)}</span>
              <span>awaiting review</span>
            </li>
          </ul>

          <div className="grid-2 explore-grid">
            <PaintedFrame tone="vermilion" ornate={false} as="section" aria-labelledby="themes-h">
              <h2 id="themes-h">Theme map</h2>
              <p className="subtle">An inscription can carry several themes at once.</p>
              <BarList
                caption="Inscriptions per theme"
                data={[...s.themes]
                  .filter((t) => t.count)
                  .sort((a, b) => b.count - a.count)
                  .map((t) => ({
                    key: t.code,
                    label: t.label_en,
                    sublabel: t.label_ne,
                    value: t.count,
                    colour: dimColor(t.group === "rhetorical" ? "rhetoric" : t.group),
                    href: `/corpus?theme=${t.code}`,
                  }))}
              />
            </PaintedFrame>

            <div className="stack">
              <PaintedFrame tone="rose" ornate={false} as="section" aria-labelledby="emo-h">
                <h2 id="emo-h">Emotion distribution</h2>
                <p className="subtle">Coded emotions grouped into families.</p>
                <BarList
                  caption="Inscriptions per emotion family"
                  data={s.emotion_families
                    .filter((f) => f.key !== "other")
                    .map((f) => ({ key: f.key, label: f.label_en, sublabel: f.label_ne, value: f.count, colour: FAMILY_COLOURS[f.key] }))}
                />
              </PaintedFrame>
              <PaintedFrame tone="peacock" ornate={false} as="section" aria-labelledby="val-h">
                <h2 id="val-h">Feeling, not just polarity</h2>
                <div className="valence-bar" role="img" aria-label={s.valence.map((v) => `${v.label}: ${v.count}`).join(", ")}>
                  {s.valence.map((v) => (
                    <span key={v.label} className={`valence-seg valence-${v.label.toLowerCase()}`} style={{ flexGrow: v.count }}>
                      {v.label} {v.count}
                    </span>
                  ))}
                </div>
                <p className="subtle">Many inscriptions hold opposing feelings at once; “mixed” is the most common reading.</p>
              </PaintedFrame>
            </div>
          </div>

          <PaintedFrame tone="indigo" ornate={false} as="section" aria-labelledby="net-h" className="network-panel">
            <h2 id="net-h">Theme relationship network</h2>
            <p className="subtle">Which themes travel together. Hover or focus a theme to trace its connections.</p>
            {s.cooccurrence && <CooccurrenceNetwork nodes={s.themes} links={s.cooccurrence} minCount={2} />}
          </PaintedFrame>

          <div className="grid-2 explore-grid">
            <PaintedFrame tone="rose" ornate={false} as="section" aria-labelledby="love-h">
              <h2 id="love-h">Kinds of love</h2>
              <BarList caption="Love types" data={s.love_types.map((l) => ({ key: l.key, label: l.label_en, value: l.count, colour: "var(--rose)" }))} />
              <p className="subtle">Greek categories are an analytical lens; माया often covers several at once.</p>
            </PaintedFrame>
            <PaintedFrame tone="turmeric" ornate={false} as="section" aria-labelledby="power-h">
              <h2 id="power-h">Stance toward power</h2>
              <BarList caption="Power stances" data={s.power_stances.map((p) => ({ key: p.label, label: p.label, value: p.count, colour: "var(--plum)" }))} />
              <p className="subtle">Does the inscription reproduce, reflect, critique or resist a hierarchy?</p>
            </PaintedFrame>
          </div>

          <section aria-labelledby="clusters-h" className="section-tight">
            <h2 id="clusters-h">Emergent clusters</h2>
            <ul className="cluster-list">
              {(clusters.data ?? []).map((c) => (
                <li key={c.name} className="cluster">
                  <h3>{c.name}</h3>
                  <p className="muted">{c.description}</p>
                  <p className="subtle">
                    {c.member_ids.map((id, i) => (
                      <span key={id}>
                        {i > 0 && " · "}
                        <Link to={`/corpus/${id}`}>NVL-{String(id).padStart(3, "0")}</Link>
                      </span>
                    ))}
                  </p>
                </li>
              ))}
            </ul>
          </section>

          <div className="grid-2 explore-grid">
            <PaintedFrame tone="peacock" ornate={false} as="section" aria-labelledby="geo-h">
              <h2 id="geo-h">Geography</h2>
              <h3>Places named in inscriptions</h3>
              <BarList
                caption="Districts mentioned in the text"
                data={s.geography.mentioned.map((g) => ({ key: g.district, label: g.district, sublabel: g.province ? `${g.province} Province` : undefined, value: g.count, colour: "var(--peacock)" }))}
              />
              <h3>Where inscriptions were seen</h3>
              {s.geography.observed.length ? (
                <BarList caption="Districts where inscriptions were observed" data={s.geography.observed.map((g) => ({ key: g.district, label: g.district, value: g.count }))} />
              ) : (
                <p className="muted">
                  No observation locations are recorded yet: the source dataset has none. Locations added with new photographs will appear here, ready
                  for mapping.
                </p>
              )}
            </PaintedFrame>
            <PaintedFrame tone="turmeric" ornate={false} as="section" aria-labelledby="veh-h">
              <h2 id="veh-h">Vehicle types</h2>
              {s.vehicles.length ? (
                <BarList caption="Inscriptions per vehicle type" data={s.vehicles.map((v) => ({ key: v.slug, label: v.slug, value: v.count }))} />
              ) : (
                <p className="muted">
                  No vehicle types are recorded in the source dataset yet, so questions like “do trucks and buses speak differently?” must wait for
                  new contributions. <Link to="/scan">Add one</Link>.
                </p>
              )}
              <h3>Forms of expression</h3>
              <BarList caption="Text types" data={s.text_types.slice(0, 8).map((t) => ({ key: t.label, label: t.label, value: t.count, colour: "var(--indigo)" }))} />
            </PaintedFrame>
          </div>
          <p className="subtle">Theme colours follow the dimension they belong to. {Object.keys(themes).length} codes in taxonomy.</p>
        </>
      )}
    </div>
  );
}

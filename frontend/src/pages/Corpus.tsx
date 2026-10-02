import { useMemo } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api } from "../api/client";
import { PhraseCard, ThemeBadge } from "../components/analysis-ui";
import { SearchBar } from "../components/inputs";
import { useMeta } from "../components/Layout";
import { useAsync } from "../lib/useAsync";

export default function Corpus() {
  const [params, setParams] = useSearchParams();
  const { themes } = useMeta();
  const q = params.get("q") ?? "";
  const theme = params.get("theme") ?? "";
  const valence = params.get("valence") ?? "";
  const review = params.get("review") ?? "";

  const set = (key: string, value: string) => {
    const next = new URLSearchParams(params);
    if (value) next.set(key, value);
    else next.delete(key);
    setParams(next, { replace: key !== "q" });
  };

  const themeCounts = useAsync(() => api.themes(), []);
  const list = useAsync(
    () => (q ? Promise.resolve(null) : api.phrases({ theme: theme || undefined, valence: valence || undefined, needs_review: review ? review === "yes" : undefined })),
    [q, theme, valence, review],
  );
  const search = useAsync(() => (q ? api.search(q, theme || undefined) : Promise.resolve(null)), [q, theme]);

  const activeTheme = theme ? themes[theme] : null;
  const items = useMemo(() => list.data?.items ?? [], [list.data]);

  return (
    <div className="container page">
      <h1>
        Research corpus <span lang="ne" className="h-ne">संग्रह</span>
      </h1>
      <p className="muted">
        Inscriptions collected from Nepali vehicles and coded by researchers across emotion, relationship, social, economic, political, cultural,
        gender and rhetorical dimensions. Codes marked <em>needs review</em> are a first pass awaiting native-speaker validation.
      </p>
      <SearchBar initial={q} onSearch={(v) => set("q", v)} busy={search.loading && !!q} />

      <div className="filters">
        <div className="filter-group" role="group" aria-label="Filter by theme">
          <button className={`chip ${!theme ? "is-on" : ""}`} aria-pressed={!theme} onClick={() => set("theme", "")}>
            All themes
          </button>
          {(themeCounts.data ?? []).map((t) => (
            <button key={t.code} className={`chip ${theme === t.code ? "is-on" : ""}`} aria-pressed={theme === t.code} onClick={() => set("theme", theme === t.code ? "" : t.code)}>
              {t.label_en} <span className="chip-count">{t.count}</span>
            </button>
          ))}
        </div>
        {!q && (
          <div className="row">
            <label className="inline-select">
              Valence
              <select value={valence} onChange={(e) => set("valence", e.target.value)}>
                <option value="">Any</option>
                <option value="positive">Positive</option>
                <option value="negative">Negative</option>
                <option value="mixed">Mixed</option>
                <option value="neutral">Neutral</option>
              </select>
            </label>
            <label className="inline-select">
              Review
              <select value={review} onChange={(e) => set("review", e.target.value)}>
                <option value="">Any</option>
                <option value="yes">Needs review</option>
                <option value="no">Reviewed / no issues</option>
              </select>
            </label>
          </div>
        )}
      </div>

      {activeTheme && (
        <p className="theme-intro">
          <ThemeBadge code={activeTheme.code} themes={themes} /> {activeTheme.definition}.{" "}
          <span className="subtle">({activeTheme.origin === "Emergent" ? "Emerged from the data" : "From the research framework"})</span>
        </p>
      )}

      {q ? (
        <section aria-live="polite" aria-busy={search.loading}>
          {search.error && <p className="notice notice-error">{search.error}</p>}
          {search.data && (
            <>
              <p className="subtle">
                {search.data.results.length} results for “{search.data.query}”
                {search.data.interpreted_themes.length > 0 && (
                  <> · read as: {search.data.interpreted_themes.map((t) => t.label_en).join(", ")}</>
                )}{" "}
                · <button className="linklike" onClick={() => set("q", "")}>clear search</button>
              </p>
              {search.data.note && <p className="notice">{search.data.note}</p>}
              <div className="card-grid">
                {search.data.results.map((r) => (
                  <PhraseCard
                    key={r.id}
                    phrase={r}
                    themes={themes}
                    extra={r.reasons.length ? <p className="related-why">{r.reasons.join(" · ")}</p> : null}
                  />
                ))}
              </div>
            </>
          )}
        </section>
      ) : (
        <section aria-live="polite" aria-busy={list.loading}>
          {list.error && <p className="notice notice-error">{list.error}</p>}
          {list.loading && !list.data && <div className="skeleton" style={{ height: 240 }} />}
          {list.data && (
            <>
              <p className="subtle">{list.data.total} inscriptions</p>
              {items.length === 0 && <p className="muted">No inscriptions match these filters.</p>}
              <div className="card-grid">
                {items.map((p) => (
                  <PhraseCard key={p.id} phrase={p} themes={themes} />
                ))}
              </div>
            </>
          )}
        </section>
      )}
      <p className="subtle">
        Know an inscription that isn't here? <Link to="/scan">Photograph it</Link> and choose to share it with the researchers.
      </p>
    </div>
  );
}

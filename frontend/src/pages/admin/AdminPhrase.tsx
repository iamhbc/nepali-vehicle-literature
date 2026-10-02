import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ApiError, adminApi } from "../../api/client";
import type { PhraseDetail } from "../../api/types";
import { ThemeBadge } from "../../components/analysis-ui";
import { VehicleSelector } from "../../components/inputs";
import { useMeta } from "../../components/Layout";
import { NumberPlate, PaintedFrame } from "../../components/ornaments";
import { AuditLog, useAdmin } from "./AdminApp";

export default function AdminPhrase() {
  const { id } = useParams();
  const { session } = useAdmin();
  const { themes } = useMeta();
  const [p, setP] = useState<PhraseDetail | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [form, setForm] = useState({ text_nepali: "", transliteration: "", translation_normalized: "", review_reason: "", needs_review: true, vehicle_type: "", note: "" });
  const [addCode, setAddCode] = useState("");
  const [auditKey, setAuditKey] = useState(0);

  const load = (detail: PhraseDetail) => {
    setP(detail);
    setForm({
      text_nepali: detail.status === "text_missing" ? detail.text_candidate ?? "" : detail.text_original,
      transliteration: detail.transliteration_original ?? "",
      translation_normalized: detail.translation_normalized ?? "",
      review_reason: detail.review_reason ?? "",
      needs_review: detail.needs_review,
      vehicle_type: detail.vehicle_type ?? "",
      note: "",
    });
    setAuditKey((k) => k + 1);
  };

  useEffect(() => {
    adminApi.get<PhraseDetail>(`/phrases/${id}`, session.token).then(load).catch((e: ApiError) => setMsg(e.message));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  const act = async (fn: () => Promise<PhraseDetail | { phrase: PhraseDetail; ai_codes_added?: string[] }>, ok: string) => {
    try {
      const r = await fn();
      const detail = "phrase" in r ? r.phrase : r;
      load(detail);
      setMsg("ai_codes_added" in r ? `${ok} AI suggested: ${r.ai_codes_added?.join(", ") || "nothing new"}.` : ok);
    } catch (e) {
      setMsg((e as ApiError).message);
    }
  };

  if (!p) return <p className="muted">{msg ?? "Loading…"}</p>;
  return (
    <div className="stack">
      <p>
        <Link to="/admin">← Review queue</Link> · <Link to={`/corpus/${p.id}`}>Public page</Link>
      </p>
      <div className="row">
        <NumberPlate corpusId={p.corpus_id} />
        <span className="tag">{p.status}</span>
        {p.needs_review && <span className="tag tag-review">needs review</span>}
        <span className="subtle">{p.updated_by ? `Last edited by ${p.updated_by}` : "Unedited import"}</span>
      </div>
      {msg && <p className="notice" role="status">{msg}</p>}
      {p.review_reason && <p className="notice notice-warn"><strong>Review note:</strong> {p.review_reason}</p>}

      <PaintedFrame tone="indigo" ornate={false} as="section" aria-labelledby="edit-h">
        <h2 id="edit-h">Edit entry</h2>
        <form
          className="stack"
          onSubmit={(e) => {
            e.preventDefault();
            act(() => adminApi.send<PhraseDetail>(`/phrases/${p.id}`, session.token, "PUT", form), "Saved.");
          }}
        >
          <div className="field">
            <label htmlFor="t">Nepali text</label>
            <textarea id="t" lang="ne" rows={2} value={form.text_nepali} onChange={(e) => setForm({ ...form, text_nepali: e.target.value })} />
            {p.status === "text_missing" && <span className="field-hint">Original cell: “{p.text_original}”. Saving confirms the reconstructed text.</span>}
          </div>
          <div className="field">
            <label htmlFor="tr">Transliteration</label>
            <input id="tr" type="text" value={form.transliteration} onChange={(e) => setForm({ ...form, transliteration: e.target.value })} />
            <span className="field-hint">Automatic: {p.transliteration_auto}</span>
          </div>
          <div className="field">
            <label htmlFor="tn">Corrected translation</label>
            <textarea id="tn" rows={2} value={form.translation_normalized} onChange={(e) => setForm({ ...form, translation_normalized: e.target.value })} />
            <span className="field-hint">Original (never overwritten): {p.translation_original}</span>
          </div>
          <div className="field">
            <label htmlFor="rr">Review note</label>
            <input id="rr" type="text" value={form.review_reason} onChange={(e) => setForm({ ...form, review_reason: e.target.value })} />
          </div>
          <VehicleSelector value={form.vehicle_type} onChange={(v) => setForm({ ...form, vehicle_type: v })} />
          <label className="checkbox">
            <input type="checkbox" checked={form.needs_review} onChange={(e) => setForm({ ...form, needs_review: e.target.checked })} />
            <span>Still needs review</span>
          </label>
          <div className="field">
            <label htmlFor="note">Change note (kept in the audit log)</label>
            <input id="note" type="text" value={form.note} onChange={(e) => setForm({ ...form, note: e.target.value })} />
          </div>
          <div className="row">
            <button className="btn btn-primary btn-sm">Save changes</button>
            <button type="button" className="btn btn-teal btn-sm" onClick={() => act(() => adminApi.send<PhraseDetail>(`/phrases/${p.id}/approve`, session.token, "POST", { note: form.note || null }), "Approved: proposed labels are now approved.")}>
              Approve coding
            </button>
            <button type="button" className="btn btn-sm" onClick={() => act(() => adminApi.send(`/phrases/${p.id}/reanalyze`, session.token, "POST"), "Re-analysed.")}>
              Re-run analysis
            </button>
            {p.status !== "archived" ? (
              <button type="button" className="btn btn-ghost btn-sm" onClick={() => window.confirm("Archive this entry? It is hidden from the public but never deleted.") && act(async () => { await adminApi.send(`/phrases/${p.id}`, session.token, "DELETE"); return adminApi.get<PhraseDetail>(`/phrases/${p.id}`, session.token); }, "Archived.")}>
                Archive
              </button>
            ) : (
              <button type="button" className="btn btn-ghost btn-sm" onClick={() => act(() => adminApi.send<PhraseDetail>(`/phrases/${p.id}`, session.token, "PUT", { status: "active" }), "Restored.")}>
                Restore
              </button>
            )}
          </div>
        </form>
      </PaintedFrame>

      <PaintedFrame tone="turmeric" ornate={false} as="section" aria-labelledby="themes-h">
        <h2 id="themes-h">Theme decisions</h2>
        <p className="muted">Every code keeps its source (corpus import, AI, researcher). Approve or reject each one.</p>
        <table className="data-table">
          <thead>
            <tr><th scope="col">Theme</th><th scope="col">Source</th><th scope="col">Status</th><th scope="col">Decide</th></tr>
          </thead>
          <tbody>
            {p.themes.map((t) => (
              <tr key={`${t.code}-${t.source}`}>
                <td><ThemeBadge code={t.code} themes={themes} />{t.rationale && <div className="subtle">{t.rationale}</div>}</td>
                <td>{t.source}{t.confidence && <span className="subtle"> · {t.confidence}</span>}</td>
                <td><span className={`tag status-${t.status}`}>{t.status}</span></td>
                <td className="row">
                  {(["approved", "rejected"] as const).map((s) => (
                    <button key={s} className="btn btn-sm" disabled={t.status === s} onClick={() => act(() => adminApi.send<PhraseDetail>(`/phrases/${p.id}/themes`, session.token, "PUT", { code: t.code, status: s, source: t.source }), `Theme ${s}.`)}>
                      {s === "approved" ? "Approve" : "Reject"}
                    </button>
                  ))}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        <form
          className="row"
          onSubmit={(e) => {
            e.preventDefault();
            if (addCode) act(() => adminApi.send<PhraseDetail>(`/phrases/${p.id}/themes`, session.token, "PUT", { code: addCode, status: "approved", source: "researcher" }), "Theme added.");
          }}
        >
          <label htmlFor="add-code" className="visually-hidden">Add a theme</label>
          <select id="add-code" value={addCode} onChange={(e) => setAddCode(e.target.value)}>
            <option value="">Add a theme…</option>
            {Object.values(themes).map((t) => <option key={t.code} value={t.code}>{t.label_en}</option>)}
          </select>
          <button className="btn btn-sm" disabled={!addCode}>Add</button>
        </form>
      </PaintedFrame>

      <section aria-labelledby="labels-h">
        <h2 id="labels-h">Coded labels</h2>
        <ul className="label-cloud">
          {p.labels.map((l) => (
            <li key={l.id} className="tag" title={`${l.source} · ${l.status}`}>
              <span className="subtle">{l.dimension}:</span> {l.label}
            </li>
          ))}
        </ul>
      </section>

      <section aria-labelledby="audit-h">
        <h2 id="audit-h">History</h2>
        <AuditLog key={auditKey} targetId={String(p.id)} />
      </section>
    </div>
  );
}

import { createContext, useContext, useEffect, useState, type FormEvent } from "react";
import { Link, NavLink, Route, Routes, useNavigate } from "react-router-dom";
import { ApiError, adminApi } from "../../api/client";
import type { PhraseSummary } from "../../api/types";
import { useMeta } from "../../components/Layout";
import { NumberPlate, PaintedFrame } from "../../components/ornaments";
import { useAsync } from "../../lib/useAsync";
import AdminPhrase from "./AdminPhrase";

interface Session {
  token: string;
  username: string;
  expires_at: string;
}

const KEY = "nvl.admin";
const AdminCtx = createContext<{ session: Session; logout: () => void } | null>(null);
export const useAdmin = () => useContext(AdminCtx)!;

// The researcher token lives in sessionStorage: it disappears when the tab closes.
function loadSession(): Session | null {
  try {
    const s = JSON.parse(sessionStorage.getItem(KEY) ?? "null") as Session | null;
    return s && new Date(s.expires_at) > new Date() ? s : null;
  } catch {
    return null;
  }
}

function Login({ onLogin }: { onLogin: (s: Session) => void }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const s = await adminApi.login(username, password);
      try {
        sessionStorage.setItem(KEY, JSON.stringify(s));
      } catch {
        /* session only in memory */
      }
      onLogin(s);
    } catch (err) {
      setError((err as ApiError).message);
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="container page narrow">
      <PaintedFrame tone="indigo">
        <h1>Researcher area</h1>
        <p className="muted">For corpus curators only. The public site never needs a login.</p>
        <form onSubmit={submit} className="stack">
          <div className="field">
            <label htmlFor="u">Username</label>
            <input id="u" type="text" autoComplete="username" value={username} onChange={(e) => setUsername(e.target.value)} required />
          </div>
          <div className="field">
            <label htmlFor="p">Password</label>
            <input id="p" type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} required />
          </div>
          {error && <p className="notice notice-error" role="alert">{error}</p>}
          <button className="btn btn-primary" disabled={busy}>
            {busy ? "Signing in…" : "Sign in"}
          </button>
        </form>
      </PaintedFrame>
    </div>
  );
}

function PhraseTable({ rows, showReason = false }: { rows: (PhraseSummary & { review_reason?: string | null })[]; showReason?: boolean }) {
  return (
    <div className="table-wrap">
      <table className="data-table admin-table">
        <thead>
          <tr>
            <th scope="col">Entry</th>
            <th scope="col">Text</th>
            <th scope="col">Themes</th>
            <th scope="col">{showReason ? "Why review" : "Status"}</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((p) => (
            <tr key={p.id}>
              <td>
                <Link to={`/admin/phrases/${p.id}`}>
                  <NumberPlate corpusId={p.corpus_id} size="sm" />
                </Link>
              </td>
              <td lang="ne" className="cell-text">
                <Link to={`/admin/phrases/${p.id}`}>{p.text}</Link>
              </td>
              <td className="subtle">{p.codes.join(", ")}</td>
              <td className="subtle">
                {showReason ? (
                  <>
                    {p.review_priority && <span className="tag tag-review">{p.review_priority}</span>} {p.review_reason}
                  </>
                ) : (
                  <>
                    {p.status}
                    {p.needs_review && " · needs review"}
                  </>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ReviewQueue() {
  const { session } = useAdmin();
  const q = useAsync(() => adminApi.get<(PhraseSummary & { review_reason: string | null })[]>("/review-queue", session.token), []);
  return (
    <section>
      <h2>Review queue</h2>
      <p className="muted">Entries whose coding needs a native-speaker check, highest priority (meaning-changing) first.</p>
      {q.error && <p className="notice notice-error">{q.error}</p>}
      {q.data && (q.data.length ? <PhraseTable rows={q.data} showReason /> : <p>Nothing waiting for review.</p>)}
    </section>
  );
}

function CorpusAdmin() {
  const { session } = useAdmin();
  const navigate = useNavigate();
  const q = useAsync(() => adminApi.get<PhraseSummary[]>("/phrases", session.token), []);
  const [text, setText] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const create = async (e: FormEvent) => {
    e.preventDefault();
    try {
      const p = await adminApi.send<{ id: number }>("/phrases", session.token, "POST", { text_nepali: text });
      navigate(`/admin/phrases/${p.id}`);
    } catch (e2) {
      setErr((e2 as ApiError).message);
    }
  };
  return (
    <section>
      <h2>Corpus entries</h2>
      <form onSubmit={create} className="row add-entry">
        <label htmlFor="new-text" className="visually-hidden">New inscription</label>
        <input id="new-text" type="text" lang="ne" placeholder="Add a new inscription (Nepali text)" value={text} onChange={(e) => setText(e.target.value)} />
        <button className="btn btn-primary btn-sm" disabled={!text.trim()}>Add entry</button>
      </form>
      {err && <p className="notice notice-error">{err}</p>}
      {q.data && <PhraseTable rows={q.data} />}
    </section>
  );
}

interface Submission {
  id: string;
  text: string;
  ocr_text: string | null;
  vehicle_type: string | null;
  district: string | null;
  created_at: string;
  status: string;
}

function Submissions() {
  const { session } = useAdmin();
  const q = useAsync(() => adminApi.get<Submission[]>("/submissions", session.token), []);
  const [edits, setEdits] = useState<Record<string, string>>({});
  const [msg, setMsg] = useState<string | null>(null);
  const decide = async (s: Submission, action: "accept" | "reject") => {
    try {
      await adminApi.send(`/submissions/${s.id}/${action}`, session.token, "POST", { text: edits[s.id] ?? s.text });
      setMsg(action === "accept" ? "Added to the corpus as a new entry needing review." : "Submission rejected.");
      q.reload();
    } catch (e) {
      setMsg((e as ApiError).message);
    }
  };
  return (
    <section>
      <h2>Public submissions</h2>
      <p className="muted">Inscriptions people chose to share. Correct OCR errors before accepting.</p>
      {msg && <p className="notice" role="status">{msg}</p>}
      {q.data?.length === 0 && <p>No pending submissions.</p>}
      <ul className="submission-list">
        {q.data?.map((s) => (
          <li key={s.id} className="submission">
            <textarea lang="ne" rows={2} value={edits[s.id] ?? s.text} onChange={(e) => setEdits({ ...edits, [s.id]: e.target.value })} aria-label="Submission text" />
            {s.ocr_text && s.ocr_text !== s.text && <p className="subtle">OCR read: <span lang="ne">{s.ocr_text}</span></p>}
            <p className="subtle">
              {[s.vehicle_type, s.district].filter(Boolean).join(" · ") || "No context"} · {new Date(s.created_at).toLocaleString()}
            </p>
            <div className="row">
              <button className="btn btn-primary btn-sm" onClick={() => decide(s, "accept")}>Accept into corpus</button>
              <button className="btn btn-sm" onClick={() => decide(s, "reject")}>Reject</button>
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}

function Analytics() {
  const { session } = useAdmin();
  const q = useAsync(() => adminApi.get<any>("/analytics?days=30", session.token), []);
  const a = q.data;
  return (
    <section>
      <h2>Analytics (30 days)</h2>
      {a && (
        <>
          <ul className="stat-tiles">
            <li><span className="stat-n">{a.analyses}</span><span>analyses</span></li>
            <li><span className="stat-n">{a.matched_corpus}</span><span>matched the corpus</span></li>
            <li><span className="stat-n">{a.median_ms ?? "–"}</span><span>median ms</span></li>
            <li><span className="stat-n">{a.submissions.pending}</span><span>pending submissions</span></li>
          </ul>
          <p>Engines: {Object.entries(a.engines).map(([k, v]) => `${k}: ${v}`).join(", ") || "none yet"}</p>
          <p>Most frequent themes in public analyses: {a.top_themes.map((t: { code: string; count: number }) => `${t.code} (${t.count})`).join(", ") || "none yet"}</p>
          <table className="data-table">
            <thead><tr><th scope="col">Day</th><th scope="col">Analyses</th></tr></thead>
            <tbody>{a.per_day.map((d: { day: string; count: number }) => <tr key={d.day}><td>{d.day}</td><td>{d.count}</td></tr>)}</tbody>
          </table>
        </>
      )}
    </section>
  );
}

export function AuditLog({ targetId }: { targetId?: string }) {
  const { session } = useAdmin();
  const q = useAsync(
    () => adminApi.get<{ id: number; action: string; target_type: string; target_id: string; reviewer: string; note: string | null; created_at: string }[]>(
      `/audit?limit=200${targetId ? `&target_id=${targetId}` : ""}`, session.token),
    [targetId],
  );
  return (
    <div className="table-wrap">
      <table className="data-table">
        <thead><tr><th scope="col">When</th><th scope="col">Who</th><th scope="col">Action</th><th scope="col">Target</th><th scope="col">Note</th></tr></thead>
        <tbody>
          {q.data?.map((e) => (
            <tr key={e.id}>
              <td className="subtle">{new Date(e.created_at).toLocaleString()}</td>
              <td>{e.reviewer}</td>
              <td>{e.action}</td>
              <td>{e.target_type} {e.target_id}</td>
              <td className="subtle">{e.note}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {q.data?.length === 0 && <p className="muted">No changes recorded yet.</p>}
    </div>
  );
}

function Tools() {
  const { session } = useAdmin();
  const { meta } = useMeta();
  const [msg, setMsg] = useState<string | null>(null);
  const [theme, setTheme] = useState({ code: "", label_en: "", label_ne: "", group: "social", definition: "" });
  const versions = useAsync(() => adminApi.get<{ id: number; version: string; is_active: boolean; themes: number; note: string | null }[]>("/taxonomy/versions", session.token), []);
  const run = async (fn: () => Promise<unknown>, ok: string) => {
    try {
      const r = await fn();
      setMsg(`${ok}${r && typeof r === "object" ? ` ${JSON.stringify(r).slice(0, 200)}` : ""}`);
    } catch (e) {
      setMsg((e as ApiError).message);
    }
  };
  return (
    <section className="stack">
      <h2>Tools</h2>
      {msg && <p className="notice" role="status">{msg}</p>}
      <PaintedFrame tone="peacock" ornate={false}>
        <h3>Export the dataset</h3>
        <p className="muted">Includes original fields, corrections, theme decisions and provenance.</p>
        <div className="row">
          <button className="btn btn-sm" onClick={() => run(() => adminApi.download("/export?format=csv", session.token, "nvl-corpus.csv"), "CSV downloaded.")}>CSV</button>
          <button className="btn btn-sm" onClick={() => run(() => adminApi.download("/export?format=json", session.token, "nvl-corpus.json"), "JSON downloaded.")}>JSON</button>
        </div>
      </PaintedFrame>
      <PaintedFrame tone="turmeric" ornate={false}>
        <h3>Re-import the processed corpus</h3>
        <p className="muted">Reloads data/processed/corpus.json. Entries edited by researchers are skipped.</p>
        <button className="btn btn-sm" onClick={() => run(() => adminApi.send("/import-corpus", session.token, "POST"), "Imported:")}>Re-import</button>
      </PaintedFrame>
      <PaintedFrame tone="rose" ornate={false}>
        <h3>Add a theme category</h3>
        <form
          className="grid-2"
          onSubmit={(e) => {
            e.preventDefault();
            run(() => adminApi.send("/themes", session.token, "POST", theme), "Theme added.");
          }}
        >
          <div className="field"><label htmlFor="tc">Code</label><input id="tc" type="text" placeholder="ROAD_SAFETY" value={theme.code} onChange={(e) => setTheme({ ...theme, code: e.target.value.toUpperCase() })} /></div>
          <div className="field"><label htmlFor="tg">Dimension</label>
            <select id="tg" value={theme.group} onChange={(e) => setTheme({ ...theme, group: e.target.value })}>
              {(meta?.dimensions ?? []).map((d) => <option key={d.key} value={d.key === "rhetoric" ? "rhetorical" : d.key}>{d.label_en}</option>)}
            </select>
          </div>
          <div className="field"><label htmlFor="te">English label</label><input id="te" type="text" value={theme.label_en} onChange={(e) => setTheme({ ...theme, label_en: e.target.value })} /></div>
          <div className="field"><label htmlFor="tn">Nepali label</label><input id="tn" type="text" lang="ne" value={theme.label_ne} onChange={(e) => setTheme({ ...theme, label_ne: e.target.value })} /></div>
          <div className="field"><label htmlFor="td">Definition</label><input id="td" type="text" value={theme.definition} onChange={(e) => setTheme({ ...theme, definition: e.target.value })} /></div>
          <div className="field"><span className="field-label">&nbsp;</span><button className="btn btn-sm">Add theme</button></div>
        </form>
      </PaintedFrame>
      <PaintedFrame tone="indigo" ornate={false}>
        <h3>Municipality directory</h3>
        <p className="muted">Upload a CSV from an authoritative source (MoFAGA or the OCHA/HDX administrative dataset) with columns: district, name_en, name_ne, kind.</p>
        <input
          type="file"
          accept=".csv,text/csv"
          aria-label="Municipality CSV"
          onChange={(e) => {
            const f = e.target.files?.[0];
            const source = window.prompt("Name the source of this file (e.g. 'MoFAGA 2024 local levels')");
            if (f && source) run(() => adminApi.upload(`/municipalities/import?source=${encodeURIComponent(source)}`, session.token, f), "Imported:");
          }}
        />
      </PaintedFrame>
      <PaintedFrame tone="vermilion" ornate={false}>
        <h3>Taxonomy versions</h3>
        <ul>
          {versions.data?.map((v) => (
            <li key={v.id}>
              v{v.version} — {v.themes} themes {v.is_active && <span className="tag">active</span>} <span className="subtle">{v.note}</span>
            </li>
          ))}
        </ul>
        <p className="subtle">New versions are proposed through the API (POST /api/admin/taxonomy/versions) and deployed by committing them to taxonomy/.</p>
      </PaintedFrame>
    </section>
  );
}

export default function AdminApp() {
  const [session, setSession] = useState<Session | null>(loadSession);
  const navigate = useNavigate();
  useEffect(() => {
    if (!session) return;
    const ms = new Date(session.expires_at).getTime() - Date.now();
    const t = window.setTimeout(() => setSession(null), Math.max(0, ms));
    return () => window.clearTimeout(t);
  }, [session]);
  const logout = () => {
    try {
      sessionStorage.removeItem(KEY);
    } catch {
      /* ignore */
    }
    setSession(null);
    navigate("/admin");
  };
  if (!session) return <Login onLogin={setSession} />;
  const tabs = [
    ["", "Review queue"],
    ["corpus", "Corpus"],
    ["submissions", "Submissions"],
    ["analytics", "Analytics"],
    ["audit", "Audit log"],
    ["tools", "Tools"],
  ];
  return (
    <AdminCtx.Provider value={{ session, logout }}>
      <div className="container page admin">
        <div className="row admin-head">
          <h1>Researcher area</h1>
          <span className="subtle">Signed in as {session.username}</span>
          <button className="btn btn-ghost btn-sm" onClick={logout}>Sign out</button>
        </div>
        <nav className="admin-tabs" aria-label="Researcher sections">
          {tabs.map(([to, label]) => (
            <NavLink key={to} end to={`/admin/${to}`} className={({ isActive }) => `chip ${isActive ? "is-on" : ""}`}>
              {label}
            </NavLink>
          ))}
        </nav>
        <Routes>
          <Route index element={<ReviewQueue />} />
          <Route path="corpus" element={<CorpusAdmin />} />
          <Route path="submissions" element={<Submissions />} />
          <Route path="analytics" element={<Analytics />} />
          <Route path="audit" element={<section><h2>Audit log</h2><AuditLog /></section>} />
          <Route path="tools" element={<Tools />} />
          <Route path="phrases/:id" element={<AdminPhrase />} />
        </Routes>
      </div>
    </AdminCtx.Provider>
  );
}

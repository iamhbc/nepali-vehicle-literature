import { useEffect, useId, useRef, useState, type FormEvent } from "react";
import { api } from "../api/client";
import type { Province, StageEvent, VehicleType } from "../api/types";
import { toNepaliDigits } from "../lib/format";

const KEYBOARD_ROWS = [
  ["अ", "आ", "इ", "ई", "उ", "ऊ", "ए", "ऐ", "ओ", "औ"],
  ["ा", "ि", "ी", "ु", "ू", "े", "ै", "ो", "ौ", "ं", "ँ", "्", "ः"],
  ["क", "ख", "ग", "घ", "ङ", "च", "छ", "ज", "झ", "ञ", "ट", "ठ", "ड", "ढ", "ण"],
  ["त", "थ", "द", "ध", "न", "प", "फ", "ब", "भ", "म", "य", "र", "ल", "व", "श", "ष", "स", "ह", "।"],
];

/** Minimal on-screen Devanagari helper for people without a Nepali keyboard. */
function DevanagariPad({ onInsert }: { onInsert: (ch: string) => void }) {
  return (
    <div className="deva-pad" role="group" aria-label="Devanagari letters">
      {KEYBOARD_ROWS.map((row, i) => (
        <div key={i} className="deva-row">
          {row.map((ch) => (
            <button key={ch} type="button" className="deva-key" lang="ne" onClick={() => onInsert(ch)} aria-label={`Insert ${ch}`}>
              {ch.length === 1 && "ािीुूेैोौंँ्ः".includes(ch) ? `◌${ch}` : ch}
            </button>
          ))}
        </div>
      ))}
    </div>
  );
}

export function PhraseInput({
  value,
  onChange,
  onSubmit,
  maxChars = 600,
  busy = false,
  autoFocus = false,
  submitLabel = "Analyse",
  secondary,
}: {
  value: string;
  onChange: (v: string) => void;
  onSubmit: () => void;
  maxChars?: number;
  busy?: boolean;
  autoFocus?: boolean;
  submitLabel?: string;
  secondary?: React.ReactNode;
}) {
  const id = useId();
  const ref = useRef<HTMLTextAreaElement>(null);
  const [pad, setPad] = useState(false);
  const over = value.length > maxChars;

  const insert = (ch: string) => {
    const el = ref.current;
    if (!el) return onChange(value + ch);
    const start = el.selectionStart ?? value.length;
    const end = el.selectionEnd ?? value.length;
    const next = value.slice(0, start) + ch + value.slice(end);
    onChange(next);
    requestAnimationFrame(() => {
      el.focus();
      el.setSelectionRange(start + ch.length, start + ch.length);
    });
  };

  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (value.trim() && !over && !busy) onSubmit();
  };

  return (
    <form className="phrase-input" onSubmit={submit}>
      <label htmlFor={id} className="visually-hidden">
        Nepali phrase to analyse
      </label>
      <textarea
        id={id}
        ref={ref}
        lang="ne"
        rows={3}
        value={value}
        autoFocus={autoFocus}
        placeholder="यहाँ नेपाली वाक्य लेख्नुहोस् … e.g. माया भनेको सम्झना रहेछ"
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) submit(e);
        }}
        aria-describedby={`${id}-count`}
        spellCheck={false}
      />
      {pad && <DevanagariPad onInsert={insert} />}
      <div className="phrase-input-bar">
        <span id={`${id}-count`} className={`subtle ${over ? "over" : ""}`} aria-live="polite">
          <span lang="ne">{toNepaliDigits(value.length)}</span> / {maxChars}
          {over && " — please shorten the phrase"}
        </span>
        <div className="row">
          <button type="button" className="btn btn-ghost btn-sm" onClick={() => setPad((p) => !p)} aria-expanded={pad}>
            <span lang="ne">क</span> {pad ? "Hide letters" : "Letters"}
          </button>
          {value && (
            <button type="button" className="btn btn-ghost btn-sm" onClick={() => onChange("")}>
              Clear
            </button>
          )}
        </div>
      </div>
      <div className="phrase-input-actions">
        <button type="submit" className="btn btn-primary" disabled={!value.trim() || over || busy}>
          {busy ? "Analysing…" : submitLabel}
        </button>
        {secondary}
      </div>
    </form>
  );
}

const STAGE_ORDER = ["normalize", "retrieve", "cues", "interpret", "verify", "map"];
const STAGE_TEXT: Record<string, string> = {
  normalize: "Reading the inscription",
  retrieve: "Searching the research corpus",
  cues: "Noting cultural and lexical cues",
  interpret: "Interpreting meaning and context",
  verify: "Checking every quote against the phrase",
  map: "Drawing the cultural map",
};

export function AnalysisProgress({ stages, engine }: { stages: StageEvent[]; engine: string }) {
  const done = new Set(stages.map((s) => s.stage));
  const order = engine === "llm" ? STAGE_ORDER : STAGE_ORDER.filter((s) => s !== "interpret");
  const current = order.find((s) => !done.has(s));
  return (
    <ol className="progress" aria-live="polite" aria-label="Analysis progress">
      {order.map((s) => (
        <li key={s} className={done.has(s) ? "is-done" : s === current ? "is-current" : ""}>
          <span className="progress-dot" aria-hidden="true" />
          {STAGE_TEXT[s]}
          {done.has(s) && <span className="visually-hidden"> — done</span>}
        </li>
      ))}
    </ol>
  );
}

export function VehicleSelector({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  const [items, setItems] = useState<VehicleType[]>([]);
  useEffect(() => {
    api.vehicles().then(setItems).catch(() => setItems([]));
  }, []);
  return (
    <div className="field">
      <span className="field-label" id="vehicle-label">
        Vehicle <span className="subtle">(optional)</span>
      </span>
      <div className="vehicle-chips" role="radiogroup" aria-labelledby="vehicle-label">
        {items.map((v) => (
          <button
            key={v.slug}
            type="button"
            role="radio"
            aria-checked={value === v.slug}
            className={`chip ${value === v.slug ? "is-on" : ""}`}
            onClick={() => onChange(value === v.slug ? "" : v.slug)}
          >
            {v.name_en} <span lang="ne">{v.name_ne}</span>
          </button>
        ))}
      </div>
    </div>
  );
}

export function LocationSelector({
  districtId,
  onChange,
}: {
  districtId: number | null;
  onChange: (v: { province_id: number | null; district_id: number | null }) => void;
}) {
  const [provinces, setProvinces] = useState<Province[]>([]);
  const [provinceId, setProvinceId] = useState<number | null>(null);
  useEffect(() => {
    api.locations().then(setProvinces).catch(() => setProvinces([]));
  }, []);
  const province = provinces.find((p) => p.id === provinceId);
  return (
    <div className="grid-2 location">
      <div className="field">
        <label htmlFor="province">
          Province <span className="subtle">(optional)</span>
        </label>
        <select
          id="province"
          value={provinceId ?? ""}
          onChange={(e) => {
            const id = e.target.value ? Number(e.target.value) : null;
            setProvinceId(id);
            onChange({ province_id: id, district_id: null });
          }}
        >
          <option value="">— Not specified —</option>
          {provinces.map((p) => (
            <option key={p.id} value={p.id}>
              {p.name_en} · {p.name_ne}
            </option>
          ))}
        </select>
      </div>
      <div className="field">
        <label htmlFor="district">District</label>
        <select
          id="district"
          value={districtId ?? ""}
          disabled={!province}
          onChange={(e) => onChange({ province_id: provinceId, district_id: e.target.value ? Number(e.target.value) : null })}
        >
          <option value="">{province ? "— Choose district —" : "Choose a province first"}</option>
          {province?.districts.map((d) => (
            <option key={d.id} value={d.id}>
              {d.name_en} · {d.name_ne}
            </option>
          ))}
        </select>
      </div>
    </div>
  );
}

export function SearchBar({ initial = "", onSearch, busy }: { initial?: string; onSearch: (q: string) => void; busy?: boolean }) {
  const [q, setQ] = useState(initial);
  useEffect(() => setQ(initial), [initial]);
  return (
    <form
      className="searchbar"
      role="search"
      onSubmit={(e) => {
        e.preventDefault();
        onSearch(q.trim());
      }}
    >
      <label htmlFor="corpus-search" className="visually-hidden">
        Search the corpus
      </label>
      <input
        id="corpus-search"
        type="search"
        value={q}
        onChange={(e) => setQ(e.target.value)}
        placeholder="Search in English or Nepali — e.g. migration and homesickness, आमा"
      />
      <button className="btn btn-teal" type="submit" disabled={busy}>
        Search
      </button>
    </form>
  );
}

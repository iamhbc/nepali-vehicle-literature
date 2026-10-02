import { useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ApiError, api } from "../api/client";
import type { OCRResponse } from "../api/types";
import { LocationSelector, VehicleSelector } from "../components/inputs";
import { useMeta } from "../components/Layout";
import { NumberPlate, PaintedFrame } from "../components/ornaments";
import { compressImage } from "../lib/image";
import { playShutter, setSoundEnabled, soundEnabled } from "../lib/sound";

type Phase = "idle" | "scanning" | "review" | "manual";

const SCAN_STEPS = ["Scanning vehicle literature", "Extracting Nepali text", "Checking against the corpus"];

export default function Scan() {
  const navigate = useNavigate();
  const { meta } = useMeta();
  const cameraInput = useRef<HTMLInputElement>(null);
  const uploadInput = useRef<HTMLInputElement>(null);
  const [phase, setPhase] = useState<Phase>("idle");
  const [preview, setPreview] = useState<string | null>(null);
  const [ocr, setOcr] = useState<OCRResponse | null>(null);
  const [text, setText] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [step, setStep] = useState(0);
  const [sound, setSound] = useState(soundEnabled());
  const [flash, setFlash] = useState(false);
  const [vehicle, setVehicle] = useState("");
  const [loc, setLoc] = useState<{ province_id: number | null; district_id: number | null }>({ province_id: null, district_id: null });
  const [contribute, setContribute] = useState(false);

  useEffect(() => () => {
    if (preview) URL.revokeObjectURL(preview);
  }, [preview]);

  useEffect(() => {
    if (phase !== "scanning") return;
    setStep(0);
    const t = window.setInterval(() => setStep((s) => Math.min(s + 1, SCAN_STEPS.length - 1)), 1400);
    return () => window.clearInterval(t);
  }, [phase]);

  const onFile = async (file: File | undefined) => {
    if (!file) return;
    setError(null);
    playShutter();
    setFlash(true);
    window.setTimeout(() => setFlash(false), 260);
    if (preview) URL.revokeObjectURL(preview);
    setPreview(URL.createObjectURL(file));
    setPhase("scanning");
    try {
      const blob = await compressImage(file);
      const res = await api.ocr(blob);
      setOcr(res);
      setText(res.text);
      setPhase("review");
      if (!res.text) setError("We couldn't confidently read the inscription. You can type it below.");
    } catch (e) {
      const err = e as ApiError;
      // When the server already said OCR is off, the page notice covers it.
      if (!(err.status === 503 && meta && !meta.ocr_available)) {
        setError(err.status === 503 ? err.message : `We couldn't confidently read the inscription. ${err.message ?? ""} You can type it below.`);
      }
      setPhase("manual");
    }
  };

  const analyze = () => {
    navigate("/analyze", {
      state: {
        input: {
          text,
          context: { vehicle_type: vehicle || null, ...loc },
          contribute,
          ocr_text: ocr?.text ?? null,
          ocr_provider: ocr?.provider ?? null,
        },
      },
    });
  };

  const reset = () => {
    setPhase("idle");
    setOcr(null);
    setText("");
    setError(null);
  };

  return (
    <div className="container page scan-page">
      <div className="row scan-head">
        <h1>
          Photograph a vehicle <span lang="ne" className="h-ne">गाडीको फोटो</span>
        </h1>
        <button
          className="btn btn-ghost btn-sm"
          aria-pressed={sound}
          onClick={() => {
            setSound(!sound);
            setSoundEnabled(!sound);
          }}
        >
          <span aria-hidden="true">{sound ? "🔊" : "🔇"}</span> Shutter sound {sound ? "on" : "off"}
        </button>
      </div>

      {meta && !meta.ocr_available && (
        <p className="notice notice-warn">
          Photo reading is not configured on this server yet. You can still type what the vehicle says and analyse it.
        </p>
      )}

      {(phase === "idle" || phase === "scanning") && (
        <PaintedFrame tone="turmeric" className={`camera ${flash ? "is-flash" : ""}`}>
          {phase === "scanning" && preview ? (
            <div className="scan-preview">
              <img src={preview} alt="Your photograph being read" />
              <div className="scanline" aria-hidden="true" />
              <p className="scan-status" role="status" aria-live="polite">
                {SCAN_STEPS[step]}…
              </p>
            </div>
          ) : (
            <div className="camera-empty">
              <div className="camera-icon" aria-hidden="true">
                <svg viewBox="0 0 64 48" width="88">
                  <rect x="2" y="10" width="60" height="36" rx="8" fill="var(--ink)" />
                  <path d="M20 10l5-8h14l5 8z" fill="var(--ink)" />
                  <circle cx="32" cy="28" r="12" fill="var(--turmeric)" stroke="var(--paper)" strokeWidth="3" />
                  <circle cx="32" cy="28" r="5" fill="var(--vermilion)" />
                  <rect x="48" y="15" width="8" height="4" rx="2" fill="var(--peacock)" />
                </svg>
              </div>
              <p className="camera-lead">Point at the painted words on a bus, truck, jeep or tempo.</p>
              <div className="camera-actions">
                <button className="btn btn-primary btn-big" onClick={() => cameraInput.current?.click()}>
                  Take photo
                </button>
                <button className="btn" onClick={() => uploadInput.current?.click()}>
                  Upload a photo
                </button>
                <button className="btn btn-ghost" onClick={() => setPhase("manual")}>
                  Type it instead
                </button>
              </div>
              <input ref={cameraInput} type="file" accept="image/*" capture="environment" hidden onChange={(e) => onFile(e.target.files?.[0])} />
              <input ref={uploadInput} type="file" accept="image/*" hidden onChange={(e) => onFile(e.target.files?.[0])} />
              <p className="subtle">
                Your photo is shrunk on your phone, its location data removed, read once, and never stored.{" "}
                <Link to="/method#privacy">Privacy</Link>
              </p>
            </div>
          )}
        </PaintedFrame>
      )}

      {error && (
        <p className="notice notice-warn" role="alert">
          {error}
        </p>
      )}

      {(phase === "review" || phase === "manual") && (
        <PaintedFrame tone="peacock" className="ocr-review" as="section" aria-labelledby="ocr-h">
          <h2 id="ocr-h" className="panel-title">
            {phase === "review" ? "Check the text we read" : "Type the inscription"}
          </h2>
          {ocr && phase === "review" && (
            <div className="row ocr-meta">
              <span className={`tag legibility-${ocr.legibility}`}>Legibility: {ocr.legibility}</span>
              {ocr.uncertain_segments.length > 0 && (
                <span className="subtle">
                  Unsure about: {ocr.uncertain_segments.map((s) => <q key={s} lang="ne">{s}</q>)}
                </span>
              )}
            </div>
          )}
          <div className="ocr-body">
            {preview && phase === "review" && <img className="ocr-thumb" src={preview} alt="Your photograph" />}
            <div className="field ocr-field">
              <label htmlFor="ocr-text">
                {phase === "review" ? "Correct anything we misread before analysing" : "What does the vehicle say?"}
              </label>
              <textarea id="ocr-text" lang="ne" rows={4} value={text} onChange={(e) => setText(e.target.value)} />
            </div>
          </div>
          {ocr?.suggestions.map((s) => (
            <div key={s.id} className="suggestion">
              <NumberPlate corpusId={s.corpus_id} size="sm" />
              <div>
                <p className="subtle">{s.reason}</p>
                <p lang="ne">{s.text}</p>
                <button className="btn btn-sm" onClick={() => setText(s.text)}>
                  Use this text
                </button>
              </div>
            </div>
          ))}
          {ocr && ocr.other_text.length > 0 && <p className="subtle">Also visible (ignored): {ocr.other_text.join(" · ")}</p>}

          <details className="context-details">
            <summary>Add where you saw it (optional)</summary>
            <VehicleSelector value={vehicle} onChange={setVehicle} />
            <LocationSelector districtId={loc.district_id} onChange={setLoc} />
          </details>
          <label className="checkbox">
            <input type="checkbox" checked={contribute} onChange={(e) => setContribute(e.target.checked)} />
            <span>
              Share this inscription's text with the researchers for the corpus. <span className="subtle">No photo or personal data is sent.</span>
            </span>
          </label>
          <div className="row">
            <button className="btn btn-primary" disabled={!text.trim()} onClick={analyze}>
              Analyse this text
            </button>
            <button className="btn btn-ghost" onClick={reset}>
              Take another photo
            </button>
          </div>
        </PaintedFrame>
      )}
    </div>
  );
}

import { useEffect, useRef, useState } from "react";

/**
 * A stylised Nepali goods truck: painted crown (visor) over the cab, झालर
 * fringe, decorated cargo body. The phrase on the body is real HTML text so
 * Devanagari shapes correctly and screen readers can reach it.
 */

function Wheel({ cx, cy = 214 }: { cx: number; cy?: number }) {
  return (
    <g>
      <circle cx={cx} cy={cy} r="27" fill="#16131f" />
      <g className="wheel-spin" style={{ transformOrigin: `${cx}px ${cy}px` }}>
        <circle cx={cx} cy={cy} r="15" fill="#c9ccd3" />
        {[0, 60, 120].map((a) => (
          <rect key={a} x={cx - 2} y={cy - 14} width="4" height="28" rx="1.5" fill="#6d7280" transform={`rotate(${a} ${cx} ${cy})`} />
        ))}
        <circle cx={cx} cy={cy} r="5" fill="var(--vermilion)" />
      </g>
    </g>
  );
}

export function TruckIllustration() {
  const fringe = Array.from({ length: 13 }, (_, i) => i);
  const colours = ["#e6b325", "#0d6767", "#d8452a", "#b42d62"];
  return (
    <svg viewBox="0 0 640 250" className="truck-svg" aria-hidden="true" focusable="false">
      {/* Cargo body */}
      <rect x="22" y="30" width="388" height="160" rx="6" fill="#0d6767" />
      <rect x="22" y="30" width="388" height="16" fill="#e6b325" />
      {Array.from({ length: 24 }, (_, i) => (
        <path key={i} d={`M${24 + i * 16} 46 q8 10 16 0`} fill="#d8452a" />
      ))}
      <rect x="34" y="58" width="364" height="112" rx="4" fill="#f4ecdb" stroke="#1c1633" strokeWidth="3" />
      <rect x="40" y="64" width="352" height="100" rx="2" fill="none" stroke="#b3301c" strokeWidth="2" strokeDasharray="10 5" />
      <rect x="22" y="176" width="388" height="14" fill="#24378a" />
      {Array.from({ length: 12 }, (_, i) => (
        <circle key={i} cx={38 + i * 32} cy="183" r="3.5" fill="#e6b325" />
      ))}
      {/* Cab */}
      <path d="M414 72 h96 q26 0 40 26 l38 52 q8 10 8 24 v26 h-182 z" fill="#b3301c" />
      <path d="M432 86 h70 q16 0 26 16 l26 40 h-122 z" fill="#bfe3ea" stroke="#1c1633" strokeWidth="3" />
      <path d="M432 86 l40 0 l-30 56 h-10z" fill="#ffffff" opacity="0.45" />
      <rect x="430" y="152" width="70" height="40" rx="4" fill="none" stroke="#1c1633" strokeWidth="2.5" />
      <rect x="484" y="166" width="12" height="4" rx="2" fill="#1c1633" />
      {/* Crown (visor) above the cab */}
      <path d="M408 70 q20 -46 80 -50 q54 2 76 50 z" fill="#e6b325" stroke="#1c1633" strokeWidth="3" />
      <path d="M426 64 q14 -30 62 -34 q40 2 58 34 z" fill="#24378a" />
      <circle cx="487" cy="46" r="10" fill="#d8452a" />
      <circle cx="487" cy="46" r="4" fill="#f4ecdb" />
      <circle cx="452" cy="58" r="5" fill="#b42d62" />
      <circle cx="522" cy="58" r="5" fill="#b42d62" />
      {/* झालर fringe under the crown */}
      {fringe.map((i) => (
        <g key={i}>
          <path d={`M${414 + i * 11} 70 l5.5 12 l5.5 -12z`} fill={colours[i % 4]} />
          <circle cx={419.5 + i * 11} cy="85" r="2" fill={colours[(i + 2) % 4]} />
        </g>
      ))}
      {/* Bumper, chevrons, lamp */}
      <rect x="560" y="196" width="44" height="14" rx="3" fill="#c9ccd3" stroke="#1c1633" strokeWidth="2" />
      <rect x="586" y="160" width="14" height="12" rx="3" fill="#ffe7a0" className="headlamp" />
      <rect x="22" y="190" width="70" height="12" fill="url(#chev)" />
      <defs>
        <pattern id="chev" width="16" height="12" patternUnits="userSpaceOnUse">
          <rect width="16" height="12" fill="#f4ecdb" />
          <path d="M0 12 L8 0 H16 L8 12z" fill="#b3301c" />
        </pattern>
      </defs>
      <rect x="400" y="190" width="200" height="10" fill="#1c1633" />
      <Wheel cx={92} />
      <Wheel cx={160} />
      <Wheel cx={512} />
    </svg>
  );
}

export function TruckAnimation({ phrases }: { phrases: { text: string; corpus_id?: string }[] }) {
  const [i, setI] = useState(0);
  const [visible, setVisible] = useState(true);
  const ref = useRef<HTMLDivElement>(null);
  const reduced = typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;

  useEffect(() => {
    const el = ref.current;
    if (!el || typeof IntersectionObserver === "undefined") return;
    const io = new IntersectionObserver(([entry]) => setVisible(entry.isIntersecting), { threshold: 0.1 });
    io.observe(el);
    const onVis = () => setVisible(!document.hidden && el.getBoundingClientRect().bottom > 0);
    document.addEventListener("visibilitychange", onVis);
    return () => {
      io.disconnect();
      document.removeEventListener("visibilitychange", onVis);
    };
  }, []);

  useEffect(() => {
    if (reduced || !visible || phrases.length < 2) return;
    const t = window.setInterval(() => setI((n) => (n + 1) % phrases.length), 6000);
    return () => window.clearInterval(t);
  }, [reduced, visible, phrases.length]);

  const current = phrases[i % Math.max(phrases.length, 1)];
  return (
    <div ref={ref} className={`truck-scene ${visible && !reduced ? "is-moving" : "is-paused"}`}>
      <div className="truck-dust" aria-hidden="true">
        <span />
        <span />
        <span />
      </div>
      <div className="truck">
        <TruckIllustration />
        <div className="truck-panel" aria-live="off">
          {current && (
            <p key={i} className="truck-phrase" lang="ne">
              {current.text}
            </p>
          )}
        </div>
      </div>
      <div className="truck-road" aria-hidden="true" />
    </div>
  );
}

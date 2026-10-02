import { useId, type CSSProperties, type ReactNode } from "react";
import { plateParts } from "../lib/format";

/**
 * Decorative vocabulary drawn from painted vehicles. All ornaments are
 * aria-hidden: they carry no information that is not also in the text.
 */

const JHALAR_COLOURS = ["var(--vermilion)", "var(--turmeric)", "var(--peacock)", "var(--rose)", "var(--marigold)", "var(--indigo)"];

/** झालर — the bead-and-pennant fringe hung from vehicle visors and bumpers. */
export function Jhalar({ height = 22, className = "" }: { height?: number; className?: string }) {
  const id = useId().replace(/:/g, "");
  const unit = 18;
  const span = unit * JHALAR_COLOURS.length;
  return (
    <svg className={`jhalar ${className}`} width="100%" height={height} aria-hidden="true" focusable="false">
      <defs>
        <pattern id={`j${id}`} width={span} height={height} patternUnits="userSpaceOnUse">
          <rect width={span} height="3" fill="var(--ink)" />
          {JHALAR_COLOURS.map((c, i) => {
            const x = i * unit;
            return (
              <g key={i}>
                <path d={`M${x + 1} 3 L${x + unit - 1} 3 L${x + unit / 2} ${height - 8} Z`} fill={c} />
                <circle cx={x + unit / 2} cy={height - 4} r="2.6" fill={JHALAR_COLOURS[(i + 2) % JHALAR_COLOURS.length]} />
              </g>
            );
          })}
        </pattern>
      </defs>
      <rect width="100%" height={height} fill={`url(#j${id})`} />
    </svg>
  );
}

/** Eight-petal rosette, the flower painted in panel corners. */
export function Rosette({ size = 26, colour = "var(--vermilion)", className = "" }: { size?: number; colour?: string; className?: string }) {
  return (
    <svg className={className} width={size} height={size} viewBox="-12 -12 24 24" aria-hidden="true" focusable="false">
      {Array.from({ length: 8 }, (_, i) => (
        <ellipse key={i} rx="2.6" ry="7" cy="-4.6" fill={i % 2 ? "var(--turmeric)" : colour} transform={`rotate(${i * 45})`} />
      ))}
      <circle r="3.2" fill="var(--peacock)" />
      <circle r="1.3" fill="var(--paper)" />
    </svg>
  );
}

/** A painted signboard panel: double border, corner rosettes. */
export function PaintedFrame({
  children,
  tone = "vermilion",
  className = "",
  as: Tag = "div",
  ornate = true,
  style,
  ...rest
}: {
  children: ReactNode;
  tone?: "vermilion" | "peacock" | "indigo" | "rose" | "turmeric";
  className?: string;
  as?: "div" | "section" | "article" | "aside";
  ornate?: boolean;
  style?: CSSProperties;
} & Record<string, unknown>) {
  return (
    <Tag className={`painted-frame tone-${tone} ${className}`} style={style} {...rest}>
      {ornate && (
        <>
          <Rosette className="corner tl" size={22} />
          <Rosette className="corner tr" size={22} />
          <Rosette className="corner bl" size={22} />
          <Rosette className="corner br" size={22} />
        </>
      )}
      {children}
    </Tag>
  );
}

/** Corpus ids as Nepali public-vehicle plates (black plate, white Devanagari). */
export function NumberPlate({ corpusId, size = "md" }: { corpusId: string; size?: "sm" | "md" }) {
  const { prefix, number } = plateParts(corpusId);
  return (
    <span className={`plate plate-${size}`} aria-label={`Corpus entry ${corpusId}`} title={corpusId}>
      <span className="plate-rivet" aria-hidden="true" />
      <span className="plate-prefix" aria-hidden="true">{prefix}</span>
      <span className="plate-number" aria-hidden="true" lang="ne">{number}</span>
      <span className="plate-rivet" aria-hidden="true" />
    </span>
  );
}

/** Centre-line road marking used as a section divider. */
export function RoadDivider({ label }: { label?: string }) {
  return (
    <div className="road" role={label ? "separator" : undefined} aria-label={label} aria-hidden={label ? undefined : true}>
      <span className="road-line" />
    </div>
  );
}

/** Diagonal hazard chevrons from bumpers and tailboards. */
export function ChevronBand({ className = "" }: { className?: string }) {
  return <div className={`chevrons ${className}`} aria-hidden="true" />;
}

export function Wordmark({ compact = false }: { compact?: boolean }) {
  return (
    <span className={`wordmark ${compact ? "wordmark-compact" : ""}`}>
      <span className="wordmark-ne" lang="ne">सवारी साहित्य</span>
      {!compact && <span className="wordmark-en">Nepali Vehicle Literature</span>}
    </span>
  );
}

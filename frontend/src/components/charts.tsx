import { forceCenter, forceCollide, forceLink, forceManyBody, forceSimulation, type SimulationNodeDatum } from "d3-force";
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { dimColor } from "../lib/format";

export interface BarDatum {
  key: string;
  label: string;
  sublabel?: string;
  value: number;
  colour?: string;
  href?: string;
}

/** Horizontal bars: readable on phones, labels never rotate, values printed. */
export function BarList({ data, caption, unit = "inscriptions" }: { data: BarDatum[]; caption: string; unit?: string }) {
  const max = Math.max(1, ...data.map((d) => d.value));
  if (!data.length) return <p className="muted">No data recorded yet.</p>;
  return (
    <figure className="barlist">
      <figcaption className="visually-hidden">{caption}</figcaption>
      <ul>
        {data.map((d) => {
          const label = (
            <>
              <span className="bar-label">{d.label}</span>
              {d.sublabel && (
                <span className="bar-sub" lang="ne">
                  {d.sublabel}
                </span>
              )}
            </>
          );
          return (
            <li key={d.key} className="bar-row">
              <div className="bar-text">{d.href ? <Link to={d.href}>{label}</Link> : label}</div>
              <div className="bar-track" aria-hidden="true">
                <span className="bar-fill" style={{ width: `${(d.value / max) * 100}%`, background: d.colour ?? "var(--vermilion)" }} />
              </div>
              <span className="bar-value">
                {d.value}
                <span className="visually-hidden"> {unit}</span>
              </span>
            </li>
          );
        })}
      </ul>
    </figure>
  );
}

interface NetNode extends SimulationNodeDatum {
  id: string;
  label: string;
  group: string;
  count: number;
}

export function CooccurrenceNetwork({
  nodes,
  links,
  minCount = 2,
}: {
  nodes: { code: string; label_en: string; group: string; count: number }[];
  links: { source: string; target: string; count: number }[];
  minCount?: number;
}) {
  const [focus, setFocus] = useState<string | null>(null);
  const [showTable, setShowTable] = useState(false);
  const layout = useMemo(() => {
    const kept = links.filter((l) => l.count >= minCount);
    const used = new Set(kept.flatMap((l) => [l.source, l.target]));
    const simNodes: NetNode[] = nodes.filter((n) => used.has(n.code)).map((n) => ({ id: n.code, label: n.label_en, group: n.group, count: n.count }));
    const simLinks = kept.map((l) => ({ ...l }));
    const sim = forceSimulation(simNodes)
      .force("link", forceLink(simLinks).id((d) => (d as NetNode).id).distance(170).strength((l) => Math.min(0.6, (l as { count: number }).count / 6)))
      .force("charge", forceManyBody().strength(-1100))
      // Collide on label width too, so names don't overprint.
      .force("collide", forceCollide<NetNode>().radius((d) => Math.max(18 + Math.sqrt(d.count) * 3, d.label.length * 4.2) + 8).iterations(3))
      .force("center", forceCenter(0, 0))
      .stop();
    for (let i = 0; i < 300; i++) sim.tick();
    const xs = simNodes.map((n) => n.x ?? 0);
    const ys = simNodes.map((n) => n.y ?? 0);
    const pad = 90;
    const box = [Math.min(...xs) - pad, Math.min(...ys) - pad, Math.max(...xs) - Math.min(...xs) + pad * 2, Math.max(...ys) - Math.min(...ys) + pad * 2];
    return { simNodes, kept, box };
  }, [nodes, links, minCount]);

  const pos = new Map(layout.simNodes.map((n) => [n.id, n]));
  const connected = (id: string) => new Set([id, ...layout.kept.filter((l) => l.source === id || l.target === id).flatMap((l) => [l.source, l.target])]);
  const near = focus ? connected(focus) : null;
  const colourOf = (g: string) => dimColor(g === "rhetorical" ? "rhetoric" : g);

  return (
    <figure className="network">
      <svg viewBox={layout.box.join(" ")} role="img" aria-label={`Network of themes that appear together in at least ${minCount} inscriptions`}>
        {layout.kept.map((l) => {
          const a = pos.get(l.source as string);
          const b = pos.get(l.target as string);
          if (!a || !b) return null;
          const on = !near || (near.has(a.id) && near.has(b.id) && (a.id === focus || b.id === focus));
          return (
            <line key={`${l.source}-${l.target}`} x1={a.x} y1={a.y} x2={b.x} y2={b.y} className={`net-link ${on ? "" : "is-dim"}`} strokeWidth={1 + l.count * 1.2} />
          );
        })}
        {layout.simNodes.map((n) => (
          <g
            key={n.id}
            transform={`translate(${n.x},${n.y})`}
            className={`net-node ${near && !near.has(n.id) ? "is-dim" : ""}`}
            tabIndex={0}
            role="button"
            aria-label={`${n.label}: ${n.count} inscriptions`}
            onMouseEnter={() => setFocus(n.id)}
            onMouseLeave={() => setFocus(null)}
            onFocus={() => setFocus(n.id)}
            onBlur={() => setFocus(null)}
          >
            <circle r={8 + Math.sqrt(n.count) * 3} fill={colourOf(n.group)} />
            <text dy={-(12 + Math.sqrt(n.count) * 3)} textAnchor="middle">
              {n.label}
            </text>
          </g>
        ))}
      </svg>
      <figcaption className="row">
        <span className="subtle">Lines join themes coded together in at least {minCount} inscriptions; thicker means more often.</span>
        <button className="btn btn-ghost btn-sm" onClick={() => setShowTable((s) => !s)} aria-expanded={showTable}>
          {showTable ? "Hide table" : "Show as table"}
        </button>
      </figcaption>
      {showTable && (
        <table className="data-table">
          <thead>
            <tr>
              <th scope="col">Theme</th>
              <th scope="col">Theme</th>
              <th scope="col">Inscriptions with both</th>
            </tr>
          </thead>
          <tbody>
            {layout.kept.map((l) => (
              <tr key={`${l.source}-${l.target}`}>
                <td>{pos.get(l.source as string)?.label}</td>
                <td>{pos.get(l.target as string)?.label}</td>
                <td>{l.count}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </figure>
  );
}

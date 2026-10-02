import { useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import type { Graph, GraphNode, Reference } from "../api/types";
import { DIMENSION_LABELS, dimColor } from "../lib/format";
import { ConfidenceIndicator, KindBadge } from "./analysis-ui";

interface TreeDatum {
  node: GraphNode;
  children: TreeDatum[];
}

function toTree(graph: Graph): TreeDatum | null {
  const byId = new Map(graph.nodes.map((n) => [n.id, { node: n, children: [] as TreeDatum[] }]));
  for (const e of graph.edges) {
    const parent = byId.get(e.source);
    const child = byId.get(e.target);
    if (parent && child) parent.children.push(child);
  }
  return byId.get("root") ?? null;
}

const truncate = (s: string, n: number) => (s.length > n ? s.slice(0, n - 1) + "…" : s);

function polar(angle: number, radius: number): [number, number] {
  return [radius * Math.cos(angle - Math.PI / 2), radius * Math.sin(angle - Math.PI / 2)];
}

function useWide(ref: React.RefObject<HTMLElement | null>, threshold = 680) {
  const [wide, setWide] = useState(true);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const update = () => setWide(el.clientWidth >= threshold);
    update();
    if (typeof ResizeObserver === "undefined") return;
    const ro = new ResizeObserver(update);
    ro.observe(el);
    return () => ro.disconnect();
  }, [ref, threshold]);
  return wide;
}

interface Point {
  node: GraphNode;
  depth: number;
  angle: number;
  radius: number;
  x: number;
  y: number;
}

/**
 * Dimensions are spaced evenly around the phrase (staggered when crowded);
 * findings fan out inside their dimension's sector. Deterministic, no physics.
 */
function radialLayout(root: TreeDatum) {
  const dims = root.children;
  const n = Math.max(dims.length, 1);
  const sector = (2 * Math.PI) / n;
  const r1 = n > 8 ? 225 : 190;
  const r2 = n > 8 ? 400 : 360;
  const points: Point[] = [];
  const links: { source: Point; target: Point }[] = [];
  const mk = (node: GraphNode, depth: number, angle: number, radius: number): Point => {
    const [x, y] = polar(angle, radius);
    const p = { node, depth, angle, radius, x, y };
    points.push(p);
    return p;
  };
  const center = mk(root.node, 0, 0, 0);
  dims.forEach((dim, i) => {
    const a = i * sector;
    const stagger = n > 8 && i % 2 ? 62 : 0;
    const dp = mk(dim.node, 1, a, r1 + stagger);
    links.push({ source: center, target: dp });
    const count = dim.children.length;
    const step = Math.min(sector / Math.max(count, 1), 0.2);
    dim.children.forEach((leaf, j) => {
      const la = a + (j - (count - 1) / 2) * step;
      const lp = mk(leaf.node, 2, la, r2 + stagger * 0.5);
      links.push({ source: dp, target: lp });
    });
  });
  const pad = 240;
  const half = r2 + pad;
  return { points, links, viewBox: `${-half} ${-(r2 + 70)} ${half * 2} ${(r2 + 70) * 2}` };
}

function NodeDetail({ node, references, onClose }: { node: GraphNode; references: Reference[]; onClose: () => void }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    // When the panel sits below the map (narrow screens), bring it into view.
    const el = ref.current;
    if (!el || typeof el.scrollIntoView !== "function") return;
    const r = el.getBoundingClientRect();
    if (r.top > window.innerHeight - 120 || r.bottom < 0) el.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }, [node.id]);
  const d = node.detail as Record<string, any>;
  const dim = node.dimension ? DIMENSION_LABELS[node.dimension] : null;
  const refs = references.filter((r) => r.matched_topics.some((t) => t.toLowerCase() === node.label.toLowerCase() || t === d.code));
  return (
    <div ref={ref} className="node-detail" style={{ ["--dim" as string]: dimColor(node.dimension), scrollMarginBottom: 96 }} aria-live="polite">
      <div className="node-detail-head">
        <div>
          {dim && (
            <span className="eyebrow" style={{ color: "var(--dim)" }}>
              {dim.en} · <span lang="ne">{dim.ne}</span>
            </span>
          )}
          <h3>{node.type === "root" ? "The phrase" : node.label}</h3>
        </div>
        <button className="btn btn-ghost btn-sm" onClick={onClose} aria-label="Close details">
          ✕
        </button>
      </div>
      {(node.kind || node.confidence) && (
        <div className="row">
          {node.kind && <KindBadge kind={node.kind} />}
          {node.confidence && <ConfidenceIndicator value={node.confidence} />}
        </div>
      )}
      {node.type === "root" && (
        <>
          <p lang="ne" className="ne">
            {node.label}
          </p>
          {d.translation && <p className="muted">{d.translation}</p>}
        </>
      )}
      {d.summary && <p>{d.summary}</p>}
      {d.explanation && <p>{d.explanation}</p>}
      {d.definition && <p className="muted">Codebook: {d.definition}</p>}
      {d.rationale && <p className="subtle">Why: {d.rationale}</p>}
      {d.gloss && (
        <p>
          <span className="translit">{d.translit}</span> — {d.gloss}
        </p>
      )}
      {Array.isArray(d.evidence) && d.evidence.length > 0 && (
        <p className="finding-evidence">
          <span className="subtle">Evidence: </span>
          {d.evidence.map((q: string, i: number) => (
            <q key={i} lang="ne">
              {q}
            </q>
          ))}
        </p>
      )}
      {node.type === "related" && (
        <>
          <p lang="ne" className="ne">
            {d.text}
          </p>
          {d.translation && <p className="muted">{d.translation}</p>}
          {Array.isArray(d.reasons) && <p className="subtle">{d.reasons.join(" · ")}</p>}
          <Link to={`/corpus/${d.id}`}>Open corpus entry →</Link>
        </>
      )}
      {refs.length > 0 && (
        <div className="subtle">
          <strong>References:</strong> {refs.map((r) => `${r.authors.split(",")[0]} (${r.year})`).join("; ")}
        </div>
      )}
    </div>
  );
}

function Outline({ root, onSelect, selected }: { root: TreeDatum; onSelect: (n: GraphNode) => void; selected: string | null }) {
  return (
    <ul className="outline" aria-label="Cultural map as a list">
      {root.children.map((dim) => (
        <li key={dim.node.id} className="outline-branch" style={{ ["--dim" as string]: dimColor(dim.node.dimension) }}>
          <button
            className={`outline-dim ${selected === dim.node.id ? "is-selected" : ""}`}
            onClick={() => onSelect(dim.node)}
            aria-pressed={selected === dim.node.id}
          >
            <span>{dim.node.label}</span>
            {dim.node.label_ne && (
              <span lang="ne" className="outline-ne">
                {dim.node.label_ne}
              </span>
            )}
          </button>
          <ul className="outline-leaves">
            {dim.children.map((leaf) => (
              <li key={leaf.node.id}>
                <button
                  className={`outline-leaf conf-${leaf.node.confidence ?? "none"} ${selected === leaf.node.id ? "is-selected" : ""}`}
                  onClick={() => onSelect(leaf.node)}
                  aria-pressed={selected === leaf.node.id}
                  lang={leaf.node.type === "concept" ? "ne" : undefined}
                >
                  {leaf.node.type === "related" ? `${leaf.node.label} · ${truncate(leaf.node.label_ne ?? "", 24)}` : truncate(leaf.node.label, 48)}
                  {leaf.node.confidence && <span className="visually-hidden">, confidence {leaf.node.confidence}</span>}
                </button>
              </li>
            ))}
          </ul>
        </li>
      ))}
    </ul>
  );
}

export function MindMap({
  graph,
  references = [],
  onSelect,
}: {
  graph: Graph;
  references?: Reference[];
  onSelect?: (node: GraphNode | null) => void;
}) {
  const wrapRef = useRef<HTMLDivElement>(null);
  const wide = useWide(wrapRef);
  const [view, setView] = useState<"map" | "outline" | null>(null);
  const [selected, setSelected] = useState<GraphNode | null>(null);
  const [hover, setHover] = useState<string | null>(null);
  const root = useMemo(() => toTree(graph), [graph]);
  const mode = view ?? (wide ? "map" : "outline");

  const layout = useMemo(() => (root ? radialLayout(root) : null), [root]);

  const select = (n: GraphNode | null) => {
    setSelected(n);
    onSelect?.(n);
  };

  if (!root || !layout) return null;
  const parentOf = new Map(layout.links.map((l) => [l.target.node.id, l.source.node.id]));
  const pathOf = (id: string): Set<string> => {
    const out = new Set([id]);
    let cur = parentOf.get(id);
    while (cur) {
      out.add(cur);
      cur = parentOf.get(cur);
    }
    return out;
  };
  const activePath = hover ? pathOf(hover) : null;

  return (
    <div className="mindmap" ref={wrapRef}>
      <div className="mindmap-toolbar row" role="group" aria-label="Map view">
        <button className={`seg ${mode === "map" ? "is-on" : ""}`} aria-pressed={mode === "map"} onClick={() => setView("map")}>
          Map
        </button>
        <button className={`seg ${mode === "outline" ? "is-on" : ""}`} aria-pressed={mode === "outline"} onClick={() => setView("outline")}>
          Branches
        </button>
        <span className="subtle">Select any node to see its evidence and confidence.</span>
      </div>
      <div className={`mindmap-body ${selected ? "has-detail" : ""}`}>
        {mode === "map" ? (
          <svg viewBox={layout.viewBox} className="mindmap-svg" role="group" aria-label="Interactive cultural map of the phrase">
            <g>
              {layout.links.map((l) => {
                const { x: x1, y: y1 } = l.source;
                const { x: x2, y: y2 } = l.target;
                const [c1x, c1y] = polar(l.source.angle, (l.source.radius + l.target.radius) / 2);
                const [c2x, c2y] = polar(l.target.angle, (l.source.radius + l.target.radius) / 2);
                const node = l.target.node;
                const on = activePath?.has(node.id);
                return (
                  <path
                    key={node.id}
                    d={l.source.depth === 0 ? `M${x1},${y1}L${x2},${y2}` : `M${x1},${y1}C${c1x},${c1y} ${c2x},${c2y} ${x2},${y2}`}
                    className={`mm-link ${activePath && !on ? "is-dim" : ""}`}
                    stroke={dimColor(node.dimension)}
                    strokeWidth={node.confidence === "high" ? 3.5 : node.confidence === "low" ? 1.5 : 2.5}
                    strokeDasharray={node.kind === "hypothesis" ? "5 5" : undefined}
                  />
                );
              })}
            </g>
            {layout.points.map((n) => {
              const { node, x, y } = n;
              const isSel = selected?.id === node.id;
              const faded = activePath && !activePath.has(node.id);
              const common = {
                tabIndex: 0,
                role: "button",
                "aria-label": `${node.type === "root" ? "Phrase" : node.label}${node.confidence ? `, ${node.confidence} confidence` : ""}${node.kind ? `, ${node.kind}` : ""}`,
                "aria-pressed": isSel,
                onClick: () => select(isSel ? null : node),
                onKeyDown: (e: React.KeyboardEvent) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    select(isSel ? null : node);
                  }
                },
                onMouseEnter: () => setHover(node.id),
                onMouseLeave: () => setHover(null),
                onFocus: () => setHover(node.id),
                onBlur: () => setHover(null),
                className: `mm-node mm-${node.type} ${isSel ? "is-selected" : ""} ${faded ? "is-dim" : ""}`,
                style: { ["--dim" as string]: dimColor(node.dimension) },
              };
              if (n.depth === 0) {
                return (
                  <g key={node.id} transform={`translate(${x},${y})`} {...common}>
                    <circle r="74" className="mm-root-ring" />
                    <circle r="64" className="mm-root-disc" />
                    <text className="mm-root-text" textAnchor="middle" dy="-6" lang="ne">
                      {truncate(node.label, 14)}
                    </text>
                    <text className="mm-root-sub" textAnchor="middle" dy="20">
                      the phrase
                    </text>
                  </g>
                );
              }
              if (n.depth === 1) {
                const w = Math.max(96, node.label.length * 10 + 30);
                return (
                  <g key={node.id} transform={`translate(${x},${y})`} {...common}>
                    <rect x={-w / 2} y="-21" width={w} height="42" rx="8" className="mm-dim-box" />
                    <text textAnchor="middle" dy="6" className="mm-dim-text">
                      {node.label}
                    </text>
                  </g>
                );
              }
              const right = Math.cos(n.angle - Math.PI / 2) >= 0;
              const label = node.type === "related" ? node.label : truncate(node.label, 26);
              return (
                <g key={node.id} transform={`translate(${x},${y})`} {...common}>
                  <circle r={node.confidence === "high" ? 8 : node.confidence === "low" ? 5 : 6.5} className="mm-leaf-dot" />
                  <text x={right ? 13 : -13} dy="4.5" textAnchor={right ? "start" : "end"} className="mm-leaf-text" lang={node.type === "concept" ? "ne" : undefined}>
                    {label}
                  </text>
                </g>
              );
            })}
          </svg>
        ) : (
          <Outline root={root} onSelect={(n) => select(selected?.id === n.id ? null : n)} selected={selected?.id ?? null} />
        )}
        {selected && <NodeDetail node={selected} references={references} onClose={() => select(null)} />}
      </div>
      <p className="mindmap-legend subtle">
        Line weight shows confidence · dashed lines are hypotheses · colours mark dimensions.
      </p>
    </div>
  );
}

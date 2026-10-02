"""Build the semantic/cultural map (phrase → dimensions → findings) from an analysis."""

from __future__ import annotations

from ..knowledge import get_knowledge
from .schema import AnalysisPayload, Finding, Graph, GraphEdge, GraphNode, RelatedEntry

_WEIGHT = {"high": 1.0, "medium": 0.66, "low": 0.33}

DIMENSION_ORDER = [
    ("emotion", "Emotion", "भावना"),
    ("love", "Love", "माया"),
    ("relationship", "Relationship", "सम्बन्ध"),
    ("social", "Social", "समाज"),
    ("economic", "Economic", "अर्थ"),
    ("political", "Political", "राजनीति"),
    ("gender_power", "Gender & Power", "लैङ्गिकता र शक्ति"),
    ("cultural", "Cultural", "संस्कृति"),
    ("philosophical", "Philosophical", "दर्शन"),
    ("rhetoric", "Rhetoric & Humour", "शैली र हास्य"),
]


def _findings(p: AnalysisPayload) -> dict[str, tuple[str, list[Finding]]]:
    return {
        "emotion": (p.emotion.summary, p.emotion.findings),
        "love": (p.love.summary, p.love.findings),
        "relationship": (p.relationships.summary, p.relationships.findings),
        "social": (p.social.summary, p.social.findings),
        "economic": (p.economic.summary, p.economic.findings),
        "political": (p.political.summary, p.political.findings),
        "gender_power": (p.gender_power.summary, p.gender_power.findings),
        "cultural": (p.cultural.summary, p.cultural.findings),
        "philosophical": (p.philosophical.summary, p.philosophical.findings),
        "rhetoric": (p.rhetoric.summary, p.rhetoric.findings),
    }


def build_graph(phrase: str, payload: AnalysisPayload, related: list[RelatedEntry] | None = None,
                concepts: list[dict] | None = None, max_findings: int = 6) -> Graph:
    kb = get_knowledge()
    nodes = [GraphNode(id="root", label=phrase, type="root", detail={"translation": payload.contextual_translation})]
    edges: list[GraphEdge] = []
    by_dim = _findings(payload)

    for key, label_en, label_ne in DIMENSION_ORDER:
        summary, findings = by_dim[key]
        if not findings:
            continue
        dim_id = f"dim:{key}"
        nodes.append(GraphNode(id=dim_id, label=label_en, label_ne=label_ne, type="dimension", dimension=key,
                               detail={"summary": summary, "count": len(findings)}))
        edges.append(GraphEdge(source="root", target=dim_id, weight=1.0))
        ranked = sorted(findings, key=lambda f: -_WEIGHT[f.confidence])[:max_findings]
        for i, f in enumerate(ranked):
            fid = f"{dim_id}:{i}"
            nodes.append(GraphNode(
                id=fid, label=f.label, type="finding", dimension=key, confidence=f.confidence, kind=f.kind,
                detail={"explanation": f.explanation, "evidence": f.evidence, **{
                    k: v for k, v in f.model_dump().items()
                    if k in ("family", "intensity", "love_type", "parties", "power_relation")
                }},
            ))
            edges.append(GraphEdge(source=dim_id, target=fid, weight=_WEIGHT[f.confidence]))

    if payload.themes:
        nodes.append(GraphNode(id="dim:themes", label="Codebook themes", label_ne="विषय", type="dimension", dimension="themes",
                               detail={"summary": "Theme codes from the research codebook."}))
        edges.append(GraphEdge(source="root", target="dim:themes"))
        for t in payload.themes:
            theme = kb.themes.get(t.code, {})
            tid = f"theme:{t.code}"
            nodes.append(GraphNode(id=tid, label=theme.get("label_en", t.code), label_ne=theme.get("label_ne"), type="theme",
                                   dimension="themes", confidence=t.confidence,
                                   detail={"code": t.code, "definition": theme.get("definition"), "rationale": t.rationale}))
            edges.append(GraphEdge(source="dim:themes", target=tid, weight=_WEIGHT[t.confidence]))

    if concepts:
        nodes.append(GraphNode(id="dim:concepts", label="Cultural concepts", label_ne="सांस्कृतिक अवधारणा", type="dimension",
                               dimension="concepts", detail={"summary": "Culturally specific words with no exact English equivalent."}))
        edges.append(GraphEdge(source="root", target="dim:concepts"))
        for c in concepts:
            cid = f"concept:{c['slug']}"
            nodes.append(GraphNode(id=cid, label=c["term"], label_ne=c["term"], type="concept", dimension="concepts",
                                   detail={"gloss": c["gloss"], "explanation": c["explanation"], "translit": c["translit"]}))
            edges.append(GraphEdge(source="dim:concepts", target=cid))

    if related:
        nodes.append(GraphNode(id="dim:related", label="Related expressions", label_ne="सम्बन्धित अभिव्यक्ति", type="dimension",
                               dimension="related", detail={"summary": "Similar entries in the research corpus."}))
        edges.append(GraphEdge(source="root", target="dim:related"))
        for r in related[:4]:
            rid = f"related:{r.id}"
            nodes.append(GraphNode(id=rid, label=r.corpus_id, label_ne=r.text[:40], type="related", dimension="related",
                                   detail={"text": r.text, "translation": r.translation, "score": r.score, "reasons": r.reasons, "id": r.id}))
            edges.append(GraphEdge(source="dim:related", target=rid, weight=r.score))
    return Graph(nodes=nodes, edges=edges)

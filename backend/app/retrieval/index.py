"""Vector index backends behind one small interface.

``MemoryVectorIndex`` holds a numpy matrix per namespace — exact cosine search,
comfortably fast for corpora up to ~100k entries. ``PgVectorIndex`` stores
vectors in PostgreSQL with the pgvector extension for larger deployments.
"""

from __future__ import annotations

from typing import Protocol

import numpy as np
from sqlalchemy import text
from sqlalchemy.engine import Engine


class VectorIndex(Protocol):
    def upsert(self, namespace: str, ids: list[int], vectors: np.ndarray) -> None: ...

    def search(
        self, namespace: str, vector: np.ndarray, k: int, exclude: set[int] | None = None
    ) -> list[tuple[int, float]]: ...

    def count(self, namespace: str) -> int: ...


class MemoryVectorIndex:
    def __init__(self) -> None:
        self._ids: dict[str, np.ndarray] = {}
        self._mat: dict[str, np.ndarray] = {}

    def upsert(self, namespace: str, ids: list[int], vectors: np.ndarray) -> None:
        if namespace in self._ids and len(self._ids[namespace]):
            keep = ~np.isin(self._ids[namespace], ids)
            old_ids, old_mat = self._ids[namespace][keep], self._mat[namespace][keep]
            self._ids[namespace] = np.concatenate([old_ids, np.asarray(ids)])
            self._mat[namespace] = np.vstack([old_mat, vectors]).astype(np.float32)
        else:
            self._ids[namespace] = np.asarray(ids)
            self._mat[namespace] = np.asarray(vectors, dtype=np.float32)

    def remove(self, namespace: str, ids: list[int]) -> None:
        if namespace in self._ids:
            keep = ~np.isin(self._ids[namespace], ids)
            self._ids[namespace] = self._ids[namespace][keep]
            self._mat[namespace] = self._mat[namespace][keep]

    def search(self, namespace, vector, k, exclude=None):
        if namespace not in self._mat or not len(self._ids[namespace]):
            return []
        scores = self._mat[namespace] @ vector.astype(np.float32)
        order = np.argsort(-scores)
        out: list[tuple[int, float]] = []
        for idx in order:
            pid = int(self._ids[namespace][idx])
            if exclude and pid in exclude:
                continue
            out.append((pid, float(scores[idx])))
            if len(out) >= k:
                break
        return out

    def count(self, namespace: str) -> int:
        return int(len(self._ids.get(namespace, [])))


class PgVectorIndex:  # pragma: no cover - requires PostgreSQL with pgvector
    """pgvector-backed index. Vectors must be L2-normalized; uses cosine distance (<=>)."""

    def __init__(self, engine: Engine, dim: int) -> None:
        self.engine = engine
        self.dim = dim
        with engine.begin() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            conn.execute(text(
                f"CREATE TABLE IF NOT EXISTS phrase_vectors ("
                f" namespace varchar(40) NOT NULL, phrase_id integer NOT NULL,"
                f" embedding vector({dim}) NOT NULL, PRIMARY KEY (namespace, phrase_id))"
            ))
            conn.execute(text(
                "CREATE INDEX IF NOT EXISTS phrase_vectors_hnsw ON phrase_vectors "
                "USING hnsw (embedding vector_cosine_ops)"
            ))

    @staticmethod
    def _literal(vec: np.ndarray) -> str:
        return "[" + ",".join(f"{x:.6f}" for x in vec.tolist()) + "]"

    def upsert(self, namespace, ids, vectors):
        rows = [{"ns": namespace, "pid": int(i), "emb": self._literal(v)} for i, v in zip(ids, vectors)]
        with self.engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO phrase_vectors (namespace, phrase_id, embedding) VALUES (:ns, :pid, CAST(:emb AS vector)) "
                    "ON CONFLICT (namespace, phrase_id) DO UPDATE SET embedding = EXCLUDED.embedding"
                ),
                rows,
            )

    def search(self, namespace, vector, k, exclude=None):
        exclude = list(exclude or [])
        with self.engine.connect() as conn:
            result = conn.execute(
                text(
                    "SELECT phrase_id, 1 - (embedding <=> CAST(:q AS vector)) AS score FROM phrase_vectors "
                    "WHERE namespace = :ns AND NOT (phrase_id = ANY(CAST(:ex AS integer[]))) "
                    "ORDER BY embedding <=> CAST(:q AS vector) LIMIT :k"
                ),
                {"q": self._literal(vector), "ns": namespace, "ex": exclude, "k": k},
            )
            return [(int(r.phrase_id), float(r.score)) for r in result]

    def count(self, namespace):
        with self.engine.connect() as conn:
            return int(conn.execute(text("SELECT count(*) FROM phrase_vectors WHERE namespace = :ns"), {"ns": namespace}).scalar())

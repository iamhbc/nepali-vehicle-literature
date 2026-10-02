"""Embedding providers.

``HashingEmbedder`` (default) needs no model download: it hashes Devanagari
character n-grams of the spelling-folded match key plus English word features
into a fixed-size vector. It captures spelling variants, inflection and shared
vocabulary, but not paraphrase. It is deterministic and fast enough to rebuild on
every start.

``SentenceTransformerEmbedder`` uses a multilingual transformer (default
``intfloat/multilingual-e5-base``) for true cross-lingual semantic similarity.
Install with ``pip install -e ".[embeddings]"`` and set
``EMBEDDING_PROVIDER=sentence-transformers``.
"""

from __future__ import annotations

import hashlib
import math
import re
from collections import Counter
from typing import Protocol

import numpy as np

from ..nlp.normalize import char_ngrams, match_key

_EN_STOP = set(
    "a an the and or of to in on at for with from by is are was were be been it its this that these those "
    "i me my you your he she his her we our they their as not no but if so do does did can could would should "
    "about phrases phrase expressions expression saying sayings inscription inscriptions find show me".split()
)


class Embedder(Protocol):
    name: str
    dim: int

    def embed_documents(self, texts: list[str]) -> np.ndarray: ...

    def embed_query(self, text: str) -> np.ndarray: ...


def _stable_hash(feature: str) -> int:
    return int.from_bytes(hashlib.blake2b(feature.encode("utf-8"), digest_size=8).digest(), "big")


def _en_stem(word: str) -> str:
    for suffix in ("ness", "ing", "ies", "ed", "es", "s"):
        if len(word) > len(suffix) + 3 and word.endswith(suffix):
            return word[: -len(suffix)] + ("y" if suffix == "ies" else "")
    return word


def english_terms(text: str) -> list[str]:
    words = [w for w in re.findall(r"[a-z]+", text.lower()) if w not in _EN_STOP and len(w) > 2]
    return [_en_stem(w) for w in words]


class HashingEmbedder:
    name = "hashing-ngram-v1"

    def __init__(self, dim: int = 2048) -> None:
        self.dim = dim

    def _features(self, text: str) -> Counter:
        feats: Counter = Counter()
        key = match_key(text)
        deva = " ".join(w for w in key.split() if re.search(r"[ऀ-ॿ]", w))
        for gram in char_ngrams(deva):
            feats["n:" + gram] += 1.0
        for word in deva.split():
            feats["w:" + word] += 1.5
        terms = english_terms(text)
        for term in terms:
            feats["e:" + term] += 1.0
        for a, b in zip(terms, terms[1:]):
            feats["b:" + a + "_" + b] += 0.5
        return feats

    def _vector(self, text: str) -> np.ndarray:
        vec = np.zeros(self.dim, dtype=np.float32)
        for feat, count in self._features(text).items():
            h = _stable_hash(feat)
            sign = 1.0 if (h >> 63) & 1 else -1.0
            vec[h % self.dim] += sign * (1.0 + math.log(count))
        norm = float(np.linalg.norm(vec))
        return vec / norm if norm else vec

    def embed_documents(self, texts: list[str]) -> np.ndarray:
        return np.vstack([self._vector(t) for t in texts]) if texts else np.zeros((0, self.dim), np.float32)

    def embed_query(self, text: str) -> np.ndarray:
        return self._vector(text)


class SentenceTransformerEmbedder:  # pragma: no cover - optional heavy dependency
    def __init__(self, model_name: str) -> None:
        from sentence_transformers import SentenceTransformer

        self._model = SentenceTransformer(model_name)
        self.name = f"st:{model_name}"
        self.dim = int(self._model.get_sentence_embedding_dimension())
        self._e5 = "e5" in model_name

    def embed_documents(self, texts: list[str]) -> np.ndarray:
        prefixed = [f"passage: {t}" for t in texts] if self._e5 else texts
        return np.asarray(self._model.encode(prefixed, normalize_embeddings=True), dtype=np.float32)

    def embed_query(self, text: str) -> np.ndarray:
        q = f"query: {text}" if self._e5 else text
        return np.asarray(self._model.encode([q], normalize_embeddings=True)[0], dtype=np.float32)


def make_embedder(provider: str, model_name: str) -> Embedder:
    if provider == "sentence-transformers":
        return SentenceTransformerEmbedder(model_name)
    return HashingEmbedder()

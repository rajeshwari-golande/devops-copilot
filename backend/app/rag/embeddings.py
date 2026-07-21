"""Local embeddings via sentence-transformers (zero API cost)."""

from __future__ import annotations

import logging
from functools import lru_cache

logger = logging.getLogger(__name__)

# Lightweight hash embedding used when sentence-transformers is unavailable
# (first boot / CI without model download). Real demos use the MiniLM model.


def _hash_embed(texts: list[str], dim: int = 384) -> list[list[float]]:
    import hashlib
    import math

    vectors: list[list[float]] = []
    for text in texts:
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        raw = [(digest[i % len(digest)] / 255.0) * 2 - 1 for i in range(dim)]
        norm = math.sqrt(sum(x * x for x in raw)) or 1.0
        vectors.append([x / norm for x in raw])
    return vectors


class EmbeddingService:
    """Wraps sentence-transformers with a deterministic fallback."""

    def __init__(self, model_name: str) -> None:
        self.model_name = model_name
        self._model = None
        self._backend = "hash"

    def _load(self) -> None:
        if self._model is not None or self._backend == "hash_locked":
            return
        try:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(self.model_name)
            self._backend = "sentence-transformers"
            logger.info("Loaded embedding model: %s", self.model_name)
        except Exception as exc:  # noqa: BLE001 — fall back for offline/CI
            logger.warning("sentence-transformers unavailable (%s); using hash embeddings", exc)
            self._backend = "hash_locked"

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        self._load()
        if self._model is not None:
            return self._model.encode(texts, normalize_embeddings=True).tolist()
        return _hash_embed(texts)

    def embed_query(self, text: str) -> list[float]:
        return self.embed_documents([text])[0]


@lru_cache
def get_embedding_service() -> EmbeddingService:
    from app.config import get_settings

    return EmbeddingService(get_settings().embedding_model)

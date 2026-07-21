"""ChromaDB knowledge base for historical CI failures + known fixes."""

from __future__ import annotations

import logging
import uuid
from functools import lru_cache
from typing import Any

import chromadb
from chromadb.config import Settings as ChromaSettings

from app.config import get_settings
from app.rag.embeddings import get_embedding_service

logger = logging.getLogger(__name__)


@lru_cache
def get_chroma_client() -> chromadb.ClientAPI:
    settings = get_settings()
    return chromadb.PersistentClient(
        path=settings.chroma_persist_dir,
        settings=ChromaSettings(anonymized_telemetry=False),
    )


def ensure_collection() -> chromadb.Collection:
    client = get_chroma_client()
    settings = get_settings()
    return client.get_or_create_collection(
        name=settings.chroma_collection,
        metadata={"hnsw:space": "cosine"},
    )


def add_knowledge(
    documents: list[str],
    metadatas: list[dict[str, Any]],
    ids: list[str] | None = None,
) -> list[str]:
    if not documents:
        return []
    collection = ensure_collection()
    embedder = get_embedding_service()
    doc_ids = ids or [str(uuid.uuid4()) for _ in documents]
    embeddings = embedder.embed_documents(documents)
    collection.upsert(
        ids=doc_ids,
        documents=documents,
        metadatas=metadatas,
        embeddings=embeddings,
    )
    logger.info("Upserted %d knowledge documents", len(documents))
    return doc_ids


def query_similar(query: str, n_results: int = 5) -> list[dict[str, Any]]:
    collection = ensure_collection()
    if collection.count() == 0:
        return []
    embedder = get_embedding_service()
    embedding = embedder.embed_query(query)
    results = collection.query(
        query_embeddings=[embedding],
        n_results=min(n_results, collection.count()),
        include=["documents", "metadatas", "distances"],
    )
    hits: list[dict[str, Any]] = []
    docs = results.get("documents", [[]])[0]
    metas = results.get("metadatas", [[]])[0]
    dists = results.get("distances", [[]])[0]
    ids = results.get("ids", [[]])[0]
    for i, doc in enumerate(docs):
        hits.append(
            {
                "id": ids[i] if i < len(ids) else None,
                "document": doc,
                "metadata": metas[i] if i < len(metas) else {},
                "distance": dists[i] if i < len(dists) else None,
            }
        )
    return hits

"""Health & readiness endpoints (keep-alive friendly for Render free tier)."""

from fastapi import APIRouter

from app import __version__
from app.config import get_settings
from app.models.schemas import HealthResponse
from app.rag.chroma_store import ensure_collection

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    settings = get_settings()
    kb_count = 0
    try:
        kb_count = ensure_collection().count()
    except Exception:  # noqa: BLE001
        kb_count = 0
    from app.rag.embeddings import get_embedding_service

    emb = get_embedding_service()
    return HealthResponse(
        status="ok",
        app=settings.app_name,
        mock_mode=settings.mock_mode,
        llm_ready=settings.use_llm or settings.use_groq,
        llm_backend=settings.llm_backend,
        embedding_backend=emb.backend_name,
        knowledge_docs=kb_count,
        version=__version__,
    )


@router.get("/")
async def root() -> dict:
    return {
        "message": "DevOps Copilot API",
        "docs": "/docs",
        "health": "/health",
    }

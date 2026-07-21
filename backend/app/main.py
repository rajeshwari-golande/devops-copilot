"""DevOps Copilot FastAPI application entrypoint."""

from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import dashboard, failures, feedback, health, samples, webhooks
from app.config import get_settings
from app.db.session import init_db
from app.rag.chroma_store import ensure_collection
from app.rag.ingestion import seed_knowledge_base

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    settings = get_settings()
    await init_db()
    ensure_collection()
    if settings.auto_seed_knowledge:
        n = seed_knowledge_base(force=False)
        if n:
            logger.info("Auto-seeded %d knowledge documents", n)
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        description=(
            "AI agent for CI/CD failure diagnosis and safe auto-remediation. "
            "Built on FastAPI + LangGraph + Groq + ChromaDB."
        ),
        version="0.1.0",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(health.router, tags=["health"])
    app.include_router(webhooks.router, prefix="/api/v1", tags=["webhooks"])
    app.include_router(failures.router, prefix="/api/v1", tags=["failures"])
    app.include_router(feedback.router, prefix="/api/v1", tags=["feedback"])
    app.include_router(dashboard.router, prefix="/api/v1", tags=["dashboard"])
    app.include_router(samples.router, prefix="/api/v1", tags=["samples"])
    return app


app = create_app()

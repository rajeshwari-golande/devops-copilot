"""Async database session & engine."""

from collections.abc import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings
from app.db.models import Base

settings = get_settings()

connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_async_engine(settings.database_url, echo=settings.debug, connect_args=connect_args)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

# Lightweight SQLite column adds when create_all won't alter existing tables
_SQLITE_EXTRA_COLUMNS = {
    "pipeline_failures": [
        ("remediation_detail", "JSON"),
        ("outcome_status", "VARCHAR(64)"),
        ("outcome_conclusion", "VARCHAR(64)"),
        ("circuit_blocked", "BOOLEAN DEFAULT 0"),
    ]
}


def _ensure_sqlite_columns(sync_conn) -> None:
    if not settings.database_url.startswith("sqlite"):
        return
    for table, cols in _SQLITE_EXTRA_COLUMNS.items():
        existing = {
            row[1]
            for row in sync_conn.execute(text(f"PRAGMA table_info({table})")).fetchall()
        }
        if not existing:
            continue
        for name, coltype in cols:
            if name not in existing:
                sync_conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {coltype}"))


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(_ensure_sqlite_columns)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session

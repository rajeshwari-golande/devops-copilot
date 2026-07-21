"""SQLAlchemy ORM models."""

from datetime import datetime
from enum import Enum

from sqlalchemy import JSON, Boolean, DateTime, Float, Integer, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class FailureStatus(str, Enum):
    RECEIVED = "received"
    ANALYZING = "analyzing"
    DIAGNOSED = "diagnosed"
    REMEDIATED = "remediated"
    AWAITING_APPROVAL = "awaiting_approval"
    RESOLVED = "resolved"
    FAILED = "failed"


class RemediationAction(str, Enum):
    NONE = "none"
    RETRY_WORKFLOW = "retry_workflow"
    CLEAR_CACHE = "clear_cache"
    PIN_DEPENDENCY = "pin_dependency"
    NEEDS_APPROVAL = "needs_approval"


class PipelineFailure(Base):
    __tablename__ = "pipeline_failures"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    github_run_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    repo: Mapped[str] = mapped_column(String(255), default="local/demo")
    workflow_name: Mapped[str] = mapped_column(String(255), default="unknown")
    job_name: Mapped[str] = mapped_column(String(255), default="unknown")
    branch: Mapped[str] = mapped_column(String(128), default="main")
    commit_sha: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(64), default=FailureStatus.RECEIVED.value)
    raw_logs: Mapped[str] = mapped_column(Text, default="")
    error_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    root_cause: Mapped[str | None] = mapped_column(Text, nullable=True)
    suggested_fix: Mapped[str | None] = mapped_column(Text, nullable=True)
    classification: Mapped[str | None] = mapped_column(String(128), nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    remediation_action: Mapped[str] = mapped_column(
        String(64), default=RemediationAction.NONE.value
    )
    auto_applied: Mapped[bool] = mapped_column(Boolean, default=False)
    similar_cases: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    agent_reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Feedback(Base):
    __tablename__ = "feedback"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    failure_id: Mapped[int] = mapped_column(Integer, index=True)
    is_correct: Mapped[bool] = mapped_column(Boolean)
    engineer_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    corrected_root_cause: Mapped[str | None] = mapped_column(Text, nullable=True)
    corrected_fix: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

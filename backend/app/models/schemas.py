"""Pydantic request/response schemas."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str
    app: str
    mock_mode: bool
    llm_ready: bool
    llm_backend: str = "mock"
    knowledge_docs: int = 0
    version: str


class SampleLogOut(BaseModel):
    id: str
    filename: str
    title: str
    description: str = ""
    expected_classification: str | None = None
    content: str


class DiagnoseRequest(BaseModel):
    repo: str = "local/demo"
    workflow_name: str = "ci"
    job_name: str = "build"
    branch: str = "main"
    commit_sha: str | None = None
    github_run_id: str | None = None
    raw_logs: str = Field(..., min_length=1, description="CI failure logs to diagnose")


class DiagnosisResult(BaseModel):
    classification: str
    root_cause: str
    suggested_fix: str
    confidence: float
    remediation_action: str
    auto_apply_safe: bool
    similar_cases: list[dict[str, Any]] = Field(default_factory=list)
    agent_reasoning: str


class FailureOut(BaseModel):
    id: int
    github_run_id: str | None
    repo: str
    workflow_name: str
    job_name: str
    branch: str
    commit_sha: str | None
    status: str
    error_summary: str | None
    root_cause: str | None
    suggested_fix: str | None
    classification: str | None
    confidence: float | None
    remediation_action: str
    auto_applied: bool
    similar_cases: list[dict[str, Any]] | dict[str, Any] | None
    agent_reasoning: str | None
    created_at: datetime | None

    model_config = {"from_attributes": True}


class FeedbackCreate(BaseModel):
    failure_id: int
    is_correct: bool
    engineer_notes: str | None = None
    corrected_root_cause: str | None = None
    corrected_fix: str | None = None


class FeedbackOut(BaseModel):
    id: int
    failure_id: int
    is_correct: bool
    engineer_notes: str | None
    created_at: datetime | None

    model_config = {"from_attributes": True}


class DashboardStats(BaseModel):
    total_failures: int
    diagnosed: int
    auto_remediated: int
    awaiting_approval: int
    feedback_count: int
    accuracy_estimate: float | None
    by_classification: dict[str, int]
    recent_failures: list[FailureOut]

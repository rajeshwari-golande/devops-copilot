"""Orchestrates diagnose → circuit check → remediate → optional outcome verify → alert."""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.graph import run_diagnosis
from app.config import get_settings
from app.db.models import FailureStatus, PipelineFailure
from app.services.log_parser import extract_error_summary
from app.services.remediation import apply_safe_remediation
from app.services.slack import post_failure_alert
from app.taxonomy import normalize_classification

logger = logging.getLogger(__name__)


async def process_failure(
    db: AsyncSession,
    *,
    raw_logs: str,
    repo: str = "local/demo",
    workflow_name: str = "ci",
    job_name: str = "build",
    branch: str = "main",
    commit_sha: str | None = None,
    github_run_id: str | None = None,
) -> PipelineFailure:
    settings = get_settings()
    failure = PipelineFailure(
        github_run_id=github_run_id,
        repo=repo,
        workflow_name=workflow_name,
        job_name=job_name,
        branch=branch,
        commit_sha=commit_sha,
        status=FailureStatus.ANALYZING.value,
        raw_logs=raw_logs,
        error_summary=extract_error_summary(raw_logs),
    )
    db.add(failure)
    await db.commit()
    await db.refresh(failure)

    diagnosis = run_diagnosis(raw_logs)
    classification = normalize_classification(diagnosis.get("classification"))
    failure.classification = classification
    failure.root_cause = diagnosis.get("root_cause")
    failure.suggested_fix = diagnosis.get("suggested_fix")
    failure.confidence = diagnosis.get("confidence")
    failure.remediation_action = diagnosis.get("remediation_action", "none")
    failure.similar_cases = diagnosis.get("similar_cases")
    failure.agent_reasoning = diagnosis.get("agent_reasoning")
    failure.status = FailureStatus.DIAGNOSED.value

    auto_applied = False
    circuit_blocked = False
    if diagnosis.get("auto_apply_safe"):
        result = await apply_safe_remediation(
            diagnosis["remediation_action"],
            repo=repo,
            github_run_id=github_run_id,
            workflow_name=workflow_name,
            verify_outcome=settings.verify_remediation_outcome,
        )
        failure.remediation_detail = result
        circuit_blocked = bool(result.get("circuit_open"))
        auto_applied = bool(result.get("applied")) and not circuit_blocked
        if auto_applied:
            failure.status = FailureStatus.REMEDIATED.value
            outcome = result.get("outcome") or {}
            if outcome.get("conclusion"):
                failure.outcome_status = outcome.get("status")
                failure.outcome_conclusion = outcome.get("conclusion")
                if outcome.get("conclusion") == "success":
                    failure.status = FailureStatus.RESOLVED.value
                elif outcome.get("conclusion") == "failure":
                    failure.status = FailureStatus.FAILED.value
        else:
            failure.status = FailureStatus.AWAITING_APPROVAL.value
    else:
        failure.status = FailureStatus.AWAITING_APPROVAL.value

    failure.auto_applied = auto_applied
    failure.circuit_blocked = circuit_blocked
    await db.commit()
    await db.refresh(failure)

    await post_failure_alert(
        {
            "classification": failure.classification,
            "repo": failure.repo,
            "workflow_name": failure.workflow_name,
            "job_name": failure.job_name,
            "root_cause": failure.root_cause,
            "suggested_fix": failure.suggested_fix,
            "remediation_action": failure.remediation_action,
            "auto_applied": failure.auto_applied,
            "confidence": failure.confidence,
            "circuit_blocked": circuit_blocked,
        }
    )
    return failure


def diagnosis_to_dict(diagnosis: dict[str, Any]) -> dict[str, Any]:
    return diagnosis

"""Orchestrates diagnose → persist → remediate → alert."""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.graph import run_diagnosis
from app.db.models import FailureStatus, PipelineFailure
from app.services.log_parser import extract_error_summary
from app.services.remediation import apply_safe_remediation
from app.services.slack import post_failure_alert

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
    failure.classification = diagnosis.get("classification")
    failure.root_cause = diagnosis.get("root_cause")
    failure.suggested_fix = diagnosis.get("suggested_fix")
    failure.confidence = diagnosis.get("confidence")
    failure.remediation_action = diagnosis.get("remediation_action", "none")
    failure.similar_cases = diagnosis.get("similar_cases")
    failure.agent_reasoning = diagnosis.get("agent_reasoning")
    failure.status = FailureStatus.DIAGNOSED.value

    auto_applied = False
    if diagnosis.get("auto_apply_safe"):
        result = await apply_safe_remediation(
            diagnosis["remediation_action"],
            repo=repo,
            github_run_id=github_run_id,
        )
        auto_applied = bool(result.get("applied"))
        if auto_applied:
            failure.status = FailureStatus.REMEDIATED.value
        else:
            failure.status = FailureStatus.AWAITING_APPROVAL.value
    else:
        failure.status = FailureStatus.AWAITING_APPROVAL.value

    failure.auto_applied = auto_applied
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
        }
    )
    return failure


def diagnosis_to_dict(diagnosis: dict[str, Any]) -> dict[str, Any]:
    return diagnosis

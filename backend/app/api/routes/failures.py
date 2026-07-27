"""Manual diagnose + failure CRUD + approve remediation."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import FailureStatus, PipelineFailure
from app.db.session import get_db
from app.models.schemas import DiagnoseRequest, FailureOut
from app.services.pipeline import process_failure
from app.services.remediation import ALLOWED_ACTIONS, apply_safe_remediation

router = APIRouter()


@router.post("/failures/diagnose", response_model=FailureOut)
async def diagnose_failure(
    body: DiagnoseRequest,
    db: AsyncSession = Depends(get_db),
):
    failure = await process_failure(
        db,
        raw_logs=body.raw_logs,
        repo=body.repo,
        workflow_name=body.workflow_name,
        job_name=body.job_name,
        branch=body.branch,
        commit_sha=body.commit_sha,
        github_run_id=body.github_run_id,
    )
    return FailureOut.model_validate(failure)


@router.get("/failures", response_model=list[FailureOut])
async def list_failures(
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
):
    limit = max(1, min(limit, 200))
    result = await db.execute(
        select(PipelineFailure).order_by(PipelineFailure.id.desc()).limit(limit)
    )
    rows = result.scalars().all()
    return [FailureOut.model_validate(r) for r in rows]


@router.get("/failures/{failure_id}", response_model=FailureOut)
async def get_failure(failure_id: int, db: AsyncSession = Depends(get_db)):
    row = await db.get(PipelineFailure, failure_id)
    if not row:
        raise HTTPException(status_code=404, detail="Failure not found")
    return FailureOut.model_validate(row)


@router.post("/failures/{failure_id}/rediagnose", response_model=FailureOut)
async def rediagnose_failure(failure_id: int, db: AsyncSession = Depends(get_db)):
    row = await db.get(PipelineFailure, failure_id)
    if not row:
        raise HTTPException(status_code=404, detail="Failure not found")
    if not row.raw_logs:
        raise HTTPException(status_code=400, detail="No logs stored for this failure")

    # Create a fresh diagnosis record from the same logs (keeps history)
    failure = await process_failure(
        db,
        raw_logs=row.raw_logs,
        repo=row.repo,
        workflow_name=row.workflow_name,
        job_name=row.job_name,
        branch=row.branch,
        commit_sha=row.commit_sha,
        github_run_id=row.github_run_id,
    )
    return FailureOut.model_validate(failure)


@router.post("/failures/{failure_id}/approve-remediation", response_model=FailureOut)
async def approve_remediation(failure_id: int, db: AsyncSession = Depends(get_db)):
    """Human approves applying the suggested safe remediation."""
    row = await db.get(PipelineFailure, failure_id)
    if not row:
        raise HTTPException(status_code=404, detail="Failure not found")

    action = row.remediation_action
    if action not in ALLOWED_ACTIONS:
        # If agent said needs_approval with a non-safe action, only retry is ever forced-safe
        if action in {"needs_approval", "none"}:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Remediation `{action}` is not auto-applicable. "
                    "Only retry_workflow / clear_cache / pin_dependency can be applied."
                ),
            )
        raise HTTPException(status_code=400, detail=f"Action `{action}` is not in the safe allowlist")

    result = await apply_safe_remediation(
        action,
        repo=row.repo,
        github_run_id=row.github_run_id,
        workflow_name=row.workflow_name,
    )
    row.remediation_detail = result
    row.circuit_blocked = bool(result.get("circuit_open"))
    if result.get("applied"):
        row.auto_applied = True
        row.status = FailureStatus.REMEDIATED.value
        outcome = result.get("outcome") or {}
        if outcome.get("conclusion"):
            row.outcome_conclusion = outcome.get("conclusion")
            row.outcome_status = outcome.get("status")
    else:
        row.status = FailureStatus.AWAITING_APPROVAL.value
    await db.commit()
    await db.refresh(row)
    return FailureOut.model_validate(row)

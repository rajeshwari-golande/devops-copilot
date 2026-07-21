"""GitHub Actions webhook ingestion."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.schemas import FailureOut
from app.services.github import fetch_workflow_run_logs, verify_webhook_signature
from app.services.pipeline import process_failure

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/webhooks/github")
async def github_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
    x_hub_signature_256: str | None = Header(default=None),
    x_github_event: str | None = Header(default=None),
):
    body = await request.body()
    if not verify_webhook_signature(body, x_hub_signature_256):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    payload = await request.json()
    event = (x_github_event or "").lower()

    if event == "ping":
        return {"ok": True, "message": "pong"}

    if event and event != "workflow_run":
        raise HTTPException(status_code=202, detail=f"Ignored event type: {event}")

    action = payload.get("action")
    workflow_run = payload.get("workflow_run") or {}
    conclusion = workflow_run.get("conclusion")
    if action != "completed" or conclusion != "failure":
        raise HTTPException(
            status_code=202,
            detail=f"Ignored event (action={action}, conclusion={conclusion})",
        )

    repo_full = payload.get("repository", {}).get("full_name", "unknown/unknown")
    owner, _, name = repo_full.partition("/")
    run_id = str(workflow_run.get("id", ""))
    logs = await fetch_workflow_run_logs(owner, name, run_id)

    failure = await process_failure(
        db,
        raw_logs=logs,
        repo=repo_full,
        workflow_name=workflow_run.get("name", "unknown"),
        job_name="failed_jobs",
        branch=workflow_run.get("head_branch", "main"),
        commit_sha=(workflow_run.get("head_sha") or None),
        github_run_id=run_id,
    )
    return FailureOut.model_validate(failure)

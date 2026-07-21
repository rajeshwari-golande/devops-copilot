"""GitHub Actions API client (read logs, re-run workflows)."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)
API = "https://api.github.com"


async def fetch_workflow_run_logs(owner: str, repo: str, run_id: str) -> str:
    settings = get_settings()
    if settings.mock_mode or not settings.github_token:
        return (
            f"[MOCK LOGS] owner={owner} repo={repo} run_id={run_id}\n"
            "Error: connect ETIMEDOUT registry.npmjs.org\n"
            "npm ERR! network Temporary network failure\n"
            "Process completed with exit code 1.\n"
        )

    headers = {
        "Authorization": f"Bearer {settings.github_token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
        # jobs list
        jobs_url = f"{API}/repos/{owner}/{repo}/actions/runs/{run_id}/jobs"
        jobs_resp = await client.get(jobs_url, headers=headers)
        jobs_resp.raise_for_status()
        jobs = jobs_resp.json().get("jobs", [])
        chunks: list[str] = []
        for job in jobs:
            if job.get("conclusion") in (None, "success"):
                continue
            job_id = job["id"]
            logs_url = f"{API}/repos/{owner}/{repo}/actions/jobs/{job_id}/logs"
            logs_resp = await client.get(logs_url, headers=headers)
            if logs_resp.status_code == 200:
                chunks.append(f"=== Job: {job.get('name')} ===\n{logs_resp.text}")
        return "\n\n".join(chunks) if chunks else f"No failed job logs found for run {run_id}"


async def rerun_workflow(run_id: str | None) -> dict[str, Any]:
    settings = get_settings()
    if not run_id:
        return {"ok": False, "error": "missing run_id"}
    owner = settings.github_repo_owner
    repo = settings.github_repo_name
    if not owner or not repo:
        return {"ok": False, "error": "GITHUB_REPO_OWNER/NAME not configured"}

    headers = {
        "Authorization": f"Bearer {settings.github_token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    url = f"{API}/repos/{owner}/{repo}/actions/runs/{run_id}/rerun"
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(url, headers=headers)
        if resp.status_code in (201, 202):
            return {"ok": True, "status_code": resp.status_code}
        return {"ok": False, "status_code": resp.status_code, "body": resp.text[:500]}


def verify_webhook_signature(payload: bytes, signature_header: str | None) -> bool:
    """HMAC SHA-256 verification for GitHub webhooks. Passes in mock/dev if secret unset."""
    import hashlib
    import hmac

    settings = get_settings()
    if not settings.github_webhook_secret:
        return True
    if not signature_header or not signature_header.startswith("sha256="):
        return False
    digest = hmac.new(
        settings.github_webhook_secret.encode(),
        payload,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(f"sha256={digest}", signature_header)

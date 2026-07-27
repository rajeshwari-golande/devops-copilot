"""GitHub Actions API — logs, re-run, cache clear, run status polling."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)
API = "https://api.github.com"


def _headers() -> dict[str, str]:
    settings = get_settings()
    return {
        "Authorization": f"Bearer {settings.github_token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def _parse_repo(repo: str | None = None) -> tuple[str, str]:
    settings = get_settings()
    if repo and "/" in repo:
        owner, _, name = repo.partition("/")
        if owner and name:
            return owner, name
    return settings.github_repo_owner, settings.github_repo_name


def github_io_enabled() -> bool:
    """True when a token is present — independent of MOCK_MODE (LLM mock can still be on)."""
    return bool(get_settings().github_token)


async def list_failed_runs(owner: str, repo: str, per_page: int = 10) -> list[dict[str, Any]]:
    """List recent failed workflow runs on a public or accessible repo."""
    if not github_io_enabled():
        return []
    url = f"{API}/repos/{owner}/{repo}/actions/runs"
    params = {"status": "failure", "per_page": per_page}
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.get(url, headers=_headers(), params=params)
        if resp.status_code != 200:
            logger.warning("list_failed_runs %s/%s -> %s", owner, repo, resp.status_code)
            return []
        return resp.json().get("workflow_runs", [])


async def fetch_workflow_run_logs(owner: str, repo: str, run_id: str) -> str:
    settings = get_settings()
    if not github_io_enabled():
        return (
            f"[MOCK LOGS] owner={owner} repo={repo} run_id={run_id}\n"
            "Error: connect ETIMEDOUT registry.npmjs.org\n"
            "npm ERR! network Temporary network failure\n"
            "Process completed with exit code 1.\n"
        )

    async with httpx.AsyncClient(timeout=90.0, follow_redirects=True) as client:
        jobs_url = f"{API}/repos/{owner}/{repo}/actions/runs/{run_id}/jobs"
        jobs_resp = await client.get(jobs_url, headers=_headers())
        jobs_resp.raise_for_status()
        jobs = jobs_resp.json().get("jobs", [])
        chunks: list[str] = []
        for job in jobs:
            if job.get("conclusion") in (None, "success"):
                continue
            job_id = job["id"]
            logs_url = f"{API}/repos/{owner}/{repo}/actions/jobs/{job_id}/logs"
            logs_resp = await client.get(logs_url, headers=_headers())
            if logs_resp.status_code == 200:
                text = logs_resp.text
                # Cap huge logs for RAG / LLM context
                if len(text) > 50_000:
                    text = text[-50_000:]
                chunks.append(f"=== Job: {job.get('name')} ===\n{text}")
        return "\n\n".join(chunks) if chunks else f"No failed job logs found for run {run_id}"


async def rerun_workflow(
    run_id: str | None,
    *,
    repo: str | None = None,
) -> dict[str, Any]:
    if not run_id:
        return {"ok": False, "error": "missing run_id"}
    owner, name = _parse_repo(repo)
    if not owner or not name:
        return {"ok": False, "error": "repo owner/name not configured"}
    if not github_io_enabled():
        return {"ok": False, "error": "GITHUB_TOKEN not set"}

    url = f"{API}/repos/{owner}/{name}/actions/runs/{run_id}/rerun"
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(url, headers=_headers())
        if resp.status_code in (201, 202):
            return {"ok": True, "status_code": resp.status_code, "owner": owner, "repo": name}
        return {"ok": False, "status_code": resp.status_code, "body": resp.text[:500]}


async def clear_actions_caches(*, repo: str | None = None) -> dict[str, Any]:
    """DELETE all Actions caches for the repo (safe allowlisted remediation)."""
    owner, name = _parse_repo(repo)
    if not owner or not name:
        return {"ok": False, "error": "repo owner/name not configured"}
    if not github_io_enabled():
        return {"ok": False, "error": "GITHUB_TOKEN not set"}

    list_url = f"{API}/repos/{owner}/{name}/actions/caches"
    async with httpx.AsyncClient(timeout=60.0) as client:
        listed = await client.get(list_url, headers=_headers(), params={"per_page": 100})
        if listed.status_code != 200:
            return {"ok": False, "status_code": listed.status_code, "body": listed.text[:300]}
        caches = listed.json().get("actions_caches", [])
        deleted = 0
        for cache in caches:
            cid = cache.get("id")
            if cid is None:
                continue
            del_url = f"{API}/repos/{owner}/{name}/actions/caches/{cid}"
            dresp = await client.delete(del_url, headers=_headers())
            if dresp.status_code in (200, 204):
                deleted += 1
        # After clearing caches, re-run is typically still needed — caller may chain retry
        return {"ok": True, "deleted": deleted, "owner": owner, "repo": name}


async def get_workflow_run(owner: str, repo: str, run_id: str) -> dict[str, Any]:
    if not github_io_enabled():
        return {"ok": False, "error": "no token"}
    url = f"{API}/repos/{owner}/{repo}/actions/runs/{run_id}"
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(url, headers=_headers())
        if resp.status_code != 200:
            return {"ok": False, "status_code": resp.status_code}
        data = resp.json()
        return {
            "ok": True,
            "id": data.get("id"),
            "status": data.get("status"),
            "conclusion": data.get("conclusion"),
            "html_url": data.get("html_url"),
        }


async def poll_run_conclusion(
    owner: str,
    repo: str,
    run_id: str,
    *,
    max_attempts: int = 12,
    interval_sec: float = 10.0,
) -> dict[str, Any]:
    """Poll until the run completes (or attempts exhausted). Verifies real outcomes."""
    import asyncio

    last: dict[str, Any] = {}
    for _ in range(max_attempts):
        last = await get_workflow_run(owner, repo, run_id)
        if not last.get("ok"):
            await asyncio.sleep(interval_sec)
            continue
        if last.get("status") == "completed":
            return last
        await asyncio.sleep(interval_sec)
    return {**last, "timed_out": True}


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

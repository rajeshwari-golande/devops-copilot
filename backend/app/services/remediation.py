"""Safe auto-remediation — allowlisted GitHub Actions API calls only."""

from __future__ import annotations

import logging
from typing import Any

from app.config import get_settings
from app.services import circuit_breaker

logger = logging.getLogger(__name__)

ALLOWED_ACTIONS = frozenset({"retry_workflow", "clear_cache", "pin_dependency"})


async def apply_safe_remediation(
    action: str,
    *,
    repo: str,
    github_run_id: str | None = None,
    workflow_name: str = "ci",
    verify_outcome: bool = False,
) -> dict[str, Any]:
    """
    Execute only allowlisted remediations.

    - MOCK_MODE or missing token: simulate apply (local demos)
    - Otherwise: call real GitHub Actions APIs
    - Circuit breaker: max auto-retries per workflow/hour
    """
    settings = get_settings()
    if action not in ALLOWED_ACTIONS:
        return {
            "applied": False,
            "action": action,
            "reason": "Action not in safe allowlist — requires human approval",
        }

    if circuit_breaker.circuit_open(repo, workflow_name):
        return {
            "applied": False,
            "action": action,
            "circuit_open": True,
            "reason": (
                f"Circuit breaker open: max {settings.auto_remediation_max_per_hour} "
                f"auto-remediations per workflow per hour — forcing manual review"
            ),
        }

    # Simulate when no GitHub write path available
    if settings.mock_github_remediation or not settings.github_token:
        circuit_breaker.record_attempt(repo, workflow_name)
        logger.info("[MOCK] Would apply remediation `%s` for %s run=%s", action, repo, github_run_id)
        return {
            "applied": True,
            "action": action,
            "mock": True,
            "detail": (
                f"Simulated `{action}` for {repo} "
                "(set GITHUB_TOKEN + MOCK_GITHUB_REMEDIATION=false to execute for real)"
            ),
        }

    from app.services import github as gh

    circuit_breaker.record_attempt(repo, workflow_name)
    detail: dict[str, Any]

    if action == "retry_workflow":
        detail = await gh.rerun_workflow(github_run_id, repo=repo)
        applied = bool(detail.get("ok"))
    elif action == "clear_cache":
        cache_result = await gh.clear_actions_caches(repo=repo)
        # Clearing cache alone rarely unblocks; chain a re-run when we have a run id
        rerun = {"ok": False, "skipped": True}
        if github_run_id and cache_result.get("ok"):
            rerun = await gh.rerun_workflow(github_run_id, repo=repo)
        detail = {"cache": cache_result, "rerun": rerun}
        applied = bool(cache_result.get("ok"))
    elif action == "pin_dependency":
        # Real Contents-API PR automation is repo-specific; we document the fix and
        # optionally re-run after a human/CI bot pins. Still allowlisted as a recommendation
        # that can trigger retry once a pin commit exists — for now open for approval.
        return {
            "applied": False,
            "action": action,
            "mock": False,
            "reason": (
                "pin_dependency requires a Contents API commit/PR for the specific manifest; "
                "posted for engineer approval (safe allowlist — no arbitrary file edits)."
            ),
        }
    else:
        return {"applied": False, "action": action, "reason": "unknown action"}

    outcome: dict[str, Any] | None = None
    if applied and verify_outcome and github_run_id and "/" in repo:
        owner, _, name = repo.partition("/")
        # Note: re-run keeps the same run id on GitHub for "re-run all jobs"
        outcome = await gh.poll_run_conclusion(
            owner,
            name,
            str(github_run_id),
            max_attempts=settings.outcome_poll_attempts,
            interval_sec=settings.outcome_poll_interval_sec,
        )

    return {
        "applied": applied,
        "action": action,
        "mock": False,
        "detail": detail,
        "outcome": outcome,
    }

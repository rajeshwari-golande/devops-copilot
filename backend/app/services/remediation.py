"""Safe auto-remediation actions only — never arbitrary code execution."""

from __future__ import annotations

import logging
from typing import Any

from app.config import get_settings

logger = logging.getLogger(__name__)

ALLOWED_ACTIONS = frozenset({"retry_workflow", "clear_cache", "pin_dependency"})


async def apply_safe_remediation(
    action: str,
    *,
    repo: str,
    github_run_id: str | None = None,
) -> dict[str, Any]:
    """
    Execute only allowlisted remediations.

    In MOCK_MODE (default), we simulate success so demos work without GitHub write access.
    """
    settings = get_settings()
    if action not in ALLOWED_ACTIONS:
        return {
            "applied": False,
            "action": action,
            "reason": "Action not in safe allowlist — requires human approval",
        }

    if settings.mock_mode or not settings.github_token:
        logger.info("[MOCK] Would apply remediation `%s` for %s run=%s", action, repo, github_run_id)
        return {
            "applied": True,
            "action": action,
            "mock": True,
            "detail": f"Simulated `{action}` for {repo} (set MOCK_MODE=false + GITHUB_TOKEN to execute)",
        }

    if action == "retry_workflow":
        from app.services.github import rerun_workflow

        result = await rerun_workflow(github_run_id)
        return {"applied": True, "action": action, "mock": False, "detail": result}

    # clear_cache / pin_dependency: logged as recommended; GitHub API support varies by org.
    return {
        "applied": False,
        "action": action,
        "mock": False,
        "reason": (
            f"`{action}` is allowlisted but requires repo-specific automation; "
            "posted as recommendation for engineer approval."
        ),
    }

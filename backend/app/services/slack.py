"""Slack alerting for risky / needs-approval diagnoses."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)


async def post_failure_alert(payload: dict[str, Any]) -> dict[str, Any]:
    settings = get_settings()
    text = (
        f"*DevOps Copilot* — `{payload.get('classification')}`\n"
        f"*Repo:* {payload.get('repo')}\n"
        f"*Workflow:* {payload.get('workflow_name')} / {payload.get('job_name')}\n"
        f"*Root cause:* {payload.get('root_cause')}\n"
        f"*Suggested fix:* {payload.get('suggested_fix')}\n"
        f"*Action:* {payload.get('remediation_action')} "
        f"(auto_applied={payload.get('auto_applied')})\n"
        f"*Confidence:* {payload.get('confidence')}"
    )

    if settings.mock_mode or not settings.slack_bot_token or not settings.slack_channel_id:
        logger.info("[MOCK Slack]\n%s", text)
        return {"ok": True, "mock": True, "text": text}

    async with httpx.AsyncClient(timeout=20.0) as client:
        resp = await client.post(
            "https://slack.com/api/chat.postMessage",
            headers={"Authorization": f"Bearer {settings.slack_bot_token}"},
            json={"channel": settings.slack_channel_id, "text": text},
        )
        data = resp.json()
        return {"ok": bool(data.get("ok")), "response": data}

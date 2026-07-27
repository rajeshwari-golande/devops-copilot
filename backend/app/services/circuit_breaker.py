"""
Circuit breaker for safe auto-remediation.

Prevents infinite retry loops burning CI minutes:
max N auto-retries per workflow key per rolling window, then force manual review.
"""

from __future__ import annotations

import time
from collections import defaultdict
from threading import Lock

from app.config import get_settings

_lock = Lock()
# key -> list of unix timestamps of auto-remediation attempts
_attempts: dict[str, list[float]] = defaultdict(list)


def _key(repo: str, workflow_name: str) -> str:
    return f"{repo}::{workflow_name}".lower()


def circuit_open(repo: str, workflow_name: str) -> bool:
    """True if auto-remediation should be blocked (force human review)."""
    settings = get_settings()
    limit = settings.auto_remediation_max_per_hour
    window = settings.auto_remediation_window_sec
    now = time.time()
    k = _key(repo, workflow_name)
    with _lock:
        recent = [t for t in _attempts[k] if now - t <= window]
        _attempts[k] = recent
        return len(recent) >= limit


def record_attempt(repo: str, workflow_name: str) -> None:
    k = _key(repo, workflow_name)
    with _lock:
        _attempts[k].append(time.time())


def remaining_quota(repo: str, workflow_name: str) -> int:
    settings = get_settings()
    limit = settings.auto_remediation_max_per_hour
    window = settings.auto_remediation_window_sec
    now = time.time()
    k = _key(repo, workflow_name)
    with _lock:
        recent = [t for t in _attempts[k] if now - t <= window]
        return max(0, limit - len(recent))


def reset_for_tests() -> None:
    with _lock:
        _attempts.clear()

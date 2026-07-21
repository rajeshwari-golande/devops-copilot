"""CI log parsing helpers."""

from __future__ import annotations

import re


ERROR_LINE = re.compile(
    r"(?i)(error|failed|exception|traceback|exit code|npm err|modulenotfound|oom|etimedout).*"
)


def extract_error_summary(logs: str, max_lines: int = 20) -> str:
    lines = logs.splitlines()
    hits = [ln.strip() for ln in lines if ERROR_LINE.search(ln)]
    if not hits:
        # Fall back to last N non-empty lines
        hits = [ln.strip() for ln in lines if ln.strip()][-max_lines:]
    return "\n".join(hits[:max_lines])


def chunk_logs(logs: str, chunk_size: int = 1500, overlap: int = 200) -> list[str]:
    if len(logs) <= chunk_size:
        return [logs]
    chunks: list[str] = []
    start = 0
    while start < len(logs):
        end = start + chunk_size
        chunks.append(logs[start:end])
        start = end - overlap
    return chunks

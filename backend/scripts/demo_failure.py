#!/usr/bin/env python3
"""Send a sample failure log to the local API for a quick demo."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[2]
SAMPLE = ROOT / "data" / "sample_failures" / "npm_network_timeout.log"
API = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"


def main() -> None:
    logs = SAMPLE.read_text(encoding="utf-8") if SAMPLE.exists() else (
        "Error: connect ETIMEDOUT registry.npmjs.org\nnpm ERR! network Temporary failure\n"
    )
    payload = {
        "repo": "demo/devops-copilot",
        "workflow_name": "CI",
        "job_name": "build",
        "branch": "main",
        "raw_logs": logs,
    }
    resp = httpx.post(f"{API}/api/v1/failures/diagnose", json=payload, timeout=120.0)
    resp.raise_for_status()
    print(json.dumps(resp.json(), indent=2))


if __name__ == "__main__":
    main()

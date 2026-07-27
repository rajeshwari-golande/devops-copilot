#!/usr/bin/env python3
"""
Fetch recent FAILED GitHub Actions logs from public repos (free GitHub API).

Requires GITHUB_TOKEN (fine-grained or classic with public_repo / actions:read).

Usage:
  $env:PYTHONPATH="backend"
  $env:GITHUB_TOKEN="ghp_..."
  python backend/scripts/fetch_public_failures.py --repos actions/runner,pallets/flask --limit 3

Saves logs under data/real_failures/ and appends unlabeled stubs to
data/eval/fetched_index.json for later manual labeling into ground_truth.json.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

# Ensure token is visible to settings before import side-effects
from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")


async def _run(repos: list[str], limit: int) -> None:
    from app.config import get_settings
    from app.services.github import fetch_workflow_run_logs, list_failed_runs

    get_settings.cache_clear()
    settings = get_settings()
    if not settings.github_token:
        # allow env override without .env
        token = os.environ.get("GITHUB_TOKEN", "")
        if token:
            os.environ["GITHUB_TOKEN"] = token
            get_settings.cache_clear()
            settings = get_settings()
    if not settings.github_token:
        print("GITHUB_TOKEN required")
        raise SystemExit(1)

    out_dir = ROOT / "data" / "real_failures"
    out_dir.mkdir(parents=True, exist_ok=True)
    index_path = ROOT / "data" / "eval" / "fetched_index.json"
    index = {"fetched_at": datetime.now(timezone.utc).isoformat(), "items": []}

    for full in repos:
        if "/" not in full:
            print(f"skip invalid repo {full}")
            continue
        owner, _, name = full.partition("/")
        runs = await list_failed_runs(owner, name, per_page=limit)
        print(f"{full}: {len(runs)} failed runs")
        for run in runs[:limit]:
            run_id = str(run.get("id"))
            logs = await fetch_workflow_run_logs(owner, name, run_id)
            fname = f"{owner}_{name}_{run_id}.log"
            (out_dir / fname).write_text(logs, encoding="utf-8", errors="replace")
            index["items"].append(
                {
                    "repo": full,
                    "run_id": run_id,
                    "workflow": run.get("name"),
                    "html_url": run.get("html_url"),
                    "log_file": f"data/real_failures/{fname}",
                    "expected_classification": None,
                    "note": "Manually label and promote into ground_truth.json",
                }
            )
            print(f"  saved {fname} ({len(logs)} chars)")

    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.write_text(json.dumps(index, indent=2), encoding="utf-8")
    print(f"Index: {index_path}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--repos",
        default="actions/checkout,pallets/flask",
        help="Comma-separated owner/name list",
    )
    parser.add_argument("--limit", type=int, default=3)
    args = parser.parse_args()
    repos = [r.strip() for r in args.repos.split(",") if r.strip()]
    asyncio.run(_run(repos, args.limit))


if __name__ == "__main__":
    main()

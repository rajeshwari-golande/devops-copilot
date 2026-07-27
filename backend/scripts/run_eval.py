#!/usr/bin/env python3
"""
Evaluate the diagnosis agent against the labeled ground-truth set.

Usage (from repo root):
  $env:PYTHONPATH="backend"
  python backend/scripts/run_eval.py

Writes data/eval/latest_results.json and prints accuracy suitable for README / interviews.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.agent.graph import run_diagnosis  # noqa: E402
from app.rag.ingestion import seed_knowledge_base  # noqa: E402
from app.taxonomy import normalize_classification  # noqa: E402

GT_PATH = ROOT / "data" / "eval" / "ground_truth.json"
OUT_PATH = ROOT / "data" / "eval" / "latest_results.json"


def _load_log(case: dict) -> str:
    if case.get("inline_log"):
        return case["inline_log"]
    rel = case.get("log_file")
    if not rel:
        return ""
    path = ROOT / rel
    return path.read_text(encoding="utf-8") if path.exists() else ""


def main() -> int:
    seed_knowledge_base(force=False)
    payload = json.loads(GT_PATH.read_text(encoding="utf-8"))
    cases = payload["cases"]
    rows = []
    correct_class = 0
    correct_action = 0
    scored_action = 0

    for case in cases:
        logs = _load_log(case)
        if not logs.strip():
            rows.append({"id": case["id"], "error": "missing_log"})
            continue
        result = run_diagnosis(logs)
        pred = normalize_classification(result.get("classification"))
        expected = normalize_classification(case.get("expected_classification"))
        class_ok = pred == expected
        if class_ok:
            correct_class += 1

        expected_action = (case.get("expected_action") or "none").strip()
        pred_action = (result.get("remediation_action") or "none").strip()
        # Map needs_approval ~ none for scoring when expected is none
        action_ok = pred_action == expected_action or (
            expected_action == "none" and pred_action in {"none", "needs_approval"}
        )
        if expected_action != "skip":
            scored_action += 1
            if action_ok:
                correct_action += 1

        rows.append(
            {
                "id": case["id"],
                "expected_classification": expected,
                "predicted_classification": pred,
                "classification_correct": class_ok,
                "expected_action": expected_action,
                "predicted_action": pred_action,
                "action_correct": action_ok,
                "confidence": result.get("confidence"),
            }
        )

    n = len([r for r in rows if "error" not in r])
    class_acc = (correct_class / n) if n else 0.0
    action_acc = (correct_action / scored_action) if scored_action else None
    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "n_cases": n,
        "classification_correct": correct_class,
        "classification_accuracy": round(class_acc, 4),
        "action_correct": correct_action,
        "action_accuracy": round(action_acc, 4) if action_acc is not None else None,
        "headline": (
            f"Correctly diagnosed root-cause class in {correct_class}/{n} "
            f"({class_acc:.0%}) of labeled CI failures"
        ),
        "cases": rows,
    }
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(summary["headline"])
    if action_acc is not None:
        print(f"Safe-action agreement: {correct_action}/{scored_action} ({action_acc:.0%})")
    print(f"Wrote {OUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

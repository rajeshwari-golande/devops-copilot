"""Dashboard aggregate stats for the React frontend."""

from collections import Counter
import json

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import ROOT_DIR
from app.db.models import Feedback, PipelineFailure
from app.db.session import get_db
from app.models.schemas import DashboardStats, FailureOut

router = APIRouter()
EVAL_RESULTS = ROOT_DIR / "data" / "eval" / "latest_results.json"


def _load_eval_metrics() -> tuple[float | None, str | None, int | None]:
    if not EVAL_RESULTS.exists():
        return None, None, None
    try:
        data = json.loads(EVAL_RESULTS.read_text(encoding="utf-8"))
        return (
            data.get("classification_accuracy"),
            data.get("headline"),
            data.get("n_cases"),
        )
    except Exception:  # noqa: BLE001
        return None, None, None


@router.get("/dashboard/stats", response_model=DashboardStats)
async def dashboard_stats(db: AsyncSession = Depends(get_db)):
    total = (await db.execute(select(func.count(PipelineFailure.id)))).scalar() or 0
    diagnosed = (
        await db.execute(
            select(func.count(PipelineFailure.id)).where(
                PipelineFailure.status.in_(
                    ["diagnosed", "remediated", "awaiting_approval", "resolved"]
                )
            )
        )
    ).scalar() or 0
    auto_remediated = (
        await db.execute(
            select(func.count(PipelineFailure.id)).where(PipelineFailure.auto_applied.is_(True))
        )
    ).scalar() or 0
    awaiting = (
        await db.execute(
            select(func.count(PipelineFailure.id)).where(
                PipelineFailure.status == "awaiting_approval"
            )
        )
    ).scalar() or 0
    feedback_count = (await db.execute(select(func.count(Feedback.id)))).scalar() or 0
    correct = (
        await db.execute(select(func.count(Feedback.id)).where(Feedback.is_correct.is_(True)))
    ).scalar() or 0
    # Prefer labeled eval accuracy when available; else engineer feedback ratio
    eval_acc, eval_headline, eval_n = _load_eval_metrics()
    accuracy = eval_acc if eval_acc is not None else (
        (correct / feedback_count) if feedback_count else None
    )

    class_rows = (
        await db.execute(
            select(PipelineFailure.classification, func.count(PipelineFailure.id)).group_by(
                PipelineFailure.classification
            )
        )
    ).all()
    by_classification = {(c or "unknown"): n for c, n in class_rows if c or n}
    if "" in by_classification:
        by_classification["unknown"] = by_classification.pop("") + by_classification.get(
            "unknown", 0
        )

    recent = (
        await db.execute(select(PipelineFailure).order_by(PipelineFailure.id.desc()).limit(10))
    ).scalars().all()

    return DashboardStats(
        total_failures=total,
        diagnosed=diagnosed,
        auto_remediated=auto_remediated,
        awaiting_approval=awaiting,
        feedback_count=feedback_count,
        accuracy_estimate=accuracy,
        eval_accuracy=eval_acc,
        eval_headline=eval_headline,
        eval_n_cases=eval_n,
        by_classification=dict(Counter(by_classification)),
        recent_failures=[FailureOut.model_validate(r) for r in recent],
    )

"""Dashboard aggregate stats for the React frontend."""

from collections import Counter

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Feedback, PipelineFailure
from app.db.session import get_db
from app.models.schemas import DashboardStats, FailureOut

router = APIRouter()


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
    accuracy = (correct / feedback_count) if feedback_count else None

    class_rows = (
        await db.execute(
            select(PipelineFailure.classification, func.count(PipelineFailure.id)).group_by(
                PipelineFailure.classification
            )
        )
    ).all()
    by_classification = {
        (c or "unknown"): n for c, n in class_rows if c or n
    }
    # Normalize empty key
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
        by_classification=dict(Counter(by_classification)),
        recent_failures=[FailureOut.model_validate(r) for r in recent],
    )

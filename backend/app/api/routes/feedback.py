"""Engineer feedback loop → updates knowledge base."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Feedback, PipelineFailure
from app.db.session import get_db
from app.models.schemas import FeedbackCreate, FeedbackOut
from app.rag.ingestion import ingest_feedback_as_knowledge

router = APIRouter()


@router.post("/feedback", response_model=FeedbackOut)
async def submit_feedback(body: FeedbackCreate, db: AsyncSession = Depends(get_db)):
    failure = await db.get(PipelineFailure, body.failure_id)
    if not failure:
        raise HTTPException(status_code=404, detail="Failure not found")

    fb = Feedback(
        failure_id=body.failure_id,
        is_correct=body.is_correct,
        engineer_notes=body.engineer_notes,
        corrected_root_cause=body.corrected_root_cause,
        corrected_fix=body.corrected_fix,
    )
    db.add(fb)
    await db.commit()
    await db.refresh(fb)

    # When engineer corrects a diagnosis, ingest into Chroma for future RAG hits
    if not body.is_correct and (body.corrected_root_cause or body.corrected_fix):
        root = body.corrected_root_cause or failure.root_cause or ""
        fix = body.corrected_fix or failure.suggested_fix or ""
        ingest_feedback_as_knowledge(
            failure_logs=failure.raw_logs or failure.error_summary or "",
            root_cause=root,
            fix=fix,
            classification=failure.classification or "engineer_corrected",
        )

    return FeedbackOut.model_validate(fb)

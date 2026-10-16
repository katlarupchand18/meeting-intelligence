from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.commitment import Commitment
from app.models.decision import Decision
from app.models.evidence import Evidence
from app.models.meeting import Meeting
from app.schemas.analysis import (
    AnalysisResponse,
    MeetingAnalysisResponse,
)
from app.services.analysis_service import analysis_service


router = APIRouter(
    prefix="/analysis",
    tags=["Analysis"],
)


@router.post(
    "/meetings/{meeting_id}",
    response_model=MeetingAnalysisResponse,
)
async def analyze_meeting(
    meeting_id: UUID,
    db: Session = Depends(get_db),
):
    try:
        return await analysis_service.analyze_meeting(
            db=db,
            meeting_id=meeting_id,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc

    except RuntimeError as exc:
        raise HTTPException(
            status_code=503,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Meeting analysis failed: {str(exc)}",
        ) from exc


@router.get(
    "/meetings/{meeting_id}/summary",
    response_model=MeetingAnalysisResponse,
)
def get_analysis_summary(
    meeting_id: UUID,
    db: Session = Depends(get_db),
):
    meeting = db.scalar(
        select(Meeting).where(
            Meeting.id == meeting_id
        )
    )

    if meeting is None:
        raise HTTPException(
            status_code=404,
            detail="Meeting not found.",
        )

    decisions = list(
        db.scalars(
            select(Decision)
            .where(Decision.meeting_id == meeting_id)
            .order_by(Decision.created_at.asc())
        ).all()
    )

    commitments = list(
        db.scalars(
            select(Commitment)
            .where(Commitment.meeting_id == meeting_id)
            .order_by(Commitment.created_at.asc())
        ).all()
    )

    evidence = list(
        db.scalars(
            select(Evidence)
            .where(Evidence.meeting_id == meeting_id)
            .order_by(Evidence.created_at.asc())
        ).all()
    )

    # Read the already-saved analysis records.
    # This endpoint must never invoke the LLM.
    confidence_values = [
        float(item.confidence or 0.0)
        for item in [*decisions, *commitments, *evidence]
    ]

    overall_confidence = (
        sum(confidence_values) / len(confidence_values)
        if confidence_values
        else 0.0
    )

    return MeetingAnalysisResponse(
        meeting_id=meeting_id,
        summary=meeting.summary or "",
        key_topics=[],
        decisions=[
            {
                "id": str(item.id),
                "meeting_id": str(item.meeting_id),
                "title": item.title,
                "description": item.description,
                "status": (
                    item.status.value
                    if hasattr(item.status, "value")
                    else str(item.status)
                ),
                "confidence": float(item.confidence or 0.0),
                "changed_from_decision_id": (
                    str(item.changed_from_decision_id)
                    if item.changed_from_decision_id
                    else None
                ),
                "created_at": (
                    item.created_at.isoformat()
                    if item.created_at
                    else None
                ),
            }
            for item in decisions
        ],
        commitments=[
            {
                "id": str(item.id),
                "meeting_id": str(item.meeting_id),
                "task": item.task,
                "owner_id": (
                    str(item.owner_id)
                    if item.owner_id
                    else None
                ),
                "deadline": (
                    item.deadline.isoformat()
                    if item.deadline
                    else None
                ),
                "deadline_text": item.deadline_text,
                "strength": (
                    item.strength.value
                    if hasattr(item.strength, "value")
                    else str(item.strength)
                ),
                "status": (
                    item.status.value
                    if hasattr(item.status, "value")
                    else str(item.status)
                ),
                "confidence": float(item.confidence or 0.0),
                "notes": item.notes,
                "created_at": (
                    item.created_at.isoformat()
                    if item.created_at
                    else None
                ),
                "updated_at": (
                    item.updated_at.isoformat()
                    if item.updated_at
                    else None
                ),
            }
            for item in commitments
        ],
        evidence=[
            {
                "id": str(item.id),
                "meeting_id": str(item.meeting_id),
                "transcript_segment_id": (
                    str(item.transcript_segment_id)
                    if item.transcript_segment_id
                    else None
                ),
                "commitment_id": (
                    str(item.commitment_id)
                    if item.commitment_id
                    else None
                ),
                "decision_id": (
                    str(item.decision_id)
                    if item.decision_id
                    else None
                ),
                "evidence_type": (
                    item.evidence_type.value
                    if hasattr(item.evidence_type, "value")
                    else str(item.evidence_type)
                ),
                "snippet": item.snippet,
                "confidence": float(item.confidence or 0.0),
                "created_at": (
                    item.created_at.isoformat()
                    if item.created_at
                    else None
                ),
            }
            for item in evidence
        ],
        overall_confidence=overall_confidence,
        processing_status=(
            "completed"
            if meeting.summary or decisions or commitments
            else "pending"
        ),
    )
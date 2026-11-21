from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.services.meeting_relationship_service import compare_meetings


router = APIRouter(
    prefix="/meeting-relationships",
    tags=["Meeting Relationships"],
)


class MeetingComparisonRequest(BaseModel):
    meeting_a_id: UUID
    meeting_b_id: UUID


class RelationshipEvidence(BaseModel):
    segment_id: str
    meeting_index: int
    quote: str | None = None
    explanation: str


class MeetingComparisonResponse(BaseModel):
    meeting_a: str
    meeting_b: str
    relationship: str
    confidence: float = Field(ge=0, le=1)
    explanation: str
    evidence: list[RelationshipEvidence]
    requires_review: bool
    saved: bool


@router.post(
    "/compare",
    response_model=MeetingComparisonResponse,
)
def compare_meeting_relationships(
    data: MeetingComparisonRequest,
    db: Session = Depends(get_db),
):
    if data.meeting_a_id == data.meeting_b_id:
        raise HTTPException(
            status_code=400,
            detail="Choose two different meetings.",
        )

    try:
        return compare_meetings(
            db=db,
            meeting_a_id=data.meeting_a_id,
            meeting_b_id=data.meeting_b_id,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=404
            if "not found" in str(exc).lower()
            else 400,
            detail=str(exc),
        ) from exc

    except RuntimeError as exc:
        raise HTTPException(
            status_code=503,
            detail="Meeting comparison AI is unavailable.",
        ) from exc

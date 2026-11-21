from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.services.followup_service import generate_meeting_followup


router = APIRouter(
    prefix="/followups",
    tags=["Meeting Follow-ups"],
)


@router.post("/meeting/{meeting_id}")
async def generate_followup(
    meeting_id: UUID,
    db: Session = Depends(get_db),
):
    try:
        result = await generate_meeting_followup(
            db=db,
            meeting_id=meeting_id,
        )
    except RuntimeError as exc:
        raise HTTPException(
            status_code=503,
            detail=str(exc),
        ) from exc

    if result is None:
        raise HTTPException(
            status_code=404,
            detail="Meeting not found.",
        )

    return result

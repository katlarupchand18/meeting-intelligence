from uuid import UUID
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.services.reminder_service import get_reminder_preview, get_reminders_by_meeting


router = APIRouter(
    prefix="/reminders",
    tags=["Reminders"],
)


@router.get("/preview")
def preview_reminders(
    days_ahead: int = Query(default=7, ge=1, le=90),
    db: Session = Depends(get_db),
):
    return get_reminder_preview(db, days_ahead=days_ahead)


@router.get("/by-meeting")
def reminders_by_meeting(
    days_ahead: int = Query(default=7, ge=1, le=90),
    meeting_id: UUID | None = Query(default=None),
    db: Session = Depends(get_db),
):
    return get_reminders_by_meeting(db, days_ahead=days_ahead, meeting_id=meeting_id)

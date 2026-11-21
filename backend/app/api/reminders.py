from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.services.reminder_service import get_reminder_preview


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

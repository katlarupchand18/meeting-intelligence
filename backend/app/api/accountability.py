from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.schemas.accountability import (
    AccountabilityOverviewResponse,
)
from app.services.accountability_service import (
    accountability_service,
)


router = APIRouter(
    prefix="/accountability",
    tags=["Accountability"],
)


@router.get(
    "",
    response_model=AccountabilityOverviewResponse,
)
def get_accountability(
    meeting_id: UUID | None = None,
    db: Session = Depends(get_db),
):

    try:
        return accountability_service.get_overview(
            db=db,
            meeting_id=meeting_id,
        )

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=(
                "Failed to load accountability data: "
                f"{str(exc)}"
            ),
        ) from exc


@router.get(
    "/summary",
)
def get_accountability_summary(
    meeting_id: UUID | None = None,
    db: Session = Depends(get_db),
):

    try:
        return accountability_service.get_summary(
            db=db,
            meeting_id=meeting_id,
        )

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=(
                "Failed to load accountability summary: "
                f"{str(exc)}"
            ),
        ) from exc
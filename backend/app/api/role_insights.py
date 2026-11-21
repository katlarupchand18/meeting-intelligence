from uuid import UUID
from app.services.person_insights_service import get_person_insights

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.services.role_insights_service import get_participant_insights


router = APIRouter(
    prefix="/insights",
    tags=["Role-Specific Insights"],
)


@router.get("/participants/{participant_id}")
def participant_insights(
    participant_id: UUID,
    db: Session = Depends(get_db),
):
    result = get_participant_insights(db, participant_id)

    if result is None:
        raise HTTPException(
            status_code=404,
            detail="Participant not found.",
        )

    return result



@router.get("/people/{person_id}")
def person_insights(
    person_id: UUID,
    db: Session = Depends(get_db),
):
    result = get_person_insights(db, person_id)

    if result is None:
        raise HTTPException(
            status_code=404,
            detail="Person not found.",
        )

    return result

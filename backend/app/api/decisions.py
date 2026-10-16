from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.schemas.decision import (
    DecisionCreate,
    DecisionResponse,
    DecisionUpdate,
)
from app.services.decision_service import (
    decision_service,
)


router = APIRouter(
    prefix="/decisions",
    tags=["Decisions"],
)


# ---------------------------------------------------------
# Create Decision
# ---------------------------------------------------------

@router.post(
    "",
    response_model=DecisionResponse,
)
def create_decision(
    data: DecisionCreate,
    db: Session = Depends(get_db),
):

    try:
        return decision_service.create_decision(
            db,
            data,
        )

    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


# ---------------------------------------------------------
# Get Decision
# ---------------------------------------------------------

@router.get(
    "/{decision_id}",
    response_model=DecisionResponse,
)
def get_decision(
    decision_id: UUID,
    db: Session = Depends(get_db),
):

    decision = decision_service.get_decision(
        db,
        decision_id,
    )

    if decision is None:
        raise HTTPException(
            status_code=404,
            detail="Decision not found.",
        )

    return decision


# ---------------------------------------------------------
# Meeting Decisions
# ---------------------------------------------------------

@router.get(
    "/meeting/{meeting_id}",
    response_model=list[DecisionResponse],
)
def get_meeting_decisions(
    meeting_id: UUID,
    db: Session = Depends(get_db),
):

    return decision_service.get_meeting_decisions(
        db,
        meeting_id,
    )


# ---------------------------------------------------------
# Final Decisions
# ---------------------------------------------------------

@router.get(
    "/meeting/{meeting_id}/final",
    response_model=list[DecisionResponse],
)
def get_final_decisions(
    meeting_id: UUID,
    db: Session = Depends(get_db),
):

    return decision_service.get_final_decisions(
        db,
        meeting_id,
    )


# ---------------------------------------------------------
# Update
# ---------------------------------------------------------

@router.patch(
    "/{decision_id}",
    response_model=DecisionResponse,
)
def update_decision(
    decision_id: UUID,
    data: DecisionUpdate,
    db: Session = Depends(get_db),
):

    decision = decision_service.get_decision(
        db,
        decision_id,
    )

    if decision is None:
        raise HTTPException(
            status_code=404,
            detail="Decision not found.",
        )

    return decision_service.update_decision(
        db,
        decision,
        data,
    )


# ---------------------------------------------------------
# Delete
# ---------------------------------------------------------

@router.delete(
    "/{decision_id}",
)
def delete_decision(
    decision_id: UUID,
    db: Session = Depends(get_db),
):

    decision = decision_service.get_decision(
        db,
        decision_id,
    )

    if decision is None:
        raise HTTPException(
            status_code=404,
            detail="Decision not found.",
        )

    decision_service.delete_decision(
        db,
        decision,
    )

    return {
        "success": True,
        "message": (
            "Decision deleted successfully."
        ),
    }
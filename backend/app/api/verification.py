from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, model_validator
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.schemas.verification import (
    VerificationAction,
    DecisionVerificationEdit,
    CommitmentVerificationEdit,
)
from app.services.verification_service import verification_service


router = APIRouter(
    prefix="/verification",
    tags=["Human-AI Verification"],
)


class DecisionReviewRequest(BaseModel):
    action: VerificationAction
    reviewer_id: str = Field(min_length=1, max_length=255)
    edits: DecisionVerificationEdit | None = None

    @model_validator(mode="after")
    def validate_edits(self):
        values = (
            self.edits.model_dump(exclude_unset=True)
            if self.edits else {}
        )

        if self.action == VerificationAction.EDITED and not values:
            raise ValueError("At least one edit is required.")

        if self.action != VerificationAction.EDITED and values:
            raise ValueError("Edits require the edited action.")

        return self


class CommitmentReviewRequest(BaseModel):
    action: VerificationAction
    reviewer_id: str = Field(min_length=1, max_length=255)
    edits: CommitmentVerificationEdit | None = None

    @model_validator(mode="after")
    def validate_edits(self):
        values = (
            self.edits.model_dump(exclude_unset=True)
            if self.edits else {}
        )

        if self.action == VerificationAction.EDITED and not values:
            raise ValueError("At least one edit is required.")

        if self.action != VerificationAction.EDITED and values:
            raise ValueError("Edits require the edited action.")

        return self


def execute_review(
    db: Session,
    item_type: str,
    item_id: UUID,
    action: VerificationAction,
    reviewer_id: str,
    edits: dict | None,
):
    try:
        item = verification_service.review(
            db=db,
            item_type=item_type,
            item_id=item_id,
            action=action.value,
            reviewer_id=reviewer_id,
            edits=edits,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc

    if item is None:
        raise HTTPException(
            status_code=404,
            detail=f"{item_type.capitalize()} not found.",
        )

    return {
        "success": True,
        "item_type": item_type,
        "item_id": str(item.id),
        "verification_status": item.verification_status,
        "verified_by": item.verified_by,
        "verified_at": (
            item.verified_at.isoformat()
            if item.verified_at else None
        ),
    }


@router.post("/decisions/{decision_id}")
def review_decision(
    decision_id: UUID,
    data: DecisionReviewRequest,
    db: Session = Depends(get_db),
):
    return execute_review(
        db,
        "decision",
        decision_id,
        data.action,
        data.reviewer_id,
        (
            data.edits.model_dump(exclude_unset=True)
            if data.edits else None
        ),
    )


@router.post("/commitments/{commitment_id}")
def review_commitment(
    commitment_id: UUID,
    data: CommitmentReviewRequest,
    db: Session = Depends(get_db),
):
    return execute_review(
        db,
        "commitment",
        commitment_id,
        data.action,
        data.reviewer_id,
        (
            data.edits.model_dump(exclude_unset=True)
            if data.edits else None
        ),
    )

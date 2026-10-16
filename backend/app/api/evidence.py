from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.schemas.evidence import EvidenceResponse
from app.services.evidence_service import (
    evidence_service,
)


router = APIRouter(
    prefix="/evidence",
    tags=["Evidence"],
)


# ---------------------------------------------------------
# Meeting Evidence
# ---------------------------------------------------------

@router.get(
    "/meeting/{meeting_id}",
    response_model=list[EvidenceResponse],
)
def get_meeting_evidence(
    meeting_id: UUID,
    db: Session = Depends(get_db),
):

    return evidence_service.get_meeting_evidence(
        db,
        meeting_id,
    )


# ---------------------------------------------------------
# Commitment Evidence
# ---------------------------------------------------------

@router.get(
    "/commitment/{commitment_id}",
    response_model=list[EvidenceResponse],
)
def get_commitment_evidence(
    commitment_id: UUID,
    db: Session = Depends(get_db),
):

    return evidence_service.get_commitment_evidence(
        db,
        commitment_id,
    )


# ---------------------------------------------------------
# Decision Evidence
# ---------------------------------------------------------

@router.get(
    "/decision/{decision_id}",
    response_model=list[EvidenceResponse],
)
def get_decision_evidence(
    decision_id: UUID,
    db: Session = Depends(get_db),
):

    return evidence_service.get_decision_evidence(
        db,
        decision_id,
    )


# ---------------------------------------------------------
# Delete Evidence
# ---------------------------------------------------------

@router.delete(
    "/{evidence_id}",
)
def delete_evidence(
    evidence_id: UUID,
    db: Session = Depends(get_db),
):

    from sqlalchemy import select
    from app.models.evidence import Evidence

    evidence = db.scalar(
        select(Evidence).where(
            Evidence.id == evidence_id
        )
    )

    if evidence is None:
        raise HTTPException(
            status_code=404,
            detail="Evidence not found.",
        )

    evidence_service.delete_evidence(
        db,
        evidence,
    )

    return {
        "success": True,
        "message": (
            "Evidence deleted successfully."
        ),
    }
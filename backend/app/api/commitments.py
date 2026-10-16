from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.schemas.commitment import (
    CommitmentCreate,
    CommitmentResponse,
    CommitmentUpdate,
)
from app.services.commitment_service import (
    commitment_service,
)


router = APIRouter(
    prefix="/commitments",
    tags=["Commitments"],
)


# ---------------------------------------------------------
# Create
# ---------------------------------------------------------

@router.post(
    "",
    response_model=CommitmentResponse,
)
def create_commitment(
    data: CommitmentCreate,
    db: Session = Depends(get_db),
):

    try:
        return commitment_service.create_commitment(
            db,
            data,
        )

    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


# ---------------------------------------------------------
# Get One
# ---------------------------------------------------------

@router.get(
    "/{commitment_id}",
    response_model=CommitmentResponse,
)
def get_commitment(
    commitment_id: UUID,
    db: Session = Depends(get_db),
):

    commitment = (
        commitment_service.get_commitment(
            db,
            commitment_id,
        )
    )

    if commitment is None:
        raise HTTPException(
            status_code=404,
            detail="Commitment not found.",
        )

    return commitment


# ---------------------------------------------------------
# Meeting Commitments
# ---------------------------------------------------------

@router.get(
    "/meeting/{meeting_id}",
    response_model=list[CommitmentResponse],
)
def get_meeting_commitments(
    meeting_id: UUID,
    db: Session = Depends(get_db),
):

    return commitment_service.get_meeting_commitments(
        db,
        meeting_id,
    )


# ---------------------------------------------------------
# Update
# ---------------------------------------------------------

@router.patch(
    "/{commitment_id}",
    response_model=CommitmentResponse,
)
def update_commitment(
    commitment_id: UUID,
    data: CommitmentUpdate,
    db: Session = Depends(get_db),
):

    commitment = (
        commitment_service.get_commitment(
            db,
            commitment_id,
        )
    )

    if commitment is None:
        raise HTTPException(
            status_code=404,
            detail="Commitment not found.",
        )

    return commitment_service.update_commitment(
        db,
        commitment,
        data,
    )


# ---------------------------------------------------------
# Refresh Overdue
# ---------------------------------------------------------

@router.post(
    "/refresh-overdue",
)
def refresh_overdue(
    db: Session = Depends(get_db),
):

    count = (
        commitment_service.refresh_all_overdue(
            db
        )
    )

    return {
        "success": True,
        "updated": count,
        "message": (
            f"{count} commitment(s) "
            "updated as overdue."
        ),
    }


# ---------------------------------------------------------
# Statistics
# ---------------------------------------------------------

@router.get(
    "/statistics/overview",
)
def commitment_statistics(
    meeting_id: UUID | None = None,
    db: Session = Depends(get_db),
):

    return commitment_service.get_statistics(
        db,
        meeting_id,
    )


# ---------------------------------------------------------
# Delete
# ---------------------------------------------------------

@router.delete(
    "/{commitment_id}",
)
def delete_commitment(
    commitment_id: UUID,
    db: Session = Depends(get_db),
):

    commitment = (
        commitment_service.get_commitment(
            db,
            commitment_id,
        )
    )

    if commitment is None:
        raise HTTPException(
            status_code=404,
            detail="Commitment not found.",
        )

    commitment_service.delete_commitment(
        db,
        commitment,
    )

    return {
        "success": True,
        "message": (
            "Commitment deleted successfully."
        ),
    }
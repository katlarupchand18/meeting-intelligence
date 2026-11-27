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
# List All Commitments
# ---------------------------------------------------------
@router.get(
    "",
    response_model=list[CommitmentResponse],
)
def list_all_commitments(
    db: Session = Depends(get_db),
):
    from sqlalchemy import select
    from app.models.commitment import Commitment

    return list(
        db.scalars(
            select(Commitment)
            .order_by(Commitment.created_at.desc())
            .limit(500)
        ).all()
    )


# ---------------------------------------------------------
# Action Tracker — commitments with meeting and owner names
# ---------------------------------------------------------
@router.get("/tracker")
def list_action_tracker(
    db: Session = Depends(get_db),
):
    from sqlalchemy import select
    from app.models.commitment import Commitment
    from app.models.meeting import Meeting
    from app.models.participant import Participant

    rows = db.execute(
        select(
            Commitment,
            Meeting.title,
            Participant.name,
        )
        .join(Meeting, Commitment.meeting_id == Meeting.id)
        .outerjoin(Participant, Commitment.owner_id == Participant.id)
        .order_by(Commitment.created_at.desc())
        .limit(500)
    ).all()

    return [
        {
            "id": str(commitment.id),
            "meeting_id": str(commitment.meeting_id),
            "meeting_title": meeting_title,
            "owner_id": str(commitment.owner_id) if commitment.owner_id else None,
            "owner_name": owner_name,
            "task": commitment.task,
            "deadline": commitment.deadline.isoformat() if commitment.deadline else None,
            "deadline_text": commitment.deadline_text,
            "status": commitment.status.value,
            "notes": commitment.notes,
        }
        for commitment, meeting_title, owner_name in rows
    ]


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

    updates = data.model_dump(exclude_unset=True)

    content_fields = {
        "owner_id",
        "task",
        "deadline",
        "deadline_text",
        "strength",
        "notes",
    }

    if (
        commitment.verification_status in {"approved", "rejected"}
        and content_fields.intersection(updates)
    ):
        raise HTTPException(
            status_code=409,
            detail=(
                "This commitment has already been reviewed. "
                "Use the verification workflow to correct its content."
            ),
        )

    if "owner_id" in updates and updates["owner_id"] is not None:
        from sqlalchemy import select
        from app.models.participant import Participant

        participant = db.scalar(
            select(Participant).where(
                Participant.id == updates["owner_id"],
                Participant.meeting_id == commitment.meeting_id,
            )
        )
        if participant is None:
            raise HTTPException(
                status_code=422,
                detail="Owner must be a participant in this meeting.",
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
# Person-filtered Action Tracker
# ---------------------------------------------------------
@router.get("/tracker/person/{person_id}")
def list_action_tracker_by_person(
    person_id: UUID,
    db: Session = Depends(get_db),
):
    from sqlalchemy import select
    from app.models.commitment import Commitment
    from app.models.meeting import Meeting
    from app.models.participant import Participant

    # Get all participants linked to this person
    participants = db.scalars(
        select(Participant).where(Participant.person_id == person_id)
    ).all()

    participant_ids = [p.id for p in participants]

    if not participant_ids:
        return []

    rows = db.execute(
        select(
            Commitment,
            Meeting.title,
            Participant.name,
        )
        .join(Meeting, Commitment.meeting_id == Meeting.id)
        .outerjoin(Participant, Commitment.owner_id == Participant.id)
        .where(Commitment.owner_id.in_(participant_ids))
        .order_by(Commitment.created_at.desc())
        .limit(500)
    ).all()

    return [
        {
            "id": str(commitment.id),
            "meeting_id": str(commitment.meeting_id),
            "meeting_title": meeting_title,
            "owner_id": str(commitment.owner_id) if commitment.owner_id else None,
            "owner_name": owner_name,
            "task": commitment.task,
            "deadline": commitment.deadline.isoformat() if commitment.deadline else None,
            "deadline_text": commitment.deadline_text,
            "status": commitment.status.value,
            "notes": commitment.notes,
        }
        for commitment, meeting_title, owner_name in rows
    ]


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
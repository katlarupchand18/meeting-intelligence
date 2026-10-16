
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.meeting import Meeting
from app.models.participant import Participant
from app.services.participant_service import participant_service


router = APIRouter(
    prefix="/participants",
    tags=["Participants"],
)


class SpeakerMappingRequest(BaseModel):
    speaker_label: str = Field(
        min_length=1,
        max_length=100,
        description="Diarization label, for example SPEAKER_00",
    )


# =========================================================
# GET ALL PARTICIPANTS FOR A MEETING
# =========================================================

@router.get("/meeting/{meeting_id}")
def get_meeting_participants(
    meeting_id: UUID,
    db: Session = Depends(get_db),
):
    meeting = db.scalar(
        select(Meeting).where(Meeting.id == meeting_id)
    )

    if meeting is None:
        raise HTTPException(
            status_code=404,
            detail="Meeting not found.",
        )

    participants = participant_service.get_meeting_participants(
        db=db,
        meeting_id=meeting_id,
    )

    return {
        "success": True,
        "meeting_id": str(meeting_id),
        "participants": [
            participant_service.to_dict(participant)
            for participant in participants
        ],
        "total": len(participants),
    }


# =========================================================
# MAP A SPEAKER LABEL TO A PARTICIPANT
# =========================================================

@router.patch("/{participant_id}/speaker")
def map_participant_speaker(
    participant_id: UUID,
    payload: SpeakerMappingRequest,
    db: Session = Depends(get_db),
):
    participant = db.scalar(
        select(Participant).where(
            Participant.id == participant_id
        )
    )

    if participant is None:
        raise HTTPException(
            status_code=404,
            detail="Participant not found.",
        )

    speaker_label = payload.speaker_label.strip()

    if not speaker_label:
        raise HTTPException(
            status_code=422,
            detail="Speaker label cannot be empty.",
        )

    # A speaker label must not be assigned to two participants
    # in the same meeting.
    existing = db.scalar(
        select(Participant).where(
            Participant.meeting_id == participant.meeting_id,
            Participant.speaker_label == speaker_label,
            Participant.id != participant.id,
        )
    )

    if existing is not None:
        raise HTTPException(
            status_code=409,
            detail=(
                f"{speaker_label} is already mapped to "
                f"participant '{existing.name}'."
            ),
        )

    try:
        participant.speaker_label = speaker_label
        db.commit()
        db.refresh(participant)
    except Exception:
        db.rollback()
        raise

    return {
        "success": True,
        "message": "Speaker mapped to participant.",
        "participant": participant_service.to_dict(participant),
    }


# =========================================================
# REMOVE A SPEAKER MAPPING
# =========================================================

@router.delete("/{participant_id}/speaker")
def clear_participant_speaker(
    participant_id: UUID,
    db: Session = Depends(get_db),
):
    participant = db.scalar(
        select(Participant).where(
            Participant.id == participant_id
        )
    )

    if participant is None:
        raise HTTPException(
            status_code=404,
            detail="Participant not found.",
        )

    try:
        participant.speaker_label = None
        db.commit()
        db.refresh(participant)
    except Exception:
        db.rollback()
        raise

    return {
        "success": True,
        "message": "Speaker mapping cleared.",
        "participant": participant_service.to_dict(participant),
    }


# =========================================================
# GET SINGLE PARTICIPANT
# =========================================================

@router.get("/{participant_id}")
def get_participant(
    participant_id: UUID,
    db: Session = Depends(get_db),
):
    participant = db.scalar(
        select(Participant).where(
            Participant.id == participant_id
        )
    )

    if participant is None:
        raise HTTPException(
            status_code=404,
            detail="Participant not found.",
        )

    return {
        "success": True,
        "participant": participant_service.to_dict(participant),
    }

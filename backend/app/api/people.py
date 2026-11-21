from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.person import Person
from app.models.participant import Participant


router = APIRouter(prefix="/people", tags=["People"])


class CreatePersonRequest(BaseModel):
    display_name: str = Field(min_length=1, max_length=255)


def serialize_participant(participant):
    return {
        "id": str(participant.id),
        "meeting_id": str(participant.meeting_id),
        "name": participant.name,
        "person_id": (
            str(participant.person_id)
            if participant.person_id
            else None
        ),
    }


def serialize_person(person):
    return {
        "id": str(person.id),
        "display_name": person.display_name,
        "created_at": (
            person.created_at.isoformat()
            if person.created_at
            else None
        ),
    }


@router.post("", status_code=201)
def create_person(
    payload: CreatePersonRequest,
    db: Session = Depends(get_db),
):
    name = payload.display_name.strip()

    if not name:
        raise HTTPException(
            status_code=422,
            detail="Display name cannot be empty.",
        )

    person = Person(display_name=name)

    db.add(person)
    db.commit()
    db.refresh(person)

    return serialize_person(person)


@router.get("")
def list_people(db: Session = Depends(get_db)):
    people = db.scalars(
        select(Person).order_by(Person.display_name)
    ).all()

    return {
        "success": True,
        "people": [serialize_person(person) for person in people],
        "total": len(people),
    }


@router.get("/{person_id}")
def get_person(
    person_id: UUID,
    db: Session = Depends(get_db),
):
    person = db.get(Person, person_id)

    if person is None:
        raise HTTPException(
            status_code=404,
            detail="Person not found.",
        )

    participants = db.scalars(
        select(Participant).where(
            Participant.person_id == person_id
        )
    ).all()

    return {
        **serialize_person(person),
        "participants": [
            serialize_participant(participant)
            for participant in participants
        ],
        "total_participants": len(participants),
    }


@router.post(
    "/{person_id}/participants/{participant_id}"
)
def link_participant(
    person_id: UUID,
    participant_id: UUID,
    db: Session = Depends(get_db),
):
    person = db.get(Person, person_id)

    if person is None:
        raise HTTPException(
            status_code=404,
            detail="Person not found.",
        )

    participant = db.get(Participant, participant_id)

    if participant is None:
        raise HTTPException(
            status_code=404,
            detail="Participant not found.",
        )

    if participant.person_id is not None:
        if participant.person_id == person_id:
            return {
                "success": True,
                "already_linked": True,
                "participant": serialize_participant(participant),
            }

        raise HTTPException(
            status_code=409,
            detail=(
                "Participant already belongs to another person. "
                "Unlink it explicitly before reassignment."
            ),
        )

    participant.person_id = person_id
    db.commit()
    db.refresh(participant)

    return {
        "success": True,
        "already_linked": False,
        "participant": serialize_participant(participant),
    }


@router.delete(
    "/{person_id}/participants/{participant_id}"
)
def unlink_participant(
    person_id: UUID,
    participant_id: UUID,
    db: Session = Depends(get_db),
):
    person = db.get(Person, person_id)

    if person is None:
        raise HTTPException(
            status_code=404,
            detail="Person not found.",
        )

    participant = db.get(Participant, participant_id)

    if participant is None:
        raise HTTPException(
            status_code=404,
            detail="Participant not found.",
        )

    if participant.person_id != person_id:
        raise HTTPException(
            status_code=409,
            detail="Participant is not linked to this person.",
        )

    participant.person_id = None
    db.commit()

    return {
        "success": True,
        "participant_id": str(participant_id),
        "person_id": None,
    }

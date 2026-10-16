
from __future__ import annotations

import re
from datetime import date
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.commitment import (
    Commitment,
    CommitmentStatus,
)
from app.models.participant import Participant
from app.schemas.commitment import (
    CommitmentCreate,
    CommitmentUpdate,
)


class CommitmentService:
    """Commitment management and owner resolution."""

    # ---------------------------------------------------------
    # OWNER NAME MATCHING
    # ---------------------------------------------------------

    @staticmethod
    def normalize_name(name: str) -> str:
        if not name:
            return ""

        normalized = re.sub(
            r"[^a-z0-9\s]",
            " ",
            name.lower().strip(),
        )

        titles = {
            "mr", "mrs", "ms", "miss", "dr",
            "councillor", "councilor", "counselor",
            "mayor", "chair", "chairperson",
        }

        return " ".join(
            word
            for word in normalized.split()
            if word not in titles
        )

    @classmethod
    def names_match(
        cls,
        participant_name: str,
        owner_name: str,
    ) -> bool:
        participant = cls.normalize_name(participant_name)
        owner = cls.normalize_name(owner_name)

        if not participant or not owner:
            return False

        if participant == owner:
            return True

        if owner in participant or participant in owner:
            return True

        participant_parts = participant.split()
        owner_parts = owner.split()

        return (
            len(participant_parts) >= 2
            and bool(owner_parts)
            and len(participant_parts[-1]) >= 3
            and participant_parts[-1] == owner_parts[-1]
        )

    @classmethod
    def find_participant_by_name(
        cls,
        db: Session,
        meeting_id: UUID,
        owner_name: str,
    ) -> Optional[Participant]:
        if not owner_name:
            return None

        participants = list(
            db.scalars(
                select(Participant)
                .where(Participant.meeting_id == meeting_id)
                .order_by(Participant.name)
            ).all()
        )

        normalized_owner = cls.normalize_name(owner_name)

        exact_matches = [
            participant
            for participant in participants
            if cls.normalize_name(participant.name) == normalized_owner
        ]

        if len(exact_matches) == 1:
            return exact_matches[0]

        matches = [
            participant
            for participant in participants
            if cls.names_match(participant.name, owner_name)
        ]

        return matches[0] if len(matches) == 1 else None

    @staticmethod
    def extract_owner_from_notes(
        notes: Optional[str],
    ) -> Optional[str]:
        if not notes:
            return None

        match = re.search(
            r"Owner identified by AI:\s*(.+)",
            notes,
            flags=re.IGNORECASE,
        )

        return match.group(1).strip() if match else None

    @classmethod
    def resolve_commitment_owner(
        cls,
        db: Session,
        commitment: Commitment,
    ) -> Optional[Participant]:
        if commitment.owner_id:
            return db.scalar(
                select(Participant).where(
                    Participant.id == commitment.owner_id
                )
            )

        owner_name = cls.extract_owner_from_notes(commitment.notes)

        if not owner_name:
            return None

        participant = cls.find_participant_by_name(
            db=db,
            meeting_id=commitment.meeting_id,
            owner_name=owner_name,
        )

        if participant:
            commitment.owner_id = participant.id

        return participant

    @classmethod
    def resolve_all_commitment_owners(
        cls,
        db: Session,
        meeting_id: UUID,
    ) -> int:
        commitments = cls.get_meeting_commitments(db, meeting_id)
        resolved_count = 0

        for commitment in commitments:
            if cls.resolve_commitment_owner(db, commitment):
                resolved_count += 1

        db.commit()
        return resolved_count

    # ---------------------------------------------------------
    # CREATE
    # ---------------------------------------------------------

    @staticmethod
    def create_commitment(
        db: Session,
        data: CommitmentCreate,
    ) -> Commitment:
        commitment = Commitment(
            **data.model_dump(exclude_unset=True)
        )

        db.add(commitment)
        db.commit()
        db.refresh(commitment)

        return commitment

    # ---------------------------------------------------------
    # READ
    # ---------------------------------------------------------

    @staticmethod
    def get_commitment(
        db: Session,
        commitment_id: UUID,
    ) -> Optional[Commitment]:
        return db.scalar(
            select(Commitment).where(
                Commitment.id == commitment_id
            )
        )

    @staticmethod
    def get_meeting_commitments(
        db: Session,
        meeting_id: UUID,
    ) -> list[Commitment]:
        return list(
            db.scalars(
                select(Commitment)
                .where(Commitment.meeting_id == meeting_id)
                .order_by(Commitment.created_at.desc())
            ).all()
        )

    # ---------------------------------------------------------
    # UPDATE
    # ---------------------------------------------------------

    @staticmethod
    def update_commitment(
        db: Session,
        commitment: Commitment,
        data: CommitmentUpdate,
    ) -> Commitment:
        updates = data.model_dump(exclude_unset=True)

        for field, value in updates.items():
            setattr(commitment, field, value)

        db.commit()
        db.refresh(commitment)

        return commitment

    # ---------------------------------------------------------
    # OVERDUE TRACKING
    # ---------------------------------------------------------

    @staticmethod
    def refresh_all_overdue(db: Session) -> int:
        today = date.today()
        updated_count = 0

        commitments = list(
            db.scalars(select(Commitment)).all()
        )

        terminal_statuses = {
            CommitmentStatus.COMPLETED,
            CommitmentStatus.CANCELLED,
            CommitmentStatus.OVERDUE,
        }

        for commitment in commitments:
            deadline = commitment.deadline

            if (
                deadline is not None
                and deadline < today
                and commitment.status not in terminal_statuses
            ):
                commitment.status = CommitmentStatus.OVERDUE
                updated_count += 1

        db.commit()
        return updated_count

    # ---------------------------------------------------------
    # STATISTICS
    # ---------------------------------------------------------

    @staticmethod
    def get_statistics(
        db: Session,
        meeting_id: Optional[UUID] = None,
    ) -> dict:
        query = select(Commitment)

        if meeting_id is not None:
            query = query.where(
                Commitment.meeting_id == meeting_id
            )

        commitments = list(db.scalars(query).all())

        status_counts: dict[str, int] = {}

        for commitment in commitments:
            status = commitment.status.value
            status_counts[status] = (
                status_counts.get(status, 0) + 1
            )

        total = len(commitments)
        assigned = sum(
            1
            for commitment in commitments
            if commitment.owner_id is not None
        )

        return {
            "total_commitments": total,
            "owner_assigned": assigned,
            "owner_unassigned": total - assigned,
            "status_counts": status_counts,
        }

    # ---------------------------------------------------------
    # DELETE
    # ---------------------------------------------------------

    @staticmethod
    def delete_commitment(
        db: Session,
        commitment: Commitment,
    ) -> None:
        db.delete(commitment)
        db.commit()


commitment_service = CommitmentService()

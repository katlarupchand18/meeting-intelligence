from __future__ import annotations

from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.commitment import Commitment
from app.models.participant import Participant
from app.services.participant_service import participant_service


class OwnerResolutionService:
    """
    Resolves AI-detected commitment owners to Participant records.

    Flow:

        AI owner text
              ↓
        clean owner name
              ↓
        find existing participant
              ↓
        if not found
              ↓
        create participant
              ↓
        assign participant.id to commitment.owner_id
    """

    # =========================================================
    # CLEAN OWNER TEXT
    # =========================================================

    @staticmethod
    def clean_owner_text(
        owner_text: Optional[str],
    ) -> str:

        if owner_text is None:
            return ""

        value = str(owner_text).strip()

        if not value:
            return ""

        # LLMs sometimes literally return "null"
        if value.lower() in {
            "null",
            "none",
            "unknown",
            "n/a",
            "na",
            "not specified",
            "not mentioned",
            "no owner",
            "unassigned",
        }:
            return ""

        # Remove common AI formatting
        value = value.replace(
            "Owner:",
            "",
        ).strip()

        return value

    # =========================================================
    # SPLIT MULTIPLE OWNERS
    # =========================================================

    @classmethod
    def split_owner_names(
        cls,
        owner_text: Optional[str],
    ) -> list[str]:

        value = cls.clean_owner_text(
            owner_text
        )

        if not value:
            return []

        # Handle common separators.
        #
        # Examples:
        # "Kaczynski and Warren"
        # "Kaczynski, Warren"
        # "Kaczynski & Warren"
        # "Kaczynski / Warren"

        import re

        value = re.sub(
            r"\s+(?:and|&)\s+",
            ",",
            value,
            flags=re.IGNORECASE,
        )

        value = re.sub(
            r"\s*/\s*",
            ",",
            value,
        )

        names = [
            item.strip()
            for item in value.split(",")
            if item.strip()
        ]

        return names

    # =========================================================
    # FIND EXISTING PARTICIPANT
    # =========================================================

    @staticmethod
    def find_existing_participant(
        db: Session,
        meeting_id: UUID,
        owner_name: str,
    ) -> Optional[Participant]:

        owner_name = (
            owner_name.strip()
        )

        if not owner_name:
            return None

        participants = list(
            db.scalars(
                select(Participant)
                .where(
                    Participant.meeting_id
                    == meeting_id
                )
            ).all()
        )

        # First try the project's participant matching
        # logic.

        participant = (
            participant_service.find_participant(
                db=db,
                meeting_id=meeting_id,
                name=owner_name,
            )
        )

        if participant:
            return participant

        # Extra fallback matching.
        normalized_owner = (
            participant_service.normalize_name(
                owner_name
            )
        )

        if not normalized_owner:
            return None

        for participant in participants:

            participant_name = " ".join(
                part
                for part in [
                    getattr(
                        participant,
                        "name",
                        None,
                    ),
                    getattr(
                        participant,
                        "full_name",
                        None,
                    ),
                ]
                if part
            ).strip()

            if not participant_name:
                first_name = getattr(
                    participant,
                    "first_name",
                    "",
                ) or ""

                last_name = getattr(
                    participant,
                    "last_name",
                    "",
                ) or ""

                participant_name = (
                    f"{first_name} "
                    f"{last_name}"
                ).strip()

            if not participant_name:
                continue

            normalized_participant = (
                participant_service.normalize_name(
                    participant_name
                )
            )

            if (
                normalized_owner
                == normalized_participant
            ):
                return participant

            # Last-name matching for names such as:
            # "counselor Warren"
            # "Warren"

            owner_tokens = set(
                participant_service.name_tokens(
                    owner_name
                )
            )

            participant_tokens = set(
                participant_service.name_tokens(
                    participant_name
                )
            )

            if (
                owner_tokens
                and participant_tokens
                and (
                    owner_tokens
                    & participant_tokens
                )
            ):
                # Only accept this fallback when the
                # owner text contains a meaningful token.
                meaningful_owner_tokens = {
                    token
                    for token in owner_tokens
                    if len(token) >= 3
                }

                if (
                    meaningful_owner_tokens
                    & participant_tokens
                ):
                    return participant

        return None

    # =========================================================
    # CREATE PARTICIPANT IF NEEDED
    # =========================================================

    @classmethod
    def ensure_owner_participant(
        cls,
        db: Session,
        meeting_id: UUID,
        owner_name: Optional[str],
    ) -> Optional[Participant]:

        clean_name = cls.clean_owner_text(
            owner_name
        )

        if not clean_name:
            return None

        # Never automatically create a participant from
        # a multi-person owner string.
        #
        # Example:
        # "Kaczynski and Warren"
        #
        # This must be handled separately.

        owner_names = (
            cls.split_owner_names(
                clean_name
            )
        )

        if len(owner_names) != 1:
            return None

        clean_name = owner_names[0]

        # -----------------------------------------------------
        # Try existing participant
        # -----------------------------------------------------

        participant = (
            cls.find_existing_participant(
                db=db,
                meeting_id=meeting_id,
                owner_name=clean_name,
            )
        )

        if participant:
            return participant

        # -----------------------------------------------------
        # Create new participant
        # -----------------------------------------------------

        participant = (
            participant_service.create_participant(
                db=db,
                meeting_id=meeting_id,
                name=clean_name,
                role=None,
                speaker_label=None,
            )
        )

        db.flush()

        return participant

    # =========================================================
    # RESOLVE SINGLE OWNER
    # =========================================================

    @classmethod
    def resolve_owner(
        cls,
        db: Session,
        meeting_id: UUID,
        owner_name: Optional[str],
    ) -> Optional[Participant]:

        clean_name = cls.clean_owner_text(
            owner_name
        )

        if not clean_name:
            return None

        # Only resolve a single owner here.
        #
        # Multi-owner commitments are deliberately left
        # unresolved rather than assigning the wrong person.

        names = cls.split_owner_names(
            clean_name
        )

        if len(names) != 1:
            return None

        return cls.ensure_owner_participant(
            db=db,
            meeting_id=meeting_id,
            owner_name=names[0],
        )

    # =========================================================
    # RESOLVE MULTIPLE OWNERS
    # =========================================================

    @classmethod
    def resolve_owners(
        cls,
        db: Session,
        meeting_id: UUID,
        owner_text: Optional[str],
    ) -> list[Participant]:

        clean_text = cls.clean_owner_text(
            owner_text
        )

        if not clean_text:
            return []

        names = cls.split_owner_names(
            clean_text
        )

        participants: list[
            Participant
        ] = []

        for name in names:

            participant = (
                cls.ensure_owner_participant(
                    db=db,
                    meeting_id=meeting_id,
                    owner_name=name,
                )
            )

            if participant:
                participants.append(
                    participant
                )

        return participants

    # =========================================================
    # ASSIGN OWNER TO COMMITMENT
    # =========================================================

    @classmethod
    def assign_owner(
        cls,
        db: Session,
        commitment: Commitment,
        owner_name: Optional[str],
    ) -> Optional[Participant]:

        clean_name = cls.clean_owner_text(
            owner_name
        )

        if not clean_name:
            commitment.owner_id = None

            # Remove misleading "Owner identified by AI: null"
            if commitment.notes:
                commitment.notes = (
                    "No owner was identified "
                    "with sufficient confidence."
                )

            return None

        participant = cls.resolve_owner(
            db=db,
            meeting_id=commitment.meeting_id,
            owner_name=clean_name,
        )

        if participant:

            commitment.owner_id = (
                participant.id
            )

            commitment.notes = (
                f"Owner identified by AI: "
                f"{clean_name}"
            )

            db.flush()

            return participant

        # -----------------------------------------------------
        # Multiple owners
        # -----------------------------------------------------

        names = cls.split_owner_names(
            clean_name
        )

        if len(names) > 1:

            participants = (
                cls.resolve_owners(
                    db=db,
                    meeting_id=commitment.meeting_id,
                    owner_text=clean_name,
                )
            )

            if len(participants) == 1:

                participant = (
                    participants[0]
                )

                commitment.owner_id = (
                    participant.id
                )

                commitment.notes = (
                    f"Owner identified by AI: "
                    f"{clean_name}"
                )

                db.flush()

                return participant

            # We deliberately do not assign one
            # participant when several people were named.

            commitment.owner_id = None

            commitment.notes = (
                f"Multiple owners identified "
                f"by AI: {clean_name}"
            )

            db.flush()

            return None

        commitment.owner_id = None

        commitment.notes = (
            f"Owner could not be resolved: "
            f"{clean_name}"
        )

        db.flush()

        return None

    # =========================================================
    # RESOLVE ONE COMMITMENT
    # =========================================================

    @classmethod
    def resolve_commitment(
        cls,
        db: Session,
        commitment: Commitment,
    ) -> Optional[Participant]:

        owner_name = None

        # -----------------------------------------------------
        # Read owner from AI-generated notes
        # -----------------------------------------------------

        if commitment.notes:

            prefix = (
                "Owner identified by AI:"
            )

            if commitment.notes.startswith(
                prefix
            ):
                owner_name = (
                    commitment.notes[
                        len(prefix):
                    ].strip()
                )

        # -----------------------------------------------------
        # Remove literal "null"
        # -----------------------------------------------------

        owner_name = cls.clean_owner_text(
            owner_name
        )

        if not owner_name:
            commitment.owner_id = None

            if commitment.notes:
                commitment.notes = (
                    "No owner was identified "
                    "with sufficient confidence."
                )

            db.flush()

            return None

        return cls.assign_owner(
            db=db,
            commitment=commitment,
            owner_name=owner_name,
        )

    # =========================================================
    # RESOLVE ALL MEETING COMMITMENTS
    # =========================================================

    @classmethod
    def resolve_meeting_commitments(
        cls,
        db: Session,
        meeting_id: UUID,
    ) -> int:

        commitments = list(
            db.scalars(
                select(Commitment)
                .where(
                    Commitment.meeting_id
                    == meeting_id
                )
            ).all()
        )

        assigned_count = 0

        for commitment in commitments:

            participant = (
                cls.resolve_commitment(
                    db=db,
                    commitment=commitment,
                )
            )

            if participant:
                assigned_count += 1

        db.flush()

        return assigned_count

    # =========================================================
    # GET PARTICIPANTS
    # =========================================================

    @staticmethod
    def get_meeting_participants(
        db: Session,
        meeting_id: UUID,
    ) -> list[Participant]:

        return list(
            db.scalars(
                select(Participant)
                .where(
                    Participant.meeting_id
                    == meeting_id
                )
                .order_by(
                    Participant.name
                )
            ).all()
        )


owner_resolution_service = (
    OwnerResolutionService()
)
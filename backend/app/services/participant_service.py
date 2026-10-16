from __future__ import annotations

import re
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.participant import Participant


class ParticipantService:
    """
    Participant intelligence service.

    Responsibilities:
    - Create participants for a meeting.
    - Avoid duplicate participants.
    - Normalize names.
    - Match short names such as "Warren" to
      full names such as "Melinda Warren".
    - Support titles such as Councillor, Mayor, Chair, etc.
    """

    # =========================================================
    # NAME NORMALIZATION
    # =========================================================

    @staticmethod
    def normalize_name(
        name: Optional[str],
    ) -> str:
        """
        Normalize a person's name.

        Example:

            "Councillor Melinda Warren"
                ->
            "melinda warren"
        """

        if not name:
            return ""

        value = name.strip().lower()

        # Remove punctuation.
        value = re.sub(
            r"[^a-z0-9\s]",
            " ",
            value,
        )

        # Remove common titles.
        titles = {
            "mr",
            "mrs",
            "ms",
            "miss",
            "dr",
            "prof",
            "professor",
            "councillor",
            "councilor",
            "counselor",
            "mayor",
            "deputy",
            "chair",
            "chairperson",
            "vice",
            "assistant",
            "ceo",
            "president",
        }

        words = value.split()

        words = [
            word
            for word in words
            if word not in titles
        ]

        value = " ".join(words)

        # Collapse whitespace.
        value = re.sub(
            r"\s+",
            " ",
            value,
        )

        return value.strip()

    # =========================================================
    # TOKENIZATION
    # =========================================================

    @classmethod
    def name_tokens(
        cls,
        name: Optional[str],
    ) -> list[str]:
        normalized = cls.normalize_name(
            name
        )

        if not normalized:
            return []

        return normalized.split()

    # =========================================================
    # NAME MATCHING
    # =========================================================

    @classmethod
    def names_match(
        cls,
        first_name: Optional[str],
        second_name: Optional[str],
    ) -> bool:
        """
        Determine whether two names refer to the
        same participant.

        Examples:

            Melinda Warren
            Melinda Warren
                -> True

            Warren
            Melinda Warren
                -> True

            Councillor Warren
            Melinda Warren
                -> True

            Miller
            Warren
                -> False
        """

        first = cls.normalize_name(
            first_name
        )

        second = cls.normalize_name(
            second_name
        )

        if not first or not second:
            return False

        # Exact match.
        if first == second:
            return True

        first_tokens = first.split()
        second_tokens = second.split()

        # Full phrase contained in the other.
        if first in second:
            return True

        if second in first:
            return True

        # -----------------------------------------------------
        # Last-name matching
        # -----------------------------------------------------

        first_last = first_tokens[-1]
        second_last = second_tokens[-1]

        if (
            len(first_last) >= 3
            and first_last == second_last
        ):
            return True

        # -----------------------------------------------------
        # First + last matching
        # -----------------------------------------------------

        if len(first_tokens) >= 2 and len(
            second_tokens
        ) >= 2:
            if (
                first_tokens[0]
                == second_tokens[0]
                and first_tokens[-1]
                == second_tokens[-1]
            ):
                return True

        return False

    # =========================================================
    # FIND EXISTING PARTICIPANT
    # =========================================================

    @classmethod
    def find_participant(
        cls,
        db: Session,
        meeting_id: UUID,
        name: str,
    ) -> Optional[Participant]:
        """
        Find an existing participant for a meeting.
        """

        if not name:
            return None

        participants = list(
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

        if not participants:
            return None

        normalized_name = cls.normalize_name(
            name
        )

        # -----------------------------------------------------
        # Exact normalized match
        # -----------------------------------------------------

        for participant in participants:
            if (
                cls.normalize_name(
                    participant.name
                )
                == normalized_name
            ):
                return participant

        # -----------------------------------------------------
        # Match by name
        # -----------------------------------------------------

        matches: list[
            Participant
        ] = []

        for participant in participants:
            if cls.names_match(
                participant.name,
                name,
            ):
                matches.append(
                    participant
                )

        # Only automatically return a match
        # when it is unambiguous.
        if len(matches) == 1:
            return matches[0]

        return None

    # =========================================================
    # CREATE PARTICIPANT
    # =========================================================

    @classmethod
    def create_participant(
        cls,
        db: Session,
        meeting_id: UUID,
        name: str,
        role: Optional[str] = None,
        speaker_label: Optional[str] = None,
    ) -> Participant:
        """
        Create a participant if one does not already exist.

        If a matching participant already exists,
        return the existing participant.
        """

        existing = cls.find_participant(
            db=db,
            meeting_id=meeting_id,
            name=name,
        )

        if existing:
            changed = False

            if (
                role
                and not getattr(
                    existing,
                    "role",
                    None,
                )
            ):
                existing.role = role
                changed = True

            if (
                speaker_label
                and hasattr(
                    existing,
                    "speaker_label",
                )
                and not existing.speaker_label
            ):
                existing.speaker_label = (
                    speaker_label
                )
                changed = True

            if changed:
                db.flush()

            return existing

        participant_kwargs = {
            "meeting_id": meeting_id,
            "name": name.strip(),
        }

        # Only use fields that may exist in the model.
        if role:
            participant_kwargs["role"] = role

        if (
            speaker_label
            and hasattr(
                Participant,
                "speaker_label",
            )
        ):
            participant_kwargs[
                "speaker_label"
            ] = speaker_label

        participant = Participant(
            **participant_kwargs
        )

        db.add(participant)
        db.flush()

        return participant

    # =========================================================
    # CREATE MANY PARTICIPANTS
    # =========================================================

    @classmethod
    def create_participants(
        cls,
        db: Session,
        meeting_id: UUID,
        names: list[str],
    ) -> list[Participant]:
        """
        Create multiple participants while avoiding
        duplicates.
        """

        participants: list[
            Participant
        ] = []

        seen: set[str] = set()

        for name in names:
            clean_name = (
                name.strip()
                if name
                else ""
            )

            if not clean_name:
                continue

            normalized = cls.normalize_name(
                clean_name
            )

            if not normalized:
                continue

            if normalized in seen:
                continue

            seen.add(normalized)

            participant = (
                cls.create_participant(
                    db=db,
                    meeting_id=meeting_id,
                    name=clean_name,
                )
            )

            participants.append(
                participant
            )

        db.flush()

        return participants

    # =========================================================
    # EXTRACT PEOPLE FROM TRANSCRIPT
    # =========================================================

    @classmethod
    def extract_candidate_names(
        cls,
        transcript_text: str,
    ) -> list[str]:
        """
        Extract likely person names from transcript text.

        This is intentionally conservative.

        It does NOT try to replace the LLM.
        It provides candidate names that can later
        be verified by the analysis pipeline.
        """

        if not transcript_text:
            return []

        candidates: list[str] = []

        # -----------------------------------------------------
        # Common meeting titles followed by a name.
        #
        # Examples:
        #
        #   Councillor Warren
        #   Mayor Smith
        #   Deputy Mayor Miller
        # -----------------------------------------------------

        title_pattern = re.compile(
            r"\b(?:Councillor|Councilor|"
            r"Counselor|Mayor|Chair|"
            r"Deputy Mayor|Dr\.?|Mr\.?|"
            r"Mrs\.?|Ms\.?)\s+"
            r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)",
            flags=re.IGNORECASE,
        )

        for match in title_pattern.finditer(
            transcript_text
        ):
            value = match.group(1).strip()

            if value:
                candidates.append(
                    value
                )

        # -----------------------------------------------------
        # Capitalized first + last names.
        # -----------------------------------------------------

        full_name_pattern = re.compile(
            r"\b([A-Z][a-z]{2,}"
            r"(?:\s+[A-Z][a-z]{2,})+)\b"
        )

        for match in full_name_pattern.finditer(
            transcript_text
        ):
            value = match.group(1).strip()

            if value:
                candidates.append(
                    value
                )

        # -----------------------------------------------------
        # Deduplicate.
        # -----------------------------------------------------

        result: list[str] = []
        seen: set[str] = set()

        for candidate in candidates:
            normalized = cls.normalize_name(
                candidate
            )

            if not normalized:
                continue

            if normalized in seen:
                continue

            seen.add(normalized)
            result.append(candidate)

        return result

    # =========================================================
    # MATCH AI OWNER
    # =========================================================

    @classmethod
    def match_owner(
        cls,
        db: Session,
        meeting_id: UUID,
        owner_name: str,
    ) -> Optional[Participant]:
        """
        Match an AI-generated owner name
        to a participant.
        """

        if not owner_name:
            return None

        return cls.find_participant(
            db=db,
            meeting_id=meeting_id,
            name=owner_name,
        )

    # =========================================================
    # GET MEETING PARTICIPANTS
    # =========================================================

    @staticmethod
    def get_meeting_participants(
        db: Session,
        meeting_id: UUID,
    ) -> list[Participant]:
        """
        Return all participants for a meeting.
        """

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

    # =========================================================
    # PARTICIPANT DICTIONARY
    # =========================================================

    @staticmethod
    def to_dict(
        participant: Participant,
    ) -> dict:
        """
        Convert participant to a frontend-friendly
        dictionary.
        """

        result = {
            "id": str(
                participant.id
            ),
            "meeting_id": str(
                participant.meeting_id
            ),
            "name": participant.name,
        }

        if hasattr(
            participant,
            "role",
        ):
            result["role"] = (
                participant.role
            )

        if hasattr(
            participant,
            "speaker_label",
        ):
            result["speaker_label"] = (
                participant.speaker_label
            )

        if hasattr(
            participant,
            "created_at",
        ):
            created_at = (
                participant.created_at
            )

            result["created_at"] = (
                created_at.isoformat()
                if created_at
                else None
            )

        return result


participant_service = ParticipantService()
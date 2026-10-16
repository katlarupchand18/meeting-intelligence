from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.evidence import Evidence, EvidenceType
from app.schemas.evidence import EvidenceResponse
from app.utils.confidence import clamp_confidence


class EvidenceService:
    """
    Handles evidence linking between AI-generated results
    and transcript segments.
    """

    # ---------------------------------------------------------
    # Create Evidence
    # ---------------------------------------------------------

    def create_evidence(
        self,
        db: Session,
        *,
        meeting_id: UUID,
        snippet: str,
        evidence_type: EvidenceType = EvidenceType.GENERAL,
        transcript_segment_id: UUID | None = None,
        commitment_id: UUID | None = None,
        decision_id: UUID | None = None,
        confidence: float = 0.0,
    ) -> Evidence:

        if not snippet.strip():
            raise ValueError(
                "Evidence snippet cannot be empty."
            )

        evidence = Evidence(
            meeting_id=meeting_id,
            transcript_segment_id=transcript_segment_id,
            commitment_id=commitment_id,
            decision_id=decision_id,
            evidence_type=evidence_type,
            snippet=snippet.strip(),
            confidence=clamp_confidence(
                confidence
            ),
        )

        db.add(evidence)
        db.commit()
        db.refresh(evidence)

        return evidence

    # ---------------------------------------------------------
    # Get Meeting Evidence
    # ---------------------------------------------------------

    def get_meeting_evidence(
        self,
        db: Session,
        meeting_id: UUID,
    ) -> list[Evidence]:

        return list(
            db.scalars(
                select(Evidence)
                .where(
                    Evidence.meeting_id
                    == meeting_id
                )
                .order_by(
                    Evidence.created_at.asc()
                )
            ).all()
        )

    # ---------------------------------------------------------
    # Get Commitment Evidence
    # ---------------------------------------------------------

    def get_commitment_evidence(
        self,
        db: Session,
        commitment_id: UUID,
    ) -> list[Evidence]:

        return list(
            db.scalars(
                select(Evidence)
                .where(
                    Evidence.commitment_id
                    == commitment_id
                )
                .order_by(
                    Evidence.created_at.asc()
                )
            ).all()
        )

    # ---------------------------------------------------------
    # Get Decision Evidence
    # ---------------------------------------------------------

    def get_decision_evidence(
        self,
        db: Session,
        decision_id: UUID,
    ) -> list[Evidence]:

        return list(
            db.scalars(
                select(Evidence)
                .where(
                    Evidence.decision_id
                    == decision_id
                )
                .order_by(
                    Evidence.created_at.asc()
                )
            ).all()
        )

    # ---------------------------------------------------------
    # Delete Evidence
    # ---------------------------------------------------------

    def delete_evidence(
        self,
        db: Session,
        evidence: Evidence,
    ) -> None:

        db.delete(evidence)
        db.commit()


evidence_service = EvidenceService()
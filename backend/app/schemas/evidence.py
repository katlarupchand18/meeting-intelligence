from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.evidence import EvidenceType


class EvidenceResponse(BaseModel):
    """
    Evidence returned by the API.

    Evidence connects an AI-generated result to the
    original transcript.
    """

    model_config = ConfigDict(
        from_attributes=True,
    )

    id: UUID

    meeting_id: UUID

    transcript_segment_id: UUID | None

    commitment_id: UUID | None

    decision_id: UUID | None

    evidence_type: EvidenceType

    snippet: str = Field(
        ...,
        min_length=1,
    )

    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
    )

    created_at: datetime
from uuid import UUID

from pydantic import BaseModel, Field


class AnalysisResponse(BaseModel):
    """
    Result of AI analysis for a meeting.
    """

    meeting_id: UUID

    summary: str = ""

    key_topics: list[str] = Field(
        default_factory=list
    )

    decisions_count: int = 0

    commitments_count: int = 0

    evidence_count: int = 0

    confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
    )


class MeetingAnalysisResponse(BaseModel):
    """
    Complete structured analysis response.
    """

    meeting_id: UUID

    summary: str = ""

    key_topics: list[str] = Field(
        default_factory=list
    )

    decisions: list[dict] = Field(
        default_factory=list
    )

    commitments: list[dict] = Field(
        default_factory=list
    )

    evidence: list[dict] = Field(
        default_factory=list
    )

    overall_confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
    )

    processing_status: str = "completed"
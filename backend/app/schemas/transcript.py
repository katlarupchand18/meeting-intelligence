from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


# =========================================================
# Transcript Segment Response
# =========================================================

class TranscriptSegmentResponse(BaseModel):
    """
    A single speaker-attributed transcript segment.
    """

    model_config = ConfigDict(
        from_attributes=True,
    )

    id: UUID

    meeting_id: UUID

    speaker_label: str | None

    speaker_name: str | None

    text: str = Field(
        ...,
        min_length=1,
    )

    start_time: float = Field(
        ...,
        ge=0,
    )

    end_time: float = Field(
        ...,
        ge=0,
    )

    sequence_number: int = Field(
        ...,
        ge=0,
    )


# =========================================================
# Transcript Response
# =========================================================

class TranscriptResponse(BaseModel):
    """
    Complete transcript response for a meeting.
    """

    meeting_id: UUID

    segments: list[TranscriptSegmentResponse]

    total_segments: int

    duration_seconds: float | None = None
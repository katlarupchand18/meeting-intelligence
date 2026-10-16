from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.commitment import (
    CommitmentStatus,
    CommitmentStrength,
)


class CommitmentCreate(BaseModel):
    """
    Data required to create a commitment.
    """

    meeting_id: UUID

    owner_id: UUID | None = None

    task: str = Field(
        ...,
        min_length=1,
        max_length=5000,
    )

    deadline: date | None = None

    deadline_text: str | None = Field(
        default=None,
        max_length=500,
    )

    strength: CommitmentStrength = (
        CommitmentStrength.UNASSIGNED
    )

    confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
    )

    notes: str | None = None


class CommitmentUpdate(BaseModel):
    """
    Fields that can be updated on a commitment.
    """

    owner_id: UUID | None = None

    task: str | None = Field(
        default=None,
        min_length=1,
        max_length=5000,
    )

    deadline: date | None = None

    deadline_text: str | None = Field(
        default=None,
        max_length=500,
    )

    strength: CommitmentStrength | None = None

    status: CommitmentStatus | None = None

    notes: str | None = None


class CommitmentResponse(BaseModel):
    """
    Commitment returned by the API.
    """

    model_config = ConfigDict(
        from_attributes=True,
    )

    id: UUID

    meeting_id: UUID

    owner_id: UUID | None

    task: str

    deadline: date | None

    deadline_text: str | None

    strength: CommitmentStrength

    status: CommitmentStatus

    confidence: float

    notes: str | None

    created_at: datetime

    updated_at: datetime
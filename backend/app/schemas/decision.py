from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.decision import DecisionStatus


class DecisionCreate(BaseModel):
    """
    Data required to create a decision.
    """

    meeting_id: UUID

    title: str = Field(
        ...,
        min_length=1,
        max_length=500,
    )

    description: str = Field(
        ...,
        min_length=1,
        max_length=10000,
    )

    status: DecisionStatus = DecisionStatus.ACCEPTED

    confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
    )

    changed_from_decision_id: UUID | None = None


class DecisionUpdate(BaseModel):
    """
    Fields that can be updated on a decision.
    """

    title: str | None = Field(
        default=None,
        min_length=1,
        max_length=500,
    )

    description: str | None = Field(
        default=None,
        min_length=1,
        max_length=10000,
    )

    status: DecisionStatus | None = None

    confidence: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
    )

    changed_from_decision_id: UUID | None = None


class DecisionResponse(BaseModel):
    """
    Decision returned by the API.
    """

    model_config = ConfigDict(
        from_attributes=True,
    )

    id: UUID

    meeting_id: UUID

    title: str

    description: str

    status: DecisionStatus

    confidence: float

    changed_from_decision_id: UUID | None

    created_at: datetime
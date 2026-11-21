from enum import Enum

from pydantic import BaseModel, Field


class VerificationAction(str, Enum):
    APPROVED = "approved"
    REJECTED = "rejected"
    EDITED = "edited"


class VerificationRequest(BaseModel):
    action: VerificationAction

    # Temporary reviewer label for local development.
    # This must not be treated as authenticated identity.
    reviewer_id: str = Field(
        min_length=1,
        max_length=255,
    )


class DecisionVerificationEdit(BaseModel):
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


class CommitmentVerificationEdit(BaseModel):
    task: str | None = Field(
        default=None,
        min_length=1,
        max_length=5000,
    )
    deadline_text: str | None = Field(
        default=None,
        max_length=500,
    )

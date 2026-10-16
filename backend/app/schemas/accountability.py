from datetime import date
from uuid import UUID

from pydantic import BaseModel, Field


class AccountabilitySummaryResponse(BaseModel):
    """
    Summary of commitment/accountability status.
    """

    total_commitments: int = 0

    open_commitments: int = 0

    in_progress_commitments: int = 0

    completed_commitments: int = 0

    blocked_commitments: int = 0

    overdue_commitments: int = 0

    unassigned_commitments: int = 0

    completion_rate: float = Field(
        default=0.0,
        ge=0.0,
        le=100.0,
    )


class AccountabilityOverviewResponse(BaseModel):
    """
    Complete accountability dashboard response.
    """

    meeting_id: UUID | None = None

    summary: AccountabilitySummaryResponse

    upcoming_deadlines: list[dict] = Field(
        default_factory=list,
    )

    overdue_items: list[dict] = Field(
        default_factory=list,
    )

    blocked_items: list[dict] = Field(
        default_factory=list,
    )

    unassigned_items: list[dict] = Field(
        default_factory=list,
    )

    dependencies: list[dict] = Field(
        default_factory=list,
    )

    generated_at: date | None = None
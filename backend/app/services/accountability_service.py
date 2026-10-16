from datetime import date
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.commitment import (
    Commitment,
    CommitmentStatus,
)
from app.models.dependency import Dependency
from app.schemas.accountability import (
    AccountabilityOverviewResponse,
    AccountabilitySummaryResponse,
)


class AccountabilityService:
    """
    Converts commitment data into an accountability view.

    This is the layer that answers:
        - What is still open?
        - What is overdue?
        - Who owns it?
        - What is blocked?
        - What is unassigned?
        - What is due soon?
    """

    # ---------------------------------------------------------
    # Summary
    # ---------------------------------------------------------

    def get_summary(
        self,
        db: Session,
        meeting_id: UUID | None = None,
    ) -> AccountabilitySummaryResponse:

        filters = []

        if meeting_id is not None:
            filters.append(
                Commitment.meeting_id
                == meeting_id
            )

        commitments = list(
            db.scalars(
                select(Commitment).where(
                    *filters
                )
            ).all()
        )

        total = len(commitments)

        counts = {
            status: 0
            for status in CommitmentStatus
        }

        unassigned = 0

        for commitment in commitments:

            counts[commitment.status] += 1

            if commitment.owner_id is None:
                unassigned += 1

        completed = counts[
            CommitmentStatus.COMPLETED
        ]

        completion_rate = (
            (completed / total) * 100
            if total
            else 0.0
        )

        return AccountabilitySummaryResponse(
            total_commitments=total,
            open_commitments=counts[
                CommitmentStatus.OPEN
            ],
            in_progress_commitments=counts[
                CommitmentStatus.IN_PROGRESS
            ],
            completed_commitments=completed,
            blocked_commitments=counts[
                CommitmentStatus.BLOCKED
            ],
            overdue_commitments=counts[
                CommitmentStatus.OVERDUE
            ],
            unassigned_commitments=unassigned,
            completion_rate=round(
                completion_rate,
                2,
            ),
        )

    # ---------------------------------------------------------
    # Overview
    # ---------------------------------------------------------

    def get_overview(
        self,
        db: Session,
        meeting_id: UUID | None = None,
    ) -> AccountabilityOverviewResponse:

        filters = []

        if meeting_id is not None:
            filters.append(
                Commitment.meeting_id
                == meeting_id
            )

        commitments = list(
            db.scalars(
                select(Commitment)
                .where(*filters)
                .order_by(
                    Commitment.deadline.asc()
                )
            ).all()
        )

        today = date.today()

        upcoming = []
        overdue = []
        blocked = []
        unassigned = []

        for commitment in commitments:

            item = {
                "id": str(
                    commitment.id
                ),
                "meeting_id": str(
                    commitment.meeting_id
                ),
                "task": commitment.task,
                "owner_id": (
                    str(commitment.owner_id)
                    if commitment.owner_id
                    else None
                ),
                "deadline": (
                    commitment.deadline.isoformat()
                    if commitment.deadline
                    else None
                ),
                "deadline_text": (
                    commitment.deadline_text
                ),
                "status": (
                    commitment.status.value
                ),
                "strength": (
                    commitment.strength.value
                ),
                "confidence": commitment.confidence,
            }

            if (
                commitment.deadline
                and commitment.deadline >= today
                and commitment.status
                not in {
                    CommitmentStatus.COMPLETED,
                    CommitmentStatus.CANCELLED,
                }
            ):
                upcoming.append(item)

            if (
                commitment.status
                == CommitmentStatus.OVERDUE
            ):
                overdue.append(item)

            if (
                commitment.status
                == CommitmentStatus.BLOCKED
            ):
                blocked.append(item)

            if commitment.owner_id is None:
                unassigned.append(item)

        dependencies = self._get_dependencies(
            db,
            commitments,
        )

        return AccountabilityOverviewResponse(
            meeting_id=meeting_id,
            summary=self.get_summary(
                db,
                meeting_id,
            ),
            upcoming_deadlines=upcoming,
            overdue_items=overdue,
            blocked_items=blocked,
            unassigned_items=unassigned,
            dependencies=dependencies,
            generated_at=today,
        )

    # ---------------------------------------------------------
    # Dependencies
    # ---------------------------------------------------------

    def _get_dependencies(
        self,
        db: Session,
        commitments: list[Commitment],
    ) -> list[dict]:

        if not commitments:
            return []

        commitment_ids = {
            commitment.id
            for commitment in commitments
        }

        dependencies = list(
            db.scalars(
                select(Dependency).where(
                    Dependency.commitment_id.in_(
                        commitment_ids
                    )
                )
            ).all()
        )

        return [
            {
                "id": str(
                    dependency.id
                ),
                "commitment_id": str(
                    dependency.commitment_id
                ),
                "depends_on_commitment_id": str(
                    dependency.depends_on_commitment_id
                ),
                "dependency_type": (
                    dependency.dependency_type.value
                ),
                "description": (
                    dependency.description
                ),
            }
            for dependency in dependencies
        ]


accountability_service = AccountabilityService()
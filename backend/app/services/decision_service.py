from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.decision import (
    Decision,
    DecisionStatus,
)
from app.schemas.decision import (
    DecisionCreate,
    DecisionUpdate,
)
from app.utils.confidence import clamp_confidence


class DecisionService:
    """
    Handles decisions and their lifecycle.

    Important distinction:
    A proposal is not automatically a final decision.
    """

    # ---------------------------------------------------------
    # Create
    # ---------------------------------------------------------

    def create_decision(
        self,
        db: Session,
        data: DecisionCreate,
    ) -> Decision:

        decision = Decision(
            meeting_id=data.meeting_id,
            title=data.title.strip(),
            description=data.description.strip(),
            status=data.status,
            confidence=clamp_confidence(
                data.confidence
            ),
            changed_from_decision_id=(
                data.changed_from_decision_id
            ),
        )

        db.add(decision)
        db.commit()
        db.refresh(decision)

        return decision

    # ---------------------------------------------------------
    # Get One
    # ---------------------------------------------------------

    def get_decision(
        self,
        db: Session,
        decision_id: UUID,
    ) -> Decision | None:

        return db.scalar(
            select(Decision).where(
                Decision.id == decision_id
            )
        )

    # ---------------------------------------------------------
    # Meeting Decisions
    # ---------------------------------------------------------

    def get_meeting_decisions(
        self,
        db: Session,
        meeting_id: UUID,
    ) -> list[Decision]:

        return list(
            db.scalars(
                select(Decision)
                .where(
                    Decision.meeting_id
                    == meeting_id
                )
                .order_by(
                    Decision.created_at.asc()
                )
            ).all()
        )

    # ---------------------------------------------------------
    # Final Decisions
    # ---------------------------------------------------------

    def get_final_decisions(
        self,
        db: Session,
        meeting_id: UUID,
    ) -> list[Decision]:

        return list(
            db.scalars(
                select(Decision)
                .where(
                    Decision.meeting_id
                    == meeting_id,
                    Decision.status
                    == DecisionStatus.ACCEPTED,
                )
                .order_by(
                    Decision.created_at.asc()
                )
            ).all()
        )

    # ---------------------------------------------------------
    # Update
    # ---------------------------------------------------------

    def update_decision(
        self,
        db: Session,
        decision: Decision,
        data: DecisionUpdate,
    ) -> Decision:

        updates = data.model_dump(
            exclude_unset=True
        )

        for field, value in updates.items():

            if isinstance(value, str):
                value = value.strip()

            if field == "confidence":
                value = clamp_confidence(value)

            setattr(
                decision,
                field,
                value,
            )

        db.commit()
        db.refresh(decision)

        return decision

    # ---------------------------------------------------------
    # Mark Changed
    # ---------------------------------------------------------

    def mark_changed(
        self,
        db: Session,
        old_decision: Decision,
        new_decision: Decision,
    ) -> None:

        old_decision.status = (
            DecisionStatus.CHANGED
        )

        new_decision.changed_from_decision_id = (
            old_decision.id
        )

        db.commit()

    # ---------------------------------------------------------
    # Delete
    # ---------------------------------------------------------

    def delete_decision(
        self,
        db: Session,
        decision: Decision,
    ) -> None:

        db.delete(decision)
        db.commit()


decision_service = DecisionService()
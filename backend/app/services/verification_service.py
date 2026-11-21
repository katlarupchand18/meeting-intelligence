from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.commitment import Commitment
from app.models.decision import Decision
from app.models.verification_history import VerificationHistory


class VerificationService:
    MODELS = {
        "decision": Decision,
        "commitment": Commitment,
    }

    EDITABLE_FIELDS = {
        "decision": {"title", "description"},
        "commitment": {"task", "deadline_text"},
    }

    @staticmethod
    def snapshot(item, item_type: str) -> dict:
        fields = VerificationService.EDITABLE_FIELDS[item_type]

        return {
            **{field: getattr(item, field) for field in fields},
            "verification_status": item.verification_status,
            "verified_by": item.verified_by,
            "verified_at": (
                item.verified_at.isoformat()
                if item.verified_at else None
            ),
        }

    def review(
        self,
        db: Session,
        item_type: str,
        item_id: UUID,
        action: str,
        reviewer_id: str,
        edits: dict | None = None,
    ):
        if item_type not in self.MODELS:
            raise ValueError("Invalid item type.")

        if action not in {"approved", "rejected", "edited"}:
            raise ValueError("Invalid verification action.")

        reviewer_id = reviewer_id.strip()
        if not reviewer_id:
            raise ValueError("Reviewer identifier is required.")

        edits = edits or {}

        if action != "edited" and edits:
            raise ValueError("Edits are only allowed with the edited action.")

        if action == "edited":
            if not edits:
                raise ValueError("At least one edit is required.")

            invalid = set(edits) - self.EDITABLE_FIELDS[item_type]
            if invalid:
                raise ValueError(
                    f"Fields cannot be edited: {sorted(invalid)}"
                )

        model = self.MODELS[item_type]

        try:
            item = db.scalar(
                select(model)
                .where(model.id == item_id)
                .with_for_update()
            )

            if item is None:
                return None

            old_value = self.snapshot(item, item_type)

            if action == "edited":
                for field, value in edits.items():
                    if isinstance(value, str):
                        value = value.strip()
                    setattr(item, field, value)

                item.verification_status = "pending"
                item.verified_by = None
                item.verified_at = None
            else:
                item.verification_status = action
                item.verified_by = reviewer_id
                item.verified_at = datetime.utcnow()

            new_value = self.snapshot(item, item_type)

            history = VerificationHistory(
                decision_id=item.id if item_type == "decision" else None,
                commitment_id=item.id if item_type == "commitment" else None,
                action=action,
                reviewer_id=reviewer_id,
                old_value=old_value,
                new_value=new_value,
            )

            db.add(history)
            db.commit()
            db.refresh(item)

            return item

        except Exception:
            db.rollback()
            raise


verification_service = VerificationService()

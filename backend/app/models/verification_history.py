import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    String,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class VerificationHistory(Base):
    __tablename__ = "verification_history"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    decision_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("decisions.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    commitment_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("commitments.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    action: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )

    reviewer_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    old_value: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
    )

    new_value: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    __table_args__ = (
        CheckConstraint(
            "(decision_id IS NOT NULL AND commitment_id IS NULL) "
            "OR (decision_id IS NULL AND commitment_id IS NOT NULL)",
            name="ck_verification_history_one_target",
        ),
        CheckConstraint(
            "action IN ('approved', 'rejected', 'edited', 'reset')",
            name="ck_verification_history_action",
        ),
    )

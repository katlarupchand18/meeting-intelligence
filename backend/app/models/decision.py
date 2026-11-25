import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, Float, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class DecisionStatus(str, enum.Enum):
    PROPOSED = "proposed"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    CHANGED = "changed"
    SUPERSEDED = "superseded"


class Decision(Base):
    __tablename__ = "decisions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    meeting_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "meetings.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    title: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )

    description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    status: Mapped[DecisionStatus] = mapped_column(
        Enum(
            DecisionStatus,
            name="decision_status",
            native_enum=True,
        ),
        default=DecisionStatus.ACCEPTED,
        nullable=False,
        index=True,
    )

    confidence: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
    )

    changed_from_decision_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "decisions.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )


    # Human-AI verification
    verification_status: Mapped[str] = mapped_column(
        String(20),
        default="pending",
        server_default="pending",
        nullable=False,
    )

    verified_by: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    verified_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
        index=True,
    )

    meeting = relationship(
        "Meeting",
        back_populates="decisions",
    )

    evidence = relationship(
        "Evidence",
        back_populates="decision",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    previous_decision = relationship(
        "Decision",
        remote_side=[id],
        foreign_keys=[changed_from_decision_id],
    )
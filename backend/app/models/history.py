import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class HistoryEventType(str, enum.Enum):
    """
    Events that can happen during a commitment's lifecycle.
    """

    CREATED = "created"
    UPDATED = "updated"
    STATUS_CHANGED = "status_changed"
    OWNER_CHANGED = "owner_changed"
    DEADLINE_CHANGED = "deadline_changed"
    BLOCKED = "blocked"
    COMPLETED = "completed"


class CommitmentHistory(Base):
    __tablename__ = "commitment_history"

    # ---------------------------------------------------------
    # Primary Key
    # ---------------------------------------------------------

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    # ---------------------------------------------------------
    # Commitment
    # ---------------------------------------------------------

    commitment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "commitments.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    # ---------------------------------------------------------
    # Event
    # ---------------------------------------------------------

    event_type: Mapped[HistoryEventType] = mapped_column(
        Enum(
            HistoryEventType,
            name="history_event_type",
            native_enum=True,
        ),
        nullable=False,
        index=True,
    )

    # ---------------------------------------------------------
    # Change Description
    # ---------------------------------------------------------

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    old_value: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    new_value: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # ---------------------------------------------------------
    # Timestamp
    # ---------------------------------------------------------

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
        index=True,
    )

    # ---------------------------------------------------------
    # Relationship
    # ---------------------------------------------------------

    commitment = relationship(
        "Commitment",
        back_populates="history",
    )
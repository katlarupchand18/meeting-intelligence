import enum
import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Enum, Float, ForeignKey, Text, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class CommitmentStrength(str, enum.Enum):
    """
    Strength/type of a commitment extracted from a meeting.
    """

    FIRM = "firm"
    WEAK = "weak"
    REQUEST = "request"
    UNASSIGNED = "unassigned"


class CommitmentStatus(str, enum.Enum):
    """
    Current lifecycle state of a commitment.
    """

    OPEN = "open"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    BLOCKED = "blocked"
    OVERDUE = "overdue"
    CANCELLED = "cancelled"


class Commitment(Base):
    __tablename__ = "commitments"

    # ---------------------------------------------------------
    # Primary Key
    # ---------------------------------------------------------

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    # ---------------------------------------------------------
    # Meeting
    # ---------------------------------------------------------

    meeting_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "meetings.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    # ---------------------------------------------------------
    # Owner
    # ---------------------------------------------------------

    owner_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "participants.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    # ---------------------------------------------------------
    # Commitment Task
    # ---------------------------------------------------------

    task: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    # ---------------------------------------------------------
    # Deadline
    # ---------------------------------------------------------

    deadline: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
        index=True,
    )

    # Original wording from the meeting.
    # Example: "before the demo", "next Friday", etc.
    deadline_text: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    # ---------------------------------------------------------
    # Commitment Strength
    # ---------------------------------------------------------

    strength: Mapped[CommitmentStrength] = mapped_column(
        Enum(
            CommitmentStrength,
            name="commitment_strength",
            native_enum=True,
        ),
        default=CommitmentStrength.UNASSIGNED,
        nullable=False,
        index=True,
    )

    # ---------------------------------------------------------
    # Status
    # ---------------------------------------------------------

    status: Mapped[CommitmentStatus] = mapped_column(
        Enum(
            CommitmentStatus,
            name="commitment_status",
            native_enum=True,
        ),
        default=CommitmentStatus.OPEN,
        nullable=False,
        index=True,
    )

    # ---------------------------------------------------------
    # AI Confidence
    # ---------------------------------------------------------

    confidence: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
    )

    # ---------------------------------------------------------
    # Additional Notes
    # ---------------------------------------------------------

    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # ---------------------------------------------------------
    # Timestamps
    # ---------------------------------------------------------


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

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    # ---------------------------------------------------------
    # Relationships
    # ---------------------------------------------------------

    meeting = relationship(
        "Meeting",
        back_populates="commitments",
    )

    owner = relationship(
        "Participant",
        back_populates="commitments",
    )

    evidence = relationship(
        "Evidence",
        back_populates="commitment",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    history = relationship(
        "CommitmentHistory",
        back_populates="commitment",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="CommitmentHistory.created_at",
    )

    dependencies = relationship(
        "Dependency",
        foreign_keys="Dependency.commitment_id",
        back_populates="commitment",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
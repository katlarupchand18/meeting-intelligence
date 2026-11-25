import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class Participant(Base):
    __tablename__ = "participants"

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

    person_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("people.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    person = relationship(
        "Person",
        back_populates="participants",
    )

    # ---------------------------------------------------------
    # Speaker Information
    # ---------------------------------------------------------

    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    speaker_label: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    # Example:
    # speaker_label = SPEAKER_00
    # name = Rahul

    # ---------------------------------------------------------
    # Role / Organization
    # ---------------------------------------------------------

    role: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    organization: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    # ---------------------------------------------------------
    # Timestamp
    # ---------------------------------------------------------

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    # ---------------------------------------------------------
    # Relationships
    # ---------------------------------------------------------

    meeting = relationship(
        "Meeting",
        back_populates="participants",
    )

    commitments = relationship(
        "Commitment",
        back_populates="owner",
    )
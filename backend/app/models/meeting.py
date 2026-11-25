import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    Enum,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class MeetingStatus(str, enum.Enum):
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class MeetingType(str, enum.Enum):
    BUSINESS = "business"
    TEAM = "team"
    PROJECT = "project"
    POLITICAL = "political"
    ACADEMIC = "academic"
    INTERVIEW = "interview"
    GENERAL = "general"


class Meeting(Base):
    __tablename__ = "meetings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    meeting_type: Mapped[MeetingType] = mapped_column(
        Enum(
            MeetingType,
            name="meeting_type",
            native_enum=True,
        ),
        default=MeetingType.GENERAL,
        nullable=False,
    )

    status: Mapped[MeetingStatus] = mapped_column(
        Enum(
            MeetingStatus,
            name="meeting_status",
            native_enum=True,
        ),
        default=MeetingStatus.UPLOADED,
        nullable=False,
        index=True,
    )

    # Current processing stage shown in the frontend.
    processing_stage: Mapped[str] = mapped_column(
        String(50),
        default="uploaded",
        nullable=False,
        server_default="uploaded",
    )

    original_filename: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    file_path: Mapped[str | None] = mapped_column(
        String(1000),
        nullable=True,
    )

    duration_seconds: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    summary: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        default=datetime.utcnow,
        nullable=False,
        index=True,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    participants = relationship(
        "Participant",
        back_populates="meeting",
        cascade="all, delete-orphan",
    )

    transcript_segments = relationship(
        "TranscriptSegment",
        back_populates="meeting",
        cascade="all, delete-orphan",
    )

    decisions = relationship(
        "Decision",
        back_populates="meeting",
        cascade="all, delete-orphan",
    )

    commitments = relationship(
        "Commitment",
        back_populates="meeting",
        cascade="all, delete-orphan",
    )

    evidence = relationship(
        "Evidence",
        back_populates="meeting",
        cascade="all, delete-orphan",
    )

    embeddings = relationship(
        "MeetingEmbedding",
        back_populates="meeting",
        cascade="all, delete-orphan",
    )
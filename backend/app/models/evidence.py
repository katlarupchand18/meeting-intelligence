import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, Float, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class EvidenceType(str, enum.Enum):
    """
    Type of evidence supporting an extracted AI result.
    """

    COMMITMENT = "commitment"
    DECISION = "decision"
    SUMMARY = "summary"
    GENERAL = "general"


class Evidence(Base):
    __tablename__ = "evidence"

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
    # Source Transcript Segment
    # ---------------------------------------------------------

    transcript_segment_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "transcript_segments.id",
            ondelete="CASCADE",
        ),
        nullable=True,
        index=True,
    )

    # ---------------------------------------------------------
    # Related Commitment
    # ---------------------------------------------------------

    commitment_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "commitments.id",
            ondelete="CASCADE",
        ),
        nullable=True,
        index=True,
    )

    # ---------------------------------------------------------
    # Related Decision
    # ---------------------------------------------------------

    decision_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "decisions.id",
            ondelete="CASCADE",
        ),
        nullable=True,
        index=True,
    )

    # ---------------------------------------------------------
    # Evidence Type
    # ---------------------------------------------------------

    evidence_type: Mapped[EvidenceType] = mapped_column(
        Enum(
            EvidenceType,
            name="evidence_type",
            native_enum=True,
        ),
        default=EvidenceType.GENERAL,
        nullable=False,
        index=True,
    )

    # ---------------------------------------------------------
    # Evidence Text
    # ---------------------------------------------------------

    snippet: Mapped[str] = mapped_column(
        Text,
        nullable=False,
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
        back_populates="evidence",
    )

    transcript_segment = relationship(
        "TranscriptSegment",
        back_populates="evidence_items",
    )

    commitment = relationship(
        "Commitment",
        back_populates="evidence",
    )

    decision = relationship(
        "Decision",
        back_populates="evidence",
    )
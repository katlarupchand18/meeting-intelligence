import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class MeetingEmbedding(Base):
    __tablename__ = "meeting_embeddings"

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
    # Text represented by the embedding
    # ---------------------------------------------------------

    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    # ---------------------------------------------------------
    # Vector Embedding
    # ---------------------------------------------------------
    #
    # text-embedding-3-small produces 1536-dimensional
    # embeddings.
    #
    # These vectors will later be used for:
    # - semantic search
    # - cross-meeting memory
    # - meeting Q&A
    # - finding related previous discussions
    #
    # ---------------------------------------------------------

    embedding: Mapped[list[float]] = mapped_column(
        Vector(768),
        nullable=False,
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

    meeting = relationship(
        "Meeting",
        back_populates="embeddings",
    )
import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class DependencyType(str, enum.Enum):
    """
    Relationship between two commitments.
    """

    BLOCKS = "blocks"
    DEPENDS_ON = "depends_on"
    RELATED = "related"


class Dependency(Base):
    __tablename__ = "dependencies"

    # ---------------------------------------------------------
    # Primary Key
    # ---------------------------------------------------------

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    # ---------------------------------------------------------
    # Current Commitment
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
    # Related Commitment
    # ---------------------------------------------------------

    depends_on_commitment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "commitments.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    # ---------------------------------------------------------
    # Dependency Type
    # ---------------------------------------------------------

    dependency_type: Mapped[DependencyType] = mapped_column(
        Enum(
            DependencyType,
            name="dependency_type",
            native_enum=True,
        ),
        default=DependencyType.DEPENDS_ON,
        nullable=False,
    )

    # ---------------------------------------------------------
    # Description
    # ---------------------------------------------------------

    description: Mapped[str | None] = mapped_column(
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
    )

    # ---------------------------------------------------------
    # Relationships
    # ---------------------------------------------------------

    commitment = relationship(
        "Commitment",
        foreign_keys=[commitment_id],
        back_populates="dependencies",
    )

    depends_on_commitment = relationship(
        "Commitment",
        foreign_keys=[depends_on_commitment_id],
    )
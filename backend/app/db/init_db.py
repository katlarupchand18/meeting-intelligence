from app.db.database import Base, engine

# Import every model so SQLAlchemy registers all tables
# before create_all() is called.
from app.models.commitment import Commitment
from app.models.decision import Decision
from app.models.dependency import Dependency
from app.models.embedding import MeetingEmbedding
from app.models.evidence import Evidence
from app.models.history import CommitmentHistory
from app.models.meeting import Meeting
from app.models.participant import Participant
from app.models.transcript import TranscriptSegment


def init_database() -> None:
    """
    Create all database tables defined by the application models.
    """
    Base.metadata.create_all(bind=engine)


if __name__ == "__main__":
    init_database()
    print("Database tables created successfully.")
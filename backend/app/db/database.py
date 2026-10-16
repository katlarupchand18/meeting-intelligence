from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings


class Base(DeclarativeBase):
    """
    Base class for all SQLAlchemy database models.
    """
    pass


# ---------------------------------------------------------
# Database Engine
# ---------------------------------------------------------

engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=1800,
    future=True,
)


# ---------------------------------------------------------
# Database Session
# ---------------------------------------------------------

SessionLocal = sessionmaker(
    bind=engine,
    class_=Session,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)


# ---------------------------------------------------------
# FastAPI Database Dependency
# ---------------------------------------------------------

def get_db() -> Generator[Session, None, None]:
    """
    Provides a database session for a FastAPI request.

    The session is always closed after the request finishes.
    """
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()


# ---------------------------------------------------------
# Database Initialization
# ---------------------------------------------------------

def create_tables() -> None:
    """
    Create all registered database tables.

    Models must be imported before calling this function so
    SQLAlchemy knows about them.
    """
    Base.metadata.create_all(bind=engine)
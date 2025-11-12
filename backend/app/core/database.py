"""
Database connection and session management.
Provides SQLAlchemy engine, session factory, and dependency injection for FastAPI.
"""
from typing import Generator
from sqlalchemy import create_engine, event
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool

from .config import settings

# Create SQLAlchemy engine with connection pooling
engine = create_engine(
    str(settings.DATABASE_URL),
    poolclass=QueuePool,
    pool_size=settings.DATABASE_POOL_SIZE,
    max_overflow=settings.DATABASE_MAX_OVERFLOW,
    pool_pre_ping=True,  # Verify connections before using them
    echo=settings.is_development,  # Log SQL in development
)

# Session factory for creating database sessions
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for all ORM models
Base = declarative_base()


# Event listener to set timezone for PostgreSQL sessions
@event.listens_for(engine, "connect")
def set_timezone(dbapi_conn, connection_record):
    """Set timezone to UTC for all database connections."""
    cursor = dbapi_conn.cursor()
    cursor.execute("SET timezone='UTC'")
    cursor.close()


def get_db() -> Generator[Session, None, None]:
    """
    Dependency function to get database session for FastAPI endpoints.

    Usage in endpoints:
        @app.get("/items")
        def get_items(db: Session = Depends(get_db)):
            return db.query(Item).all()

    Yields:
        Session: SQLAlchemy database session
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """
    Initialize database by creating all tables.
    Should be called on application startup.
    """
    # Import all models here to ensure they are registered with Base
    from app.api.models import (  # noqa: F401
        social_accounts,
        posts,
        predictions,
        scheduled_posts,
        carbon_forecasts,
        job_queue,
        execution_logs,
    )

    Base.metadata.create_all(bind=engine)

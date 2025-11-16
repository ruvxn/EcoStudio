"""
Database connection and session management.
Provides SQLAlchemy engine, session factory, and dependency injection for FastAPI.
"""
from typing import Generator, AsyncGenerator
from sqlalchemy import create_engine, event
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool, NullPool

from .config import settings

# Create synchronous SQLAlchemy engine (for migrations and sync operations)
engine = create_engine(
    str(settings.DATABASE_URL),
    poolclass=QueuePool,
    pool_size=settings.DATABASE_POOL_SIZE,
    max_overflow=settings.DATABASE_MAX_OVERFLOW,
    pool_pre_ping=True,  # Verify connections before using them
    echo=settings.is_development,  # Log SQL in development
)

# Create async SQLAlchemy engine (for FastAPI endpoints)
async_database_url = str(settings.DATABASE_URL).replace("postgresql://", "postgresql+asyncpg://")
async_engine = create_async_engine(
    async_database_url,
    poolclass=NullPool,  # Use NullPool for async to avoid connection issues
    echo=settings.is_development,
)

# Session factory for creating database sessions
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Async session factory for FastAPI endpoints
AsyncSessionLocal = async_sessionmaker(
    async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

# Base class for all ORM models
Base = declarative_base()


# Event listener to set timezone for PostgreSQL sessions (sync)
@event.listens_for(engine, "connect")
def set_timezone(dbapi_conn, connection_record):
    """Set timezone to UTC for all database connections."""
    cursor = dbapi_conn.cursor()
    cursor.execute("SET timezone='UTC'")
    cursor.close()


def get_db() -> Generator[Session, None, None]:
    """
    Dependency function to get synchronous database session.
    Use for migrations and sync operations only.

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


async def get_async_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency function to get async database session for FastAPI endpoints.
    This is the recommended way for FastAPI async endpoints.

    Usage in endpoints:
        @app.get("/items")
        async def get_items(db: AsyncSession = Depends(get_async_db)):
            result = await db.execute(select(Item))
            return result.scalars().all()

    Yields:
        AsyncSession: Async SQLAlchemy database session
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


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
        green_windows,
        carbon_savings,
        system_config,
    )

    Base.metadata.create_all(bind=engine)

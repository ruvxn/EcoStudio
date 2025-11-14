"""
Job queue model for managing async background tasks.
"""
from datetime import datetime
from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    Float,
    DateTime,
    ForeignKey,
    Index,
    Enum as SQLEnum,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
import enum

from app.core.database import Base


class JobType(str, enum.Enum):
    """Types of background jobs."""

    SYNC_POSTS = "sync_posts"  # Fetch historical posts from platform
    RETRAIN_MODEL = "retrain_model"  # Train ML model with new data
    GENERATE_CONTENT = "generate_content"  # AI content generation
    POST_CONTENT = "post_content"  # Publish post to platform
    FETCH_CARBON_FORECAST = "fetch_carbon_forecast"  # Get carbon data
    CALCULATE_ENGAGEMENT = "calculate_engagement"  # Update engagement scores


class JobStatus(str, enum.Enum):
    """Status of a job in the queue."""

    QUEUED = "queued"  # Waiting to execute
    RUNNING = "running"  # Currently executing
    COMPLETED = "completed"  # Successfully completed
    FAILED = "failed"  # Failed with error
    CANCELLED = "cancelled"  # Cancelled by user or system


class Job(Base):
    """
    Background job for async task execution.

    Manages the queue and execution of compute-intensive or time-scheduled tasks.
    In Phase 2, jobs are scheduled during low-carbon windows.
    """

    __tablename__ = "job_queue"

    id = Column(Integer, primary_key=True, index=True)
    job_type = Column(
        SQLEnum(JobType),
        nullable=False,
        index=True,
        comment="Type of job to execute",
    )
    account_id = Column(
        Integer,
        ForeignKey("social_accounts.id", ondelete="CASCADE"),
        nullable=True,  # Some jobs (like carbon fetch) are not account-specific
        index=True,
    )
    scheduled_for = Column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
        comment="When to execute this job (UTC)",
    )
    carbon_intensity = Column(
        Integer,
        nullable=True,
        comment="Carbon intensity at scheduled time (Phase 2)",
    )
    estimated_duration_minutes = Column(
        Integer,
        nullable=True,
        comment="Estimated job duration for scheduling (Phase 2)",
    )
    optimal_window_start = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="Recommended green window start time (Phase 2)",
    )
    optimal_window_end = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="Recommended green window end time (Phase 2)",
    )
    carbon_score = Column(
        Float,
        nullable=True,
        comment="Carbon optimization score 0-1 (Phase 2)",
    )
    status = Column(
        SQLEnum(JobStatus),
        nullable=False,
        default=JobStatus.QUEUED,
        index=True,
        comment="Current status of the job",
    )
    priority = Column(
        Integer,
        nullable=False,
        default=5,
        comment="Job priority (1=highest, 10=lowest)",
    )
    result = Column(
        JSONB,
        nullable=True,
        comment="Job-specific result data (JSON format)",
    )
    error_message = Column(
        Text, nullable=True, comment="Error details if job failed"
    )
    retry_count = Column(
        Integer, default=0, comment="Number of retry attempts"
    )
    max_retries = Column(
        Integer, default=3, comment="Maximum retry attempts before marking as failed"
    )

    # Timestamps
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        comment="When job was created",
    )
    started_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="When job execution started",
    )
    completed_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="When job finished (success or failure)",
    )

    # Relationships
    account = relationship("SocialAccount", back_populates="jobs")
    execution_logs = relationship(
        "ExecutionLog", back_populates="job", cascade="all, delete-orphan"
    )
    carbon_saving = relationship(
        "CarbonSaving", back_populates="job", uselist=False, cascade="all, delete-orphan"
    )

    # Indexes
    __table_args__ = (
        Index("idx_jobs_status_scheduled", "status", "scheduled_for"),
        Index("idx_jobs_type_status", "job_type", "status"),
    )

    def __repr__(self):
        return f"<Job(id={self.id}, type={self.job_type}, status={self.status})>"

    def is_ready_to_execute(self) -> bool:
        """Check if job is ready to be executed."""
        return (
            self.status == JobStatus.QUEUED
            and datetime.utcnow() >= self.scheduled_for
        )

    def can_retry(self) -> bool:
        """Check if job can be retried after failure."""
        return (
            self.status == JobStatus.FAILED
            and self.retry_count < self.max_retries
        )

    @property
    def execution_duration_seconds(self) -> int:
        """Calculate job execution duration in seconds."""
        if not self.started_at or not self.completed_at:
            return 0
        return int((self.completed_at - self.started_at).total_seconds())

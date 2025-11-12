"""
Scheduled post model for managing posts to be published in the future.
"""
from datetime import datetime
from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Enum as SQLEnum,
)
from sqlalchemy.orm import relationship
import enum

from app.core.database import Base
from app.api.models.posts import ContentType


class PostStatus(str, enum.Enum):
    """Status of a scheduled post."""

    PENDING = "pending"  # Awaiting content generation
    GENERATED = "generated"  # Content generated, awaiting approval
    APPROVED = "approved"  # User approved, ready to post
    POSTED = "posted"  # Successfully posted
    FAILED = "failed"  # Posting failed
    CANCELLED = "cancelled"  # User cancelled


class ScheduledPost(Base):
    """
    Post scheduled for future publication.

    Tracks posts from creation through content generation, approval, and publishing.
    Stores both predicted and actual engagement for model improvement.
    """

    __tablename__ = "scheduled_posts"

    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(
        Integer,
        ForeignKey("social_accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    scheduled_time = Column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
        comment="When to publish this post (UTC)",
    )
    content = Column(Text, nullable=True, comment="Generated or user-provided caption")
    content_type = Column(
        SQLEnum(ContentType), nullable=False, comment="Type of content to post"
    )
    image_url = Column(
        Text, nullable=True, comment="S3 URL or local path to image/video"
    )
    media_id = Column(
        String(255),
        nullable=True,
        comment="Platform-specific media ID after upload",
    )

    # Status tracking
    status = Column(
        SQLEnum(PostStatus),
        nullable=False,
        default=PostStatus.PENDING,
        index=True,
        comment="Current status of the scheduled post",
    )
    error_message = Column(
        Text, nullable=True, comment="Error details if posting failed"
    )

    # Engagement tracking
    predicted_engagement = Column(
        Float,
        nullable=True,
        comment="ML-predicted engagement score for this time slot",
    )
    actual_engagement = Column(
        Float, nullable=True, comment="Actual engagement after posting (for feedback)"
    )
    platform_post_id = Column(
        String(255),
        nullable=True,
        unique=True,
        comment="ID of the published post on the platform",
    )

    # Metadata
    generation_job_id = Column(
        Integer,
        ForeignKey("job_queue.id"),
        nullable=True,
        comment="Reference to content generation job",
    )
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        comment="When this post was scheduled",
    )
    posted_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="Actual timestamp when posted",
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    # Relationships
    account = relationship("SocialAccount", back_populates="scheduled_posts")
    generation_job = relationship("Job", foreign_keys=[generation_job_id])

    # Indexes
    __table_args__ = (
        Index("idx_scheduled_posts_time", "scheduled_time"),
        Index("idx_scheduled_posts_status", "status", "scheduled_time"),
    )

    def __repr__(self):
        return f"<ScheduledPost(id={self.id}, time={self.scheduled_time}, status={self.status})>"

    def is_past_scheduled_time(self) -> bool:
        """Check if the scheduled time has passed."""
        return datetime.utcnow() >= self.scheduled_time

    def can_be_edited(self) -> bool:
        """Check if post can still be edited."""
        return self.status in [PostStatus.PENDING, PostStatus.GENERATED]

    def can_be_cancelled(self) -> bool:
        """Check if post can be cancelled."""
        return self.status not in [PostStatus.POSTED, PostStatus.CANCELLED]

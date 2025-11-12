"""
Post model for storing historical social media posts with engagement metrics.
Used for training the ML prediction model.
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
)
from sqlalchemy.orm import relationship
import enum

from app.core.database import Base


class ContentType(str, enum.Enum):
    """Types of social media content."""

    IMAGE = "image"
    VIDEO = "video"
    CAROUSEL = "carousel"
    REEL = "reel"
    STORY = "story"


class Post(Base):
    """
    Historical social media post with engagement metrics.

    Stores posts fetched from social media platforms for analysis and ML training.
    Engagement score is calculated as: (likes + comments * 2 + shares * 3) / followers
    """

    __tablename__ = "posts"

    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(
        Integer,
        ForeignKey("social_accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    post_id = Column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
        comment="Platform-specific post ID",
    )
    content = Column(Text, nullable=True, comment="Caption/description text")
    post_time = Column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
        comment="When the post was published (UTC)",
    )

    # Engagement metrics
    likes = Column(Integer, default=0, comment="Number of likes")
    comments = Column(Integer, default=0, comment="Number of comments")
    shares = Column(Integer, default=0, comment="Number of shares")
    views = Column(Integer, nullable=True, comment="Number of views (for videos)")
    saves = Column(Integer, nullable=True, comment="Number of saves/bookmarks")
    engagement_score = Column(
        Float,
        nullable=True,
        index=True,
        comment="Normalized engagement: (likes + comments*2 + shares*3) / followers",
    )

    # Content characteristics
    content_type = Column(
        String(20),
        nullable=False,
        comment="Type of content"
    )
    caption_length = Column(
        Integer, nullable=True, comment="Character count of caption"
    )
    hashtag_count = Column(Integer, default=0, comment="Number of hashtags used")
    has_emoji = Column(Integer, default=0, comment="1 if caption contains emoji, 0 otherwise")
    media_url = Column(Text, nullable=True, comment="URL to the media file")

    # Metadata
    synced_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        comment="When this post was fetched from the platform",
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    # Relationships
    account = relationship("SocialAccount", back_populates="posts")

    # Composite indexes for common queries
    __table_args__ = (
        Index("idx_posts_account_time", "account_id", "post_time"),
        Index("idx_posts_account_engagement", "account_id", "engagement_score"),
    )

    def __repr__(self):
        return f"<Post(id={self.id}, post_id={self.post_id}, engagement={self.engagement_score})>"

    def calculate_engagement_score(self, follower_count: int) -> float:
        """
        Calculate normalized engagement score.

        Formula: (likes + comments * 2 + shares * 3) / followers
        This gives more weight to comments and shares as they indicate deeper engagement.

        Args:
            follower_count: Current follower count of the account

        Returns:
            Normalized engagement score (0.0 to ~1.0 range)
        """
        if follower_count == 0:
            return 0.0

        weighted_engagement = (
            (self.likes or 0) + (self.comments or 0) * 2 + (self.shares or 0) * 3
        )
        return weighted_engagement / follower_count

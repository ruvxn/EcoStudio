"""
Social media account model for storing OAuth credentials and account information.
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, Enum as SQLEnum
from sqlalchemy.orm import relationship
import enum

from app.core.database import Base


class PlatformType(str, enum.Enum):
    """Supported social media platforms."""

    INSTAGRAM = "instagram"
    YOUTUBE = "youtube"


class SocialAccount(Base):
    """
    Represents a connected social media account.

    Stores OAuth tokens and platform-specific account information.
    Used as the parent table for posts, predictions, and scheduled content.
    """

    __tablename__ = "social_accounts"

    id = Column(Integer, primary_key=True, index=True)
    platform = Column(
        SQLEnum(PlatformType, native_enum=False),
        nullable=False,
        comment="Social media platform (instagram, youtube)",
    )
    account_id = Column(
        String(255),
        nullable=False,
        unique=True,
        index=True,
        comment="Platform-specific account ID",
    )
    username = Column(
        String(255), nullable=True, comment="Display username on the platform"
    )
    access_token = Column(
        Text, nullable=False, comment="OAuth access token (encrypted in production)"
    )
    token_expires_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="Token expiration timestamp (UTC)",
    )
    refresh_token = Column(
        Text, nullable=True, comment="OAuth refresh token (if supported)"
    )
    follower_count = Column(
        Integer, nullable=True, comment="Current follower count (synced periodically)"
    )
    last_sync_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="Timestamp of last data synchronization",
    )
    created_at = Column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    # Relationships
    posts = relationship("Post", back_populates="account", cascade="all, delete-orphan")
    predictions = relationship(
        "Prediction", back_populates="account", cascade="all, delete-orphan"
    )
    scheduled_posts = relationship(
        "ScheduledPost", back_populates="account", cascade="all, delete-orphan"
    )
    jobs = relationship("Job", back_populates="account", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<SocialAccount(id={self.id}, platform={self.platform}, username={self.username})>"

    def is_token_expired(self) -> bool:
        """Check if the OAuth token has expired."""
        if not self.token_expires_at:
            return False
        return datetime.utcnow() >= self.token_expires_at

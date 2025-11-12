"""
Pydantic schemas for social account API requests and responses.
"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field

from app.api.models import PlatformType


# Request Schemas
class SocialAccountConnect(BaseModel):
    """Request to initiate OAuth connection."""

    platform: PlatformType = Field(..., description="Social media platform to connect")
    redirect_url: Optional[str] = Field(
        None, description="Custom redirect URL after OAuth"
    )


class SocialAccountSync(BaseModel):
    """Request to sync historical data."""

    days: int = Field(
        default=90, ge=1, le=365, description="Number of days to sync (1-365)"
    )
    force_refresh: bool = Field(
        default=False, description="Force re-sync even if recently synced"
    )


# Response Schemas
class SocialAccountBase(BaseModel):
    """Base schema for social account."""

    platform: PlatformType
    account_id: str
    username: Optional[str] = None
    follower_count: Optional[int] = None


class SocialAccountResponse(SocialAccountBase):
    """Response schema for social account details."""

    id: int
    token_expires_at: Optional[datetime] = None
    last_sync_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SocialAccountStats(BaseModel):
    """Statistics for a social account."""

    total_posts: int = Field(..., description="Total historical posts fetched")
    avg_engagement: float = Field(..., description="Average engagement score")
    best_posting_hour: int = Field(..., description="Hour with best engagement (0-23)")
    best_posting_day: int = Field(..., description="Day with best engagement (0-6)")
    total_likes: int
    total_comments: int
    total_shares: int
    date_range_start: datetime
    date_range_end: datetime


class OAuthCallbackResponse(BaseModel):
    """Response after successful OAuth callback."""

    success: bool
    message: str
    account_id: Optional[int] = None
    redirect_to: str = Field(..., description="Frontend URL to redirect to")

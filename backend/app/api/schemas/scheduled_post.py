"""
Pydantic schemas for scheduled post API requests and responses.
"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field

from app.api.models import ContentType, PostStatus


# Request Schemas
class SchedulePostRequest(BaseModel):
    """Request to schedule a new post."""

    account_id: int
    scheduled_time: datetime = Field(..., description="When to post (UTC)")
    content: Optional[str] = Field(None, description="Caption (leave empty for AI generation)")
    content_type: ContentType = Field(default=ContentType.IMAGE)
    image_url: Optional[str] = Field(None, description="S3 URL or local path to media")
    auto_generate_content: bool = Field(
        default=True, description="Use AI to generate caption"
    )


class UpdateScheduledPostRequest(BaseModel):
    """Request to update a scheduled post."""

    content: Optional[str] = None
    scheduled_time: Optional[datetime] = None
    image_url: Optional[str] = None
    status: Optional[PostStatus] = None


class GenerateContentRequest(BaseModel):
    """Request to generate content for a scheduled post."""

    scheduled_post_id: int
    tone: str = Field(default="casual", description="Tone: casual, professional, inspirational")
    include_hashtags: bool = Field(default=True)
    include_emoji: bool = Field(default=True)


# Response Schemas
class ScheduledPostResponse(BaseModel):
    """Response schema for scheduled post."""

    id: int
    account_id: int
    scheduled_time: datetime
    content: Optional[str] = None
    content_type: ContentType
    image_url: Optional[str] = None
    status: PostStatus
    predicted_engagement: Optional[float] = None
    actual_engagement: Optional[float] = None
    platform_post_id: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime
    posted_at: Optional[datetime] = None
    updated_at: datetime

    model_config = {"from_attributes": True}


class ScheduledPostList(BaseModel):
    """List of scheduled posts with pagination."""

    posts: list[ScheduledPostResponse]
    total: int
    page: int
    page_size: int
    has_more: bool


class PostPerformanceComparison(BaseModel):
    """Compare predicted vs actual engagement."""

    scheduled_post_id: int
    predicted_engagement: float
    actual_engagement: float
    accuracy_percentage: float = Field(
        ..., description="How close prediction was to reality"
    )
    posted_at: datetime
    time_slot: str = Field(..., description="e.g., 'Monday 7PM'")

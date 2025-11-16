"""
Pydantic schemas for scheduled post API requests and responses.
"""
from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, Field, field_validator, HttpUrl
from urllib.parse import urlparse

from app.api.models import ContentType, PostStatus


# Request Schemas
class SchedulePostRequest(BaseModel):
    """Request to schedule a new post."""

    account_id: int
    scheduled_time: datetime = Field(..., description="When to post (UTC)")
    content: Optional[str] = Field(None, description="Caption (leave empty for AI generation)")
    content_type: ContentType = Field(default=ContentType.IMAGE)
    image_url: Optional[str] = Field(None, description="S3 URL or local path to media")
    auto_generate: bool = Field(
        default=True, description="Use AI to generate caption"
    )
    auto_post_enabled: bool = Field(
        default=True, description="Auto-post at scheduled time"
    )

    @field_validator('account_id')
    @classmethod
    def validate_account_id(cls, v: int) -> int:
        """Validate account_id is a positive integer."""
        if v <= 0:
            raise ValueError('account_id must be a positive integer')
        return v

    @field_validator('scheduled_time')
    @classmethod
    def validate_future_time(cls, v: datetime) -> datetime:
        """Validate that scheduled_time is in the future."""
        now = datetime.now(timezone.utc)

        # Make scheduled_time timezone-aware if it isn't already
        if v.tzinfo is None:
            v = v.replace(tzinfo=timezone.utc)

        if v <= now:
            raise ValueError(
                f'scheduled_time must be in the future. '
                f'Provided: {v.isoformat()}, Current time: {now.isoformat()}'
            )
        return v

    @field_validator('content')
    @classmethod
    def validate_caption_length(cls, v: Optional[str]) -> Optional[str]:
        """Validate caption length doesn't exceed Instagram's 2,200 character limit."""
        if v is not None and len(v) > 2200:
            raise ValueError(
                f'Caption exceeds Instagram maximum of 2,200 characters. '
                f'Current length: {len(v)} characters'
            )
        return v

    @field_validator('image_url')
    @classmethod
    def validate_image_url(cls, v: Optional[str]) -> Optional[str]:
        """Validate image URL format if provided."""
        if v is None:
            return v

        # Basic URL format validation
        try:
            result = urlparse(v)
            # Check if it has a scheme (http/https) and netloc (domain)
            if not all([result.scheme, result.netloc]):
                raise ValueError(
                    f'Invalid URL format. URL must include protocol (http/https) and domain. '
                    f'Provided: {v}'
                )

            # Ensure it's http or https
            if result.scheme not in ['http', 'https']:
                raise ValueError(
                    f'URL must use HTTP or HTTPS protocol. '
                    f'Provided scheme: {result.scheme}'
                )

            return v
        except Exception as e:
            raise ValueError(f'Invalid URL format: {str(e)}')


class UpdateScheduledPostRequest(BaseModel):
    """Request to update a scheduled post."""

    content: Optional[str] = None
    scheduled_time: Optional[datetime] = None
    image_url: Optional[str] = None
    status: Optional[PostStatus] = None
    user_approved: Optional[bool] = None

    @field_validator('scheduled_time')
    @classmethod
    def validate_future_time(cls, v: Optional[datetime]) -> Optional[datetime]:
        """Validate that scheduled_time is in the future if provided."""
        if v is None:
            return v

        now = datetime.now(timezone.utc)

        # Make scheduled_time timezone-aware if it isn't already
        if v.tzinfo is None:
            v = v.replace(tzinfo=timezone.utc)

        if v <= now:
            raise ValueError(
                f'scheduled_time must be in the future. '
                f'Provided: {v.isoformat()}, Current time: {now.isoformat()}'
            )
        return v

    @field_validator('content')
    @classmethod
    def validate_caption_length(cls, v: Optional[str]) -> Optional[str]:
        """Validate caption length doesn't exceed Instagram's 2,200 character limit."""
        if v is not None and len(v) > 2200:
            raise ValueError(
                f'Caption exceeds Instagram maximum of 2,200 characters. '
                f'Current length: {len(v)} characters'
            )
        return v

    @field_validator('image_url')
    @classmethod
    def validate_image_url(cls, v: Optional[str]) -> Optional[str]:
        """Validate image URL format if provided."""
        if v is None:
            return v

        # Basic URL format validation
        try:
            result = urlparse(v)
            # Check if it has a scheme (http/https) and netloc (domain)
            if not all([result.scheme, result.netloc]):
                raise ValueError(
                    f'Invalid URL format. URL must include protocol (http/https) and domain. '
                    f'Provided: {v}'
                )

            # Ensure it's http or https
            if result.scheme not in ['http', 'https']:
                raise ValueError(
                    f'URL must use HTTP or HTTPS protocol. '
                    f'Provided scheme: {result.scheme}'
                )

            return v
        except Exception as e:
            raise ValueError(f'Invalid URL format: {str(e)}')


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
    user_approved: bool = False
    user_edited: bool = False
    auto_post_enabled: bool = True
    predicted_engagement: Optional[float] = None
    actual_engagement: Optional[float] = None
    platform_post_id: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime
    posted_at: Optional[datetime] = None
    updated_at: datetime

    # Carbon-aware scheduling info
    generation_scheduled_for: Optional[datetime] = Field(None, description="When content generation will run")
    green_window_start: Optional[datetime] = Field(None, description="Optimal green window start")
    green_window_end: Optional[datetime] = Field(None, description="Optimal green window end")

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

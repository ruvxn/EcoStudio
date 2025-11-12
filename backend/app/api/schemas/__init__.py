"""
Pydantic schemas for API request/response validation.
"""
from .social_account import (
    SocialAccountConnect,
    SocialAccountSync,
    SocialAccountResponse,
    SocialAccountStats,
    OAuthCallbackResponse,
)
from .prediction import (
    PredictionRequest,
    TrainModelRequest,
    PredictionResponse,
    PredictionSchedule,
    TrainModelResponse,
)
from .scheduled_post import (
    SchedulePostRequest,
    UpdateScheduledPostRequest,
    GenerateContentRequest,
    ScheduledPostResponse,
    ScheduledPostList,
    PostPerformanceComparison,
)

__all__ = [
    # Social Account
    "SocialAccountConnect",
    "SocialAccountSync",
    "SocialAccountResponse",
    "SocialAccountStats",
    "OAuthCallbackResponse",
    # Predictions
    "PredictionRequest",
    "TrainModelRequest",
    "PredictionResponse",
    "PredictionSchedule",
    "TrainModelResponse",
    # Scheduled Posts
    "SchedulePostRequest",
    "UpdateScheduledPostRequest",
    "GenerateContentRequest",
    "ScheduledPostResponse",
    "ScheduledPostList",
    "PostPerformanceComparison",
]

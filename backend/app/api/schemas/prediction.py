"""
Pydantic schemas for prediction API requests and responses.
"""
from datetime import datetime, date
from typing import List, Optional
from pydantic import BaseModel, Field

from app.api.models import ContentType


# Request Schemas
class PredictionRequest(BaseModel):
    """Request to generate posting schedule predictions."""

    account_id: int = Field(..., description="Social account to predict for")
    days: int = Field(default=7, ge=1, le=30, description="Number of days to predict")
    content_type: ContentType = Field(
        default=ContentType.IMAGE, description="Type of content to predict for"
    )
    min_confidence: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Minimum confidence score for predictions",
    )


class TrainModelRequest(BaseModel):
    """Request to trigger model retraining."""

    account_id: int = Field(..., description="Account to train model for")
    force_retrain: bool = Field(
        default=False, description="Force retrain even if recently trained"
    )


# Response Schemas
class PredictionResponse(BaseModel):
    """Single prediction response."""

    id: int
    prediction_date: date
    day_of_week: int
    day_name: str = Field(..., description="Human-readable day name")
    hour: int = Field(..., ge=0, le=23, description="Hour of day in local time")
    content_type: ContentType
    predicted_engagement: float = Field(..., description="Expected engagement (0-1)")
    confidence_score: float = Field(..., description="Model confidence (0-1)")
    confidence_level: str = Field(..., description="Low/Medium/High")
    model_version: str
    created_at: datetime

    model_config = {"from_attributes": True}


class PredictionSchedule(BaseModel):
    """Weekly schedule of optimal posting times."""

    account_id: int
    predictions: List[PredictionResponse]
    total_predictions: int
    date_range_start: date
    date_range_end: date
    avg_predicted_engagement: float
    model_version: str


class TrainModelResponse(BaseModel):
    """Response after model training."""

    success: bool
    message: str
    model_version: str
    training_samples: int = Field(..., description="Number of posts used for training")
    model_accuracy: float = Field(..., description="R² score or similar metric")
    training_duration_seconds: int
    job_id: Optional[int] = Field(None, description="Background job ID if async")

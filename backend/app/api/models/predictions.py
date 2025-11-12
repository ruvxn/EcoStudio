"""
Prediction model for storing ML-generated optimal posting times.
"""
from datetime import datetime
from sqlalchemy import (
    Column,
    Integer,
    String,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Enum as SQLEnum,
)
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.api.models.posts import ContentType


class Prediction(Base):
    """
    ML-generated prediction for optimal posting time.

    Stores predictions from the engagement prediction model about when to post
    for maximum engagement. Generated weekly after model retraining.
    """

    __tablename__ = "predictions"

    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(
        Integer,
        ForeignKey("social_accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    prediction_date = Column(
        Date, nullable=False, index=True, comment="Date for this prediction"
    )
    day_of_week = Column(
        Integer, nullable=False, comment="0=Monday, 6=Sunday"
    )
    hour = Column(Integer, nullable=False, comment="Hour of day (0-23) in local time")
    content_type = Column(
        SQLEnum(ContentType),
        nullable=False,
        comment="Predicted content type for this slot",
    )
    predicted_engagement = Column(
        Float,
        nullable=False,
        index=True,
        comment="Expected engagement score (0.0 to 1.0)",
    )
    confidence_score = Column(
        Float,
        nullable=False,
        comment="Model confidence in this prediction (0.0 to 1.0)",
    )
    model_version = Column(
        String(50), nullable=False, comment="Version of the ML model used"
    )
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        comment="When this prediction was generated",
    )

    # Relationships
    account = relationship("SocialAccount", back_populates="predictions")

    # Composite indexes for queries
    __table_args__ = (
        Index("idx_predictions_account_date", "account_id", "prediction_date"),
        Index(
            "idx_predictions_account_engagement",
            "account_id",
            "predicted_engagement",
        ),
    )

    def __repr__(self):
        return f"<Prediction(date={self.prediction_date}, hour={self.hour}, engagement={self.predicted_engagement:.2f})>"

    @property
    def day_name(self) -> str:
        """Get human-readable day name."""
        days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        return days[self.day_of_week]

    @property
    def confidence_level(self) -> str:
        """Get human-readable confidence level."""
        if self.confidence_score >= 0.8:
            return "High"
        elif self.confidence_score >= 0.6:
            return "Medium"
        else:
            return "Low"

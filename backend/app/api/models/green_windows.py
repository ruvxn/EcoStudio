"""
Green window model for storing optimal execution periods with low carbon intensity.
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Float, Index

from app.core.database import Base


class GreenWindow(Base):
    """
    Recommended time windows with low carbon intensity for scheduling jobs.

    These windows are pre-calculated by analyzing carbon forecast data to identify
    continuous periods of low carbon intensity suitable for compute-intensive operations.
    """

    __tablename__ = "green_windows"

    id = Column(Integer, primary_key=True, index=True)
    region = Column(
        String(50),
        nullable=False,
        index=True,
        comment="Region code (e.g., 'AU-VIC')",
    )
    window_start = Column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
        comment="Start of green window (UTC)",
    )
    window_end = Column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
        comment="End of green window (UTC)",
    )
    avg_carbon_intensity = Column(
        Integer,
        nullable=True,
        comment="Average carbon intensity during window (gCO2/kWh)",
    )
    min_carbon_intensity = Column(
        Integer,
        nullable=True,
        comment="Minimum carbon intensity during window (gCO2/kWh)",
    )
    renewable_percentage = Column(
        Float,
        nullable=True,
        comment="Percentage of renewable energy during window",
    )
    recommendation_score = Column(
        Float,
        nullable=True,
        comment="Recommendation score (0-1, higher is better)",
    )
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        comment="When this window was calculated",
    )

    # Indexes
    __table_args__ = (
        Index("idx_green_windows_time", "window_start", "window_end"),
        Index("idx_green_windows_region_score", "region", "recommendation_score"),
    )

    def __repr__(self):
        return f"<GreenWindow(region={self.region}, start={self.window_start}, score={self.recommendation_score})>"

    @property
    def duration_hours(self) -> float:
        """Calculate window duration in hours."""
        if not self.window_start or not self.window_end:
            return 0.0
        return (self.window_end - self.window_start).total_seconds() / 3600

    def is_active(self) -> bool:
        """Check if window is currently active."""
        now = datetime.utcnow()
        return self.window_start <= now <= self.window_end

    def is_upcoming(self) -> bool:
        """Check if window is in the future."""
        return datetime.utcnow() < self.window_start

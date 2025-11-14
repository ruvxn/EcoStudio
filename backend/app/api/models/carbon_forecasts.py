"""
Carbon forecast model for storing electricity carbon intensity predictions.
Used in Phase 2 for eco-scheduling compute-intensive tasks.
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Index, UniqueConstraint

from app.core.database import Base


class CarbonForecast(Base):
    """
    Carbon intensity forecast for a specific region and time.

    Stores predictions of carbon intensity (gCO2/kWh) fetched from ElectricityMap API.
    Used to schedule compute-heavy operations during low-carbon windows.

    Note: This is implemented in Phase 1 but only actively used in Phase 2.
    """

    __tablename__ = "carbon_forecasts"

    id = Column(Integer, primary_key=True, index=True)
    region = Column(
        String(50),
        nullable=False,
        index=True,
        comment="Region code (e.g., 'AU-VIC' for Victoria, Australia)",
    )
    forecast_time = Column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
        comment="Timestamp for this forecast (UTC)",
    )
    carbon_intensity = Column(
        Integer,
        nullable=False,
        comment="Carbon intensity in grams CO2 per kWh",
    )
    is_renewable_high = Column(
        Boolean,
        nullable=True,
        default=False,
        comment="True if renewable energy percentage > 70%",
    )
    source = Column(
        String(100),
        nullable=True,
        comment="Data source (e.g., 'electricitymap', 'mock')",
    )
    fetched_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        comment="When this forecast was retrieved",
    )

    # Constraints and indexes
    __table_args__ = (
        UniqueConstraint("region", "forecast_time", name="uix_region_forecast_time"),
        Index("idx_carbon_region_time", "region", "forecast_time"),
        Index("idx_carbon_intensity", "carbon_intensity"),
    )

    def __repr__(self):
        return f"<CarbonForecast(region={self.region}, time={self.forecast_time}, intensity={self.carbon_intensity})>"

    @property
    def intensity_level(self) -> str:
        """
        Get human-readable carbon intensity level.

        Based on typical grid carbon intensity ranges:
        - Low: < 250 gCO2/kWh (renewable-heavy)
        - Medium: 250-500 gCO2/kWh (mixed)
        - High: > 500 gCO2/kWh (fossil fuel-heavy)
        """
        if self.carbon_intensity < 250:
            return "Low"
        elif self.carbon_intensity < 500:
            return "Medium"
        else:
            return "High"

    def is_green_window(self, threshold: int = 300) -> bool:
        """
        Check if this time window is considered 'green' for scheduling tasks.

        Args:
            threshold: Maximum carbon intensity (gCO2/kWh) to be considered green

        Returns:
            True if carbon intensity is below threshold
        """
        return self.carbon_intensity < threshold

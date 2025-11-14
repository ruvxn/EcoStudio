"""
Carbon savings model for tracking environmental impact of eco-scheduling.
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from app.core.database import Base


class CarbonSaving(Base):
    """
    Track carbon savings achieved by scheduling jobs during green windows.

    Records the actual carbon intensity when a job was executed versus what it
    would have been if scheduled randomly, quantifying the environmental benefit.
    """

    __tablename__ = "carbon_savings"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(
        Integer,
        ForeignKey("job_queue.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Reference to the job that was executed",
    )
    scheduled_carbon_intensity = Column(
        Integer,
        nullable=False,
        comment="Actual carbon intensity when job executed (gCO2/kWh)",
    )
    average_carbon_intensity = Column(
        Integer,
        nullable=True,
        comment="Average carbon intensity for the time period",
    )
    baseline_carbon_intensity = Column(
        Integer,
        nullable=True,
        comment="What carbon intensity would have been without optimization",
    )
    carbon_saved_grams = Column(
        Integer,
        nullable=True,
        comment="Grams of CO2 saved by smart scheduling",
    )
    energy_used_kwh = Column(
        Float,
        nullable=True,
        comment="Estimated energy consumption of the job (kWh)",
    )
    calculation_method = Column(
        String(100),
        nullable=True,
        comment="Method used to calculate savings",
    )
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        comment="When savings were calculated",
    )

    # Relationships
    job = relationship("Job", back_populates="carbon_saving")

    def __repr__(self):
        return f"<CarbonSaving(job_id={self.job_id}, saved={self.carbon_saved_grams}g CO2)>"

    @property
    def percentage_saved(self) -> float:
        """Calculate percentage of carbon saved."""
        if not self.baseline_carbon_intensity or not self.scheduled_carbon_intensity:
            return 0.0

        baseline_emissions = self.baseline_carbon_intensity * (self.energy_used_kwh or 1.0)
        if baseline_emissions == 0:
            return 0.0

        actual_emissions = self.scheduled_carbon_intensity * (self.energy_used_kwh or 1.0)
        return ((baseline_emissions - actual_emissions) / baseline_emissions) * 100

    @property
    def carbon_saved_kg(self) -> float:
        """Get carbon saved in kilograms."""
        return (self.carbon_saved_grams or 0) / 1000.0

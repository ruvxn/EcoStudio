"""
Execution log model for tracking job performance and carbon metrics.
"""
from datetime import datetime
from sqlalchemy import Column, Integer, Float, DateTime, ForeignKey, Index

from app.core.database import Base
from sqlalchemy.orm import relationship


class ExecutionLog(Base):
    """
    Log entry for job execution metrics.

    Tracks performance metrics and carbon savings for each executed job.
    Used for analytics and demonstrating environmental impact in Phase 2.
    """

    __tablename__ = "execution_logs"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(
        Integer,
        ForeignKey("job_queue.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Reference to the executed job",
    )
    carbon_saved_grams = Column(
        Integer,
        nullable=True,
        comment="Estimated grams of CO2 saved vs random scheduling (Phase 2)",
    )
    energy_used_kwh = Column(
        Float,
        nullable=True,
        comment="Estimated energy consumed by this job in kWh",
    )
    execution_time_seconds = Column(
        Integer,
        nullable=False,
        comment="How long the job took to execute",
    )
    baseline_carbon_intensity = Column(
        Integer,
        nullable=True,
        comment="Average carbon intensity for comparison (gCO2/kWh)",
    )
    actual_carbon_intensity = Column(
        Integer,
        nullable=True,
        comment="Actual carbon intensity when job ran (gCO2/kWh)",
    )
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        comment="When this log was created",
    )

    # Relationships
    job = relationship("Job", back_populates="execution_logs")

    # Indexes
    __table_args__ = (
        Index("idx_execution_logs_job", "job_id"),
        Index("idx_execution_logs_created", "created_at"),
    )

    def __repr__(self):
        return f"<ExecutionLog(job_id={self.job_id}, duration={self.execution_time_seconds}s, carbon_saved={self.carbon_saved_grams}g)>"

    @property
    def carbon_reduction_percentage(self) -> float:
        """
        Calculate percentage of carbon reduction vs baseline.

        Returns:
            Percentage reduction (0-100), or 0 if data unavailable
        """
        if not self.baseline_carbon_intensity or not self.actual_carbon_intensity:
            return 0.0

        if self.baseline_carbon_intensity == 0:
            return 0.0

        reduction = (
            (self.baseline_carbon_intensity - self.actual_carbon_intensity)
            / self.baseline_carbon_intensity
            * 100
        )
        return max(0.0, reduction)  # Don't show negative reductions

    def calculate_carbon_saved(
        self,
        baseline_intensity: int,
        actual_intensity: int,
        energy_kwh: float,
    ) -> int:
        """
        Calculate carbon saved in grams.

        Formula: (baseline_intensity - actual_intensity) * energy_kwh

        Args:
            baseline_intensity: Average carbon intensity (gCO2/kWh)
            actual_intensity: Carbon intensity when job ran (gCO2/kWh)
            energy_kwh: Energy consumed by the job

        Returns:
            Grams of CO2 saved (can be negative if scheduled during high carbon)
        """
        return int((baseline_intensity - actual_intensity) * energy_kwh)

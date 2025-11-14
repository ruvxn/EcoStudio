"""
System configuration model for storing application settings.
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB

from app.core.database import Base


class SystemConfig(Base):
    """
    System-wide configuration settings stored in database.

    Allows dynamic configuration of carbon thresholds, scheduler behavior,
    and other system parameters without code changes.
    """

    __tablename__ = "system_config"

    id = Column(Integer, primary_key=True, index=True)
    config_key = Column(
        String(100),
        nullable=False,
        unique=True,
        index=True,
        comment="Unique configuration key",
    )
    config_value = Column(
        JSONB,
        nullable=False,
        comment="Configuration value (JSON format for flexibility)",
    )
    description = Column(
        String(500),
        nullable=True,
        comment="Human-readable description of this setting",
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        comment="When this config was last updated",
    )

    # Constraints
    __table_args__ = (
        UniqueConstraint("config_key", name="uix_config_key"),
    )

    def __repr__(self):
        return f"<SystemConfig(key={self.config_key})>"

    def get_value(self, default=None):
        """
        Get the actual value from the JSONB field.

        For simple values, returns config_value['value'].
        For complex values, returns the entire config_value dict.
        """
        if isinstance(self.config_value, dict) and 'value' in self.config_value:
            return self.config_value.get('value', default)
        return self.config_value if self.config_value is not None else default

    @classmethod
    def get_default_configs(cls):
        """
        Return default configuration values for initial setup.

        Returns:
            List of dicts with config_key, config_value, and description
        """
        return [
            {
                "config_key": "carbon_threshold_low",
                "config_value": {
                    "value": 300,
                    "unit": "gCO2/kWh",
                },
                "description": "Carbon intensity considered low (good for scheduling)",
            },
            {
                "config_key": "carbon_threshold_high",
                "config_value": {
                    "value": 600,
                    "unit": "gCO2/kWh",
                },
                "description": "Carbon intensity considered high (avoid scheduling)",
            },
            {
                "config_key": "scheduler_enabled",
                "config_value": {
                    "value": True,
                },
                "description": "Enable automatic job scheduling",
            },
            {
                "config_key": "green_window_preference",
                "config_value": {
                    "value": 0.7,
                    "min": 0.0,
                    "max": 1.0,
                },
                "description": "How much to prioritize green windows (0=no preference, 1=only green)",
            },
            {
                "config_key": "default_region",
                "config_value": {
                    "value": "AU-VIC",
                },
                "description": "Default electricity grid region for carbon data",
            },
            {
                "config_key": "forecast_update_interval_hours",
                "config_value": {
                    "value": 6,
                },
                "description": "How often to fetch new carbon forecasts (hours)",
            },
        ]

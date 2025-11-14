"""
Carbon Forecast Service for fetching and managing carbon intensity data.
Integrates with ElectricityMap API to optimize job scheduling.
"""
import os
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import httpx
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.api.models.carbon_forecasts import CarbonForecast
from app.api.models.green_windows import GreenWindow

logger = logging.getLogger(__name__)


class CarbonForecastService:
    """
    Service for fetching and storing carbon intensity forecasts.

    Integrates with ElectricityMap API to retrieve grid carbon intensity
    predictions and identifies green windows for eco-scheduling.
    """

    def __init__(self, db: Session):
        """
        Initialize the carbon forecast service.

        Args:
            db: Database session
        """
        self.db = db
        self.api_key = os.getenv('ELECTRICITY_MAP_API_KEY')
        self.base_url = "https://api.electricitymap.org/v3"
        self.region = os.getenv('ELECTRICITY_MAP_REGION', 'AU-VIC')

    async def fetch_forecast(self, hours: int = 72) -> List[Dict]:
        """
        Fetch carbon intensity forecast from ElectricityMap API.

        Args:
            hours: Number of hours ahead to fetch (max 72)

        Returns:
            List of forecast dicts with forecast_time, carbon_intensity, is_renewable_high
        """
        if not self.api_key:
            logger.warning("ELECTRICITY_MAP_API_KEY not set, using mock data")
            return self._generate_mock_forecast(hours)

        url = f"{self.base_url}/carbon-intensity/forecast"

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    url,
                    params={"zone": self.region},
                    headers={"auth-token": self.api_key}
                )
                response.raise_for_status()
                data = response.json()

                forecasts = []
                for item in data.get('forecast', [])[:hours]:
                    # Parse datetime
                    forecast_time = datetime.fromisoformat(
                        item['datetime'].replace('Z', '+00:00')
                    )

                    forecasts.append({
                        'forecast_time': forecast_time,
                        'carbon_intensity': int(item.get('carbonIntensity', 400)),
                        'is_renewable_high': item.get('fossilFreePercentage', 0) > 70
                    })

                logger.info(f"Fetched {len(forecasts)} forecast entries from ElectricityMap")
                return forecasts

        except httpx.HTTPError as e:
            logger.error(f"Error fetching carbon forecast from API: {e}")
            logger.info("Falling back to mock data")
            return self._generate_mock_forecast(hours)
        except Exception as e:
            logger.error(f"Unexpected error fetching forecast: {e}")
            return self._generate_mock_forecast(hours)

    def _generate_mock_forecast(self, hours: int = 72) -> List[Dict]:
        """
        Generate mock forecast data for testing when API is unavailable.

        Creates a sinusoidal pattern with lower carbon during night hours.
        """
        import math

        forecasts = []
        now = datetime.utcnow()

        for i in range(hours):
            forecast_time = now + timedelta(hours=i)
            hour_of_day = forecast_time.hour

            # Sinusoidal pattern: lower at night (2-6 AM), higher during day (12-6 PM)
            base_intensity = 400
            variation = 200 * math.sin((hour_of_day - 6) * math.pi / 12)
            carbon_intensity = int(base_intensity + variation)

            # Clamp to reasonable range
            carbon_intensity = max(200, min(600, carbon_intensity))

            forecasts.append({
                'forecast_time': forecast_time,
                'carbon_intensity': carbon_intensity,
                'is_renewable_high': carbon_intensity < 300
            })

        logger.info(f"Generated {len(forecasts)} mock forecast entries")
        return forecasts

    def store_forecasts(self, forecasts: List[Dict]) -> int:
        """
        Store forecast data in database, handling duplicates.

        Args:
            forecasts: List of forecast dicts from fetch_forecast()

        Returns:
            Number of forecasts stored
        """
        stored_count = 0

        for forecast in forecasts:
            # Check if forecast already exists
            existing = self.db.query(CarbonForecast).filter(
                and_(
                    CarbonForecast.region == self.region,
                    CarbonForecast.forecast_time == forecast['forecast_time']
                )
            ).first()

            if existing:
                # Update existing forecast
                existing.carbon_intensity = forecast['carbon_intensity']
                existing.is_renewable_high = forecast['is_renewable_high']
                existing.fetched_at = datetime.utcnow()
            else:
                # Create new forecast
                new_forecast = CarbonForecast(
                    region=self.region,
                    forecast_time=forecast['forecast_time'],
                    carbon_intensity=forecast['carbon_intensity'],
                    is_renewable_high=forecast['is_renewable_high'],
                    source='electricitymap' if self.api_key else 'mock',
                    fetched_at=datetime.utcnow()
                )
                self.db.add(new_forecast)

            stored_count += 1

        self.db.commit()
        logger.info(f"Stored {stored_count} forecast entries in database")
        return stored_count

    async def update_forecasts(self) -> int:
        """
        Main method to fetch and store forecasts. Called by scheduler.

        Returns:
            Number of forecasts stored
        """
        logger.info(f"[{datetime.utcnow()}] Updating carbon forecasts...")

        forecasts = await self.fetch_forecast(hours=72)

        if forecasts:
            count = self.store_forecasts(forecasts)

            # Generate green window recommendations
            self.generate_green_windows()

            return count
        else:
            logger.warning("No forecasts received")
            return 0

    def get_current_intensity(self) -> int:
        """
        Get current carbon intensity from most recent forecast.

        Returns:
            Carbon intensity in gCO2/kWh (default 400 if no data)
        """
        now = datetime.utcnow()

        # Find forecast closest to current time (within 1 hour window)
        forecast = self.db.query(CarbonForecast).filter(
            and_(
                CarbonForecast.region == self.region,
                CarbonForecast.forecast_time >= now - timedelta(hours=1),
                CarbonForecast.forecast_time <= now + timedelta(hours=1)
            )
        ).order_by(CarbonForecast.forecast_time.asc()).first()

        if forecast:
            return forecast.carbon_intensity
        else:
            logger.warning("No current carbon forecast available, using default value")
            return 400  # Default moderate value

    def generate_green_windows(self, hours_ahead: int = 72) -> int:
        """
        Identify optimal green windows for scheduling jobs.

        A green window is a continuous period of low carbon intensity.
        Windows must be at least 2 hours long.

        Args:
            hours_ahead: How many hours ahead to analyze

        Returns:
            Number of green windows generated
        """
        now = datetime.utcnow()
        end_time = now + timedelta(hours=hours_ahead)

        # Fetch forecast data
        forecasts = self.db.query(CarbonForecast).filter(
            and_(
                CarbonForecast.region == self.region,
                CarbonForecast.forecast_time >= now,
                CarbonForecast.forecast_time <= end_time
            )
        ).order_by(CarbonForecast.forecast_time.asc()).all()

        if len(forecasts) < 6:  # Need at least 6 hours of data
            logger.warning(f"Insufficient forecast data for green windows ({len(forecasts)} hours)")
            return 0

        # Calculate statistics
        intensities = [f.carbon_intensity for f in forecasts]
        avg_intensity = sum(intensities) / len(intensities)
        min_intensity = min(intensities)

        # Threshold: 30% above minimum
        threshold = min_intensity + (avg_intensity - min_intensity) * 0.3
        logger.info(f"Green window threshold: {threshold:.0f} gCO2/kWh")

        # Find continuous low-carbon windows (minimum 2 hours)
        windows = []
        current_window_start = None
        current_window_intensities = []
        current_window_forecasts = []

        for i, forecast in enumerate(forecasts):
            if forecast.carbon_intensity <= threshold:
                if current_window_start is None:
                    current_window_start = forecast.forecast_time
                current_window_intensities.append(forecast.carbon_intensity)
                current_window_forecasts.append(forecast)
            else:
                if current_window_start and len(current_window_intensities) >= 2:
                    # Window ended, save it
                    windows.append({
                        'start': current_window_start,
                        'end': forecasts[i-1].forecast_time + timedelta(hours=1),  # Add 1 hour for window end
                        'avg_intensity': sum(current_window_intensities) / len(current_window_intensities),
                        'min_intensity': min(current_window_intensities),
                        'duration_hours': len(current_window_intensities)
                    })
                current_window_start = None
                current_window_intensities = []
                current_window_forecasts = []

        # Handle window at end of data
        if current_window_start and len(current_window_intensities) >= 2:
            windows.append({
                'start': current_window_start,
                'end': forecasts[-1].forecast_time + timedelta(hours=1),
                'avg_intensity': sum(current_window_intensities) / len(current_window_intensities),
                'min_intensity': min(current_window_intensities),
                'duration_hours': len(current_window_intensities)
            })

        # Calculate recommendation scores (0-1, higher is better)
        max_intensity = max(intensities)
        for window in windows:
            # Score based on intensity (70%) and duration (30%)
            intensity_score = 1 - (window['avg_intensity'] / max_intensity)
            duration_score = min(window['duration_hours'] / 6, 1.0)
            window['score'] = (intensity_score * 0.7) + (duration_score * 0.3)

        # Delete old windows for this region
        self.db.query(GreenWindow).filter(
            and_(
                GreenWindow.region == self.region,
                GreenWindow.window_start >= now
            )
        ).delete()

        # Store new windows
        for window in windows:
            green_window = GreenWindow(
                region=self.region,
                window_start=window['start'],
                window_end=window['end'],
                avg_carbon_intensity=int(window['avg_intensity']),
                min_carbon_intensity=window['min_intensity'],
                recommendation_score=window['score'],
                created_at=datetime.utcnow()
            )
            self.db.add(green_window)

        self.db.commit()
        logger.info(f"Generated {len(windows)} green windows")

        return len(windows)

    def get_forecasts(self, hours: int = 72) -> List[CarbonForecast]:
        """
        Get stored forecasts from database.

        Args:
            hours: Number of hours ahead to retrieve

        Returns:
            List of CarbonForecast objects
        """
        now = datetime.utcnow()
        end_time = now + timedelta(hours=hours)

        forecasts = self.db.query(CarbonForecast).filter(
            and_(
                CarbonForecast.region == self.region,
                CarbonForecast.forecast_time >= now,
                CarbonForecast.forecast_time <= end_time
            )
        ).order_by(CarbonForecast.forecast_time.asc()).all()

        return forecasts

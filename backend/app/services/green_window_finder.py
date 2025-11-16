"""
Green Window Finder Service for optimal job scheduling.
Finds the greenest execution windows based on carbon intensity forecasts.
"""
import os
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.api.models.green_windows import GreenWindow
from app.api.models.carbon_forecasts import CarbonForecast
from app.api.models.carbon_savings import CarbonSaving

logger = logging.getLogger(__name__)


class GreenWindowFinder:
    """
    Service for finding optimal execution windows with low carbon intensity.

    Analyzes green windows and forecasts to determine the best time to
    schedule compute-intensive jobs.
    """

    def __init__(self, db: Session):
        """
        Initialize the green window finder.

        Args:
            db: Database session
        """
        self.db = db
        self.region = os.getenv('ELECTRICITY_MAP_REGION', 'AU-VIC')

    def find_optimal_window(
        self,
        before_time: datetime,
        duration_minutes: int = 60,
        job_type: Optional[str] = None
    ) -> Optional[Dict]:
        """
        Find the greenest execution window before a deadline.

        Args:
            before_time: Job must complete before this time
            duration_minutes: Estimated job duration
            job_type: Type of job (for specific optimization rules)

        Returns:
            Dict with window_start, window_end, carbon_intensity, score
            or None if no suitable window found
        """
        now = datetime.now(timezone.utc)

        # Ensure before_time is in the future
        if before_time <= now:
            logger.warning("Deadline is in the past, scheduling immediately")
            return None

        # Query pre-calculated green windows
        duration_hours = duration_minutes / 60.0

        green_windows = self.db.query(GreenWindow).filter(
            and_(
                GreenWindow.region == self.region,
                GreenWindow.window_start >= now,
                GreenWindow.window_end <= before_time,
                # Window must be long enough for the job
                GreenWindow.window_end >= GreenWindow.window_start + timedelta(hours=duration_hours)
            )
        ).order_by(GreenWindow.recommendation_score.desc()).all()

        if green_windows:
            # Use the best green window
            best_window = green_windows[0]
            logger.info(
                f"Found optimal green window: {best_window.window_start} "
                f"(score: {best_window.recommendation_score:.2f}, "
                f"intensity: {best_window.avg_carbon_intensity} gCO2/kWh)"
            )

            return {
                'window_start': best_window.window_start,
                'window_end': best_window.window_end,
                'carbon_intensity': best_window.avg_carbon_intensity,
                'score': best_window.recommendation_score
            }

        # Fallback: Find lowest carbon intensity hour-by-hour from forecasts
        logger.info("No pre-calculated green windows found, searching forecasts...")

        forecasts = self.db.query(CarbonForecast).filter(
            and_(
                CarbonForecast.region == self.region,
                CarbonForecast.forecast_time >= now,
                CarbonForecast.forecast_time <= before_time - timedelta(minutes=duration_minutes)
            )
        ).order_by(CarbonForecast.carbon_intensity.asc()).all()

        if forecasts:
            # Use the forecast with lowest carbon intensity
            best_forecast = forecasts[0]
            logger.info(
                f"Found lowest carbon forecast: {best_forecast.forecast_time} "
                f"({best_forecast.carbon_intensity} gCO2/kWh)"
            )

            return {
                'window_start': best_forecast.forecast_time,
                'window_end': best_forecast.forecast_time + timedelta(minutes=duration_minutes),
                'carbon_intensity': best_forecast.carbon_intensity,
                'score': 0.5  # Medium confidence (not a pre-identified window)
            }

        # No green window found, schedule immediately
        logger.warning("No suitable green window found, will schedule immediately")
        return None

    def calculate_carbon_savings(
        self,
        actual_carbon_intensity: int,
        scheduled_time: datetime,
        duration_minutes: int,
        job_type: Optional[str] = None
    ) -> Dict:
        """
        Calculate how much carbon was saved by smart scheduling.

        Compares against average and random baseline.

        Args:
            actual_carbon_intensity: Carbon intensity when job executed
            scheduled_time: When the job was scheduled
            duration_minutes: How long the job took
            job_type: Type of job (affects energy estimation)

        Returns:
            Dict with carbon savings metrics
        """
        # Get average carbon intensity for the region (7-day window)
        now = datetime.now(timezone.utc)
        avg_query = self.db.query(CarbonForecast).filter(
            and_(
                CarbonForecast.region == self.region,
                CarbonForecast.forecast_time >= now - timedelta(days=7),
                CarbonForecast.forecast_time <= now + timedelta(days=7)
            )
        ).all()

        if avg_query:
            avg_intensity = sum(f.carbon_intensity for f in avg_query) / len(avg_query)
        else:
            avg_intensity = 400  # Default if no data

        # Estimate energy consumption based on job type and duration
        # These are rough estimates and should be calibrated based on actual measurements
        energy_kwh_per_hour = {
            'RETRAIN_MODEL': 2.0,  # Model training is compute-intensive
            'GENERATE_CONTENT': 0.5,  # AI content generation
            'SYNC_POSTS': 0.1,  # API calls, minimal compute
            'POST_CONTENT': 0.1,  # Publishing content
            'FETCH_CARBON_FORECAST': 0.05,  # Just an API call
            'CALCULATE_ENGAGEMENT': 0.3,  # Database queries and calculations
        }.get(job_type, 1.0)  # Default 1 kWh/hour

        energy_kwh = (duration_minutes / 60) * energy_kwh_per_hour

        # Calculate emissions
        # Carbon intensity is in gCO2/kWh, so multiply by energy
        baseline_emissions_grams = avg_intensity * energy_kwh
        actual_emissions_grams = actual_carbon_intensity * energy_kwh
        carbon_saved_grams = int(baseline_emissions_grams - actual_emissions_grams)

        # Calculate percentage saved
        percentage_saved = 0.0
        if baseline_emissions_grams > 0:
            percentage_saved = ((baseline_emissions_grams - actual_emissions_grams) / baseline_emissions_grams) * 100

        logger.info(
            f"Carbon savings: {carbon_saved_grams}g CO2 saved "
            f"({percentage_saved:.1f}% reduction)"
        )

        return {
            'scheduled_carbon_intensity': actual_carbon_intensity,
            'average_carbon_intensity': int(avg_intensity),
            'baseline_carbon_intensity': int(avg_intensity),
            'carbon_saved_grams': carbon_saved_grams,
            'energy_used_kwh': energy_kwh,
            'percentage_saved': percentage_saved,
            'calculation_method': 'baseline_comparison'
        }

    def store_carbon_savings(
        self,
        job_id: int,
        savings_data: Dict
    ) -> CarbonSaving:
        """
        Store carbon savings record in database.

        Args:
            job_id: ID of the job that was executed
            savings_data: Dict from calculate_carbon_savings()

        Returns:
            Created CarbonSaving object
        """
        carbon_saving = CarbonSaving(
            job_id=job_id,
            scheduled_carbon_intensity=savings_data['scheduled_carbon_intensity'],
            average_carbon_intensity=savings_data.get('average_carbon_intensity'),
            baseline_carbon_intensity=savings_data['baseline_carbon_intensity'],
            carbon_saved_grams=savings_data['carbon_saved_grams'],
            energy_used_kwh=savings_data['energy_used_kwh'],
            calculation_method=savings_data.get('calculation_method', 'baseline_comparison'),
            created_at=datetime.now(timezone.utc)
        )

        self.db.add(carbon_saving)
        self.db.commit()
        self.db.refresh(carbon_saving)

        logger.info(f"Stored carbon savings for job {job_id}: {savings_data['carbon_saved_grams']}g CO2")

        return carbon_saving

    def get_green_windows(self, hours_ahead: int = 72) -> list[GreenWindow]:
        """
        Get all green windows for the next N hours.

        Args:
            hours_ahead: How many hours ahead to retrieve

        Returns:
            List of GreenWindow objects
        """
        now = datetime.now(timezone.utc)
        end_time = now + timedelta(hours=hours_ahead)

        windows = self.db.query(GreenWindow).filter(
            and_(
                GreenWindow.region == self.region,
                GreenWindow.window_start >= now,
                GreenWindow.window_start <= end_time
            )
        ).order_by(GreenWindow.recommendation_score.desc()).all()

        return windows

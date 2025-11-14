"""
Carbon API endpoints for managing carbon intensity forecasts and green windows.
"""
import os
import logging
from datetime import datetime, timedelta
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.core.database import get_db
from app.services.carbon_forecast_service import CarbonForecastService
from app.services.green_window_finder import GreenWindowFinder

logger = logging.getLogger(__name__)

router = APIRouter()


# Response Models
class CarbonIntensityResponse(BaseModel):
    """Response model for current carbon intensity."""
    intensity: int
    unit: str = "gCO2/kWh"
    category: str  # "low", "medium", "high"
    color: str  # "green", "yellow", "red"
    timestamp: str


class ForecastDataPoint(BaseModel):
    """Single forecast data point."""
    time: str
    intensity: int
    is_green: bool
    is_renewable_high: bool


class ForecastResponse(BaseModel):
    """Response model for carbon forecast."""
    region: str
    forecast_start: str
    forecast_end: str
    data: List[ForecastDataPoint]


class GreenWindowResponse(BaseModel):
    """Single green window response."""
    start: str
    end: str
    duration_hours: float
    avg_intensity: int
    min_intensity: int
    score: float


class GreenWindowsResponse(BaseModel):
    """Response model for green windows."""
    region: str
    windows: List[GreenWindowResponse]


@router.get("/current", response_model=CarbonIntensityResponse)
async def get_current_carbon(db: Session = Depends(get_db)):
    """
    Get current carbon intensity.

    Returns the current grid carbon intensity with categorization
    (low/medium/high) for the configured region.
    """
    try:
        service = CarbonForecastService(db)
        intensity = service.get_current_intensity()

        # Categorize based on intensity
        if intensity < 300:
            category = "low"
            color = "green"
        elif intensity < 500:
            category = "medium"
            color = "yellow"
        else:
            category = "high"
            color = "red"

        return CarbonIntensityResponse(
            intensity=intensity,
            category=category,
            color=color,
            timestamp=datetime.utcnow().isoformat()
        )

    except Exception as e:
        logger.error(f"Error fetching current carbon intensity: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch current carbon intensity")


@router.get("/forecast", response_model=ForecastResponse)
async def get_carbon_forecast(
    hours: int = Query(72, ge=1, le=168, description="Hours ahead to forecast"),
    db: Session = Depends(get_db)
):
    """
    Get carbon intensity forecast for next N hours.

    Returns hourly carbon intensity predictions for the configured region.
    Data is fetched from ElectricityMap API and cached in the database.

    Args:
        hours: Number of hours ahead (1-168, default 72)
    """
    try:
        service = CarbonForecastService(db)
        forecasts = service.get_forecasts(hours=hours)

        region = os.getenv('ELECTRICITY_MAP_REGION', 'AU-VIC')
        now = datetime.utcnow()

        data = [
            ForecastDataPoint(
                time=f.forecast_time.isoformat(),
                intensity=f.carbon_intensity,
                is_green=f.carbon_intensity < 300,
                is_renewable_high=f.is_renewable_high or False
            )
            for f in forecasts
        ]

        return ForecastResponse(
            region=region,
            forecast_start=now.isoformat(),
            forecast_end=(now + timedelta(hours=hours)).isoformat(),
            data=data
        )

    except Exception as e:
        logger.error(f"Error fetching carbon forecast: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch carbon forecast")


@router.get("/windows", response_model=GreenWindowsResponse)
async def get_green_windows(
    hours_ahead: int = Query(72, ge=1, le=168, description="Hours ahead to retrieve"),
    db: Session = Depends(get_db)
):
    """
    Get recommended green windows for job scheduling.

    Returns optimal time windows with low carbon intensity for scheduling
    compute-intensive operations.

    Args:
        hours_ahead: Number of hours ahead to retrieve (1-168, default 72)
    """
    try:
        finder = GreenWindowFinder(db)
        windows = finder.get_green_windows(hours_ahead=hours_ahead)

        region = os.getenv('ELECTRICITY_MAP_REGION', 'AU-VIC')

        window_responses = [
            GreenWindowResponse(
                start=w.window_start.isoformat(),
                end=w.window_end.isoformat(),
                duration_hours=w.duration_hours,
                avg_intensity=w.avg_carbon_intensity,
                min_intensity=w.min_carbon_intensity,
                score=round(w.recommendation_score, 2)
            )
            for w in windows
        ]

        return GreenWindowsResponse(
            region=region,
            windows=window_responses
        )

    except Exception as e:
        logger.error(f"Error fetching green windows: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch green windows")


@router.post("/forecast/update")
async def trigger_forecast_update(db: Session = Depends(get_db)):
    """
    Manually trigger a carbon forecast update.

    This endpoint allows manual triggering of forecast updates
    outside the regular schedule. Useful for testing or forcing
    immediate updates.
    """
    try:
        service = CarbonForecastService(db)
        count = await service.update_forecasts()

        return {
            "status": "success",
            "message": f"Updated {count} forecast entries",
            "timestamp": datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error(f"Error updating forecasts: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to update forecasts")

"""
Temporal feature engineering for time-based patterns
"""
import numpy as np
import pandas as pd
from datetime import datetime
from typing import Dict, Any

from ..config import TIME_OF_DAY_BINS


def extract_temporal_features(df: pd.DataFrame, timestamp_col: str = "posted_at") -> pd.DataFrame:
    """
    Extract time-based features from timestamp column

    Args:
        df: DataFrame with timestamp column
        timestamp_col: Name of the timestamp column

    Returns:
        DataFrame with additional temporal features
    """
    df = df.copy()

    # Ensure timestamp is datetime
    if not pd.api.types.is_datetime64_any_dtype(df[timestamp_col]):
        df[timestamp_col] = pd.to_datetime(df[timestamp_col])

    # Basic temporal features
    df["hour"] = df[timestamp_col].dt.hour
    df["day_of_week"] = df[timestamp_col].dt.dayofweek  # 0=Monday, 6=Sunday
    df["day_of_month"] = df[timestamp_col].dt.day
    df["month"] = df[timestamp_col].dt.month
    df["is_weekend"] = (df["day_of_week"] >= 5).astype(int)

    # Cyclical encoding for hour (24-hour cycle)
    df["hour_sin"] = np.sin(2 * np.pi * df["hour"] / 24)
    df["hour_cos"] = np.cos(2 * np.pi * df["hour"] / 24)

    # Cyclical encoding for day of week (7-day cycle)
    df["day_sin"] = np.sin(2 * np.pi * df["day_of_week"] / 7)
    df["day_cos"] = np.cos(2 * np.pi * df["day_of_week"] / 7)

    # Time of day category
    df["time_of_day"] = df["hour"].apply(categorize_time_of_day)

    return df


def categorize_time_of_day(hour: int) -> str:
    """
    Categorize hour into time of day period

    Args:
        hour: Hour of day (0-23)

    Returns:
        Time period category (morning, afternoon, evening, night)
    """
    for period, (start, end) in TIME_OF_DAY_BINS.items():
        if start < end:  # Normal range (e.g., 6-12)
            if start <= hour < end:
                return period
        else:  # Wraps around midnight (e.g., 21-6)
            if hour >= start or hour < end:
                return period
    return "night"  # Default


def add_temporal_interactions(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add interaction features between temporal variables

    Args:
        df: DataFrame with temporal features

    Returns:
        DataFrame with interaction features added
    """
    df = df.copy()

    # Hour × Day interactions
    df["hour_day_interaction"] = df["hour"] * df["day_of_week"]

    # Weekend × Evening interaction
    df["weekend_evening"] = (
        (df["is_weekend"] == 1) & (df["time_of_day"] == "evening")
    ).astype(int)

    # Weekend × Night interaction
    df["weekend_night"] = (
        (df["is_weekend"] == 1) & (df["time_of_day"] == "night")
    ).astype(int)

    return df


def get_temporal_stats(df: pd.DataFrame, engagement_col: str = "engagement_score") -> Dict[str, Any]:
    """
    Calculate temporal statistics for the dataset

    Args:
        df: DataFrame with temporal features and engagement
        engagement_col: Name of the engagement score column

    Returns:
        Dictionary of temporal statistics
    """
    stats = {
        "date_range": {
            "start": df["posted_at"].min().isoformat() if "posted_at" in df else None,
            "end": df["posted_at"].max().isoformat() if "posted_at" in df else None,
        },
        "avg_engagement_by_hour": (
            df.groupby("hour")[engagement_col].mean().to_dict()
            if "hour" in df else {}
        ),
        "avg_engagement_by_day": (
            df.groupby("day_of_week")[engagement_col].mean().to_dict()
            if "day_of_week" in df else {}
        ),
        "avg_engagement_by_time_of_day": (
            df.groupby("time_of_day")[engagement_col].mean().to_dict()
            if "time_of_day" in df else {}
        ),
        "weekend_vs_weekday": {
            "weekend": df[df["is_weekend"] == 1][engagement_col].mean() if "is_weekend" in df else None,
            "weekday": df[df["is_weekend"] == 0][engagement_col].mean() if "is_weekend" in df else None,
        },
    }

    return stats


def generate_future_temporal_features(
    days_ahead: int = 7,
    hours: list = None,
) -> pd.DataFrame:
    """
    Generate temporal features for future dates/times

    Args:
        days_ahead: Number of days to generate predictions for
        hours: List of hours to include (defaults to all 24 hours)

    Returns:
        DataFrame with temporal features for future dates
    """
    if hours is None:
        hours = list(range(24))

    # Generate future dates
    start_date = datetime.now()
    dates = pd.date_range(start=start_date, periods=days_ahead, freq="D")

    # Create all combinations of dates and hours
    future_data = []
    for date in dates:
        for hour in hours:
            timestamp = date.replace(hour=hour, minute=0, second=0, microsecond=0)
            future_data.append({"posted_at": timestamp})

    df = pd.DataFrame(future_data)

    # Extract temporal features
    df = extract_temporal_features(df)

    return df

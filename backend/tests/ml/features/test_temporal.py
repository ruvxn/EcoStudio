"""
Tests for temporal feature engineering
"""
import pytest
import pandas as pd
import numpy as np
from datetime import datetime

from app.ml.features.temporal import (
    extract_temporal_features,
    categorize_time_of_day,
    add_temporal_interactions,
    get_temporal_stats,
    generate_future_temporal_features,
)


class TestExtractTemporalFeatures:
    """Test temporal feature extraction"""

    def test_basic_temporal_features(self):
        """Test extraction of basic temporal features"""
        df = pd.DataFrame({
            "posted_at": [
                datetime(2025, 1, 1, 10, 30),  # Wednesday morning
                datetime(2025, 1, 6, 18, 45),  # Monday evening
            ]
        })

        result = extract_temporal_features(df)

        # Check hour
        assert result["hour"].tolist() == [10, 18]

        # Check day of week (0=Monday)
        assert result["day_of_week"].tolist() == [2, 0]

        # Check weekend flag
        assert result["is_weekend"].tolist() == [0, 0]

    def test_cyclical_encoding(self):
        """Test cyclical sin/cos encoding"""
        df = pd.DataFrame({
            "posted_at": [datetime(2025, 1, 1, 0, 0)]  # Midnight
        })

        result = extract_temporal_features(df)

        # At midnight (hour=0), cos should be 1, sin should be 0
        assert np.isclose(result["hour_cos"].iloc[0], 1.0, atol=0.01)
        assert np.isclose(result["hour_sin"].iloc[0], 0.0, atol=0.01)

    def test_weekend_detection(self):
        """Test weekend detection"""
        df = pd.DataFrame({
            "posted_at": [
                datetime(2025, 1, 3, 10, 0),   # Friday - not weekend
                datetime(2025, 1, 4, 10, 0),   # Saturday - weekend
                datetime(2025, 1, 5, 10, 0),   # Sunday - weekend
                datetime(2025, 1, 6, 10, 0),   # Monday - not weekend
            ]
        })

        result = extract_temporal_features(df)

        assert result["is_weekend"].tolist() == [0, 1, 1, 0]

    def test_time_of_day_categorization(self):
        """Test time of day category assignment"""
        df = pd.DataFrame({
            "posted_at": [
                datetime(2025, 1, 1, 8, 0),   # Morning
                datetime(2025, 1, 1, 14, 0),  # Afternoon
                datetime(2025, 1, 1, 19, 0),  # Evening
                datetime(2025, 1, 1, 23, 0),  # Night
            ]
        })

        result = extract_temporal_features(df)

        assert result["time_of_day"].tolist() == ["morning", "afternoon", "evening", "night"]


class TestCategorizeTimeOfDay:
    """Test time of day categorization function"""

    def test_morning_hours(self):
        assert categorize_time_of_day(6) == "morning"
        assert categorize_time_of_day(9) == "morning"
        assert categorize_time_of_day(11) == "morning"

    def test_afternoon_hours(self):
        assert categorize_time_of_day(12) == "afternoon"
        assert categorize_time_of_day(15) == "afternoon"
        assert categorize_time_of_day(16) == "afternoon"

    def test_evening_hours(self):
        assert categorize_time_of_day(17) == "evening"
        assert categorize_time_of_day(19) == "evening"
        assert categorize_time_of_day(20) == "evening"

    def test_night_hours(self):
        assert categorize_time_of_day(21) == "night"
        assert categorize_time_of_day(0) == "night"
        assert categorize_time_of_day(5) == "night"


class TestTemporalInteractions:
    """Test temporal interaction features"""

    def test_add_temporal_interactions(self):
        """Test interaction feature creation"""
        df = pd.DataFrame({
            "posted_at": [datetime(2025, 1, 4, 19, 0)],  # Saturday evening
            "hour": [19],
            "day_of_week": [5],
            "is_weekend": [1],
            "time_of_day": ["evening"],
        })

        result = add_temporal_interactions(df)

        # Check hour × day interaction
        assert result["hour_day_interaction"].iloc[0] == 19 * 5

        # Check weekend × evening
        assert result["weekend_evening"].iloc[0] == 1


class TestTemporalStats:
    """Test temporal statistics calculation"""

    def test_get_temporal_stats(self, sample_dataframe):
        """Test temporal statistics generation"""
        df = sample_dataframe.copy()
        df = extract_temporal_features(df)

        stats = get_temporal_stats(df)

        assert "date_range" in stats
        assert "avg_engagement_by_hour" in stats
        assert "avg_engagement_by_day" in stats
        assert "avg_engagement_by_time_of_day" in stats
        assert "weekend_vs_weekday" in stats


class TestGenerateFutureTemporalFeatures:
    """Test future temporal feature generation"""

    def test_generate_future_features(self):
        """Test generation of future temporal features"""
        result = generate_future_temporal_features(days_ahead=7, hours=[9, 12, 18])

        # Should generate 7 days × 3 hours = 21 rows
        assert len(result) == 21

        # Should have all temporal features
        assert "hour" in result.columns
        assert "day_of_week" in result.columns
        assert "hour_sin" in result.columns
        assert "time_of_day" in result.columns

    def test_generate_all_hours(self):
        """Test generation with all 24 hours"""
        result = generate_future_temporal_features(days_ahead=1)

        # Should generate 1 day × 24 hours = 24 rows
        assert len(result) == 24

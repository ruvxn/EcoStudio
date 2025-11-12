"""
Generate predictions for optimal posting times
"""
import pandas as pd
import numpy as np
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta

from ..features.temporal import generate_future_temporal_features
from ..features.content import generate_content_type_combinations
from ..training.data_loader import DataLoader
from ..config import DEFAULT_PREDICTION_DAYS, MAX_PREDICTION_DAYS, TOP_PREDICTIONS_TO_STORE


class Predictor:
    """
    Generates predictions for optimal posting times
    """

    def __init__(self, model, feature_engineer, db_session=None):
        """
        Initialize predictor

        Args:
            model: Trained model
            feature_engineer: Fitted FeatureEngineer instance
            db_session: Optional database session for loading historical averages
        """
        self.model = model
        self.feature_engineer = feature_engineer
        self.db = db_session
        self.historical_averages = None

    def predict_schedule(
        self,
        account_id: int,
        days_ahead: int = DEFAULT_PREDICTION_DAYS,
        content_types: Optional[List[str]] = None,
        hours: Optional[List[int]] = None,
        top_n: int = TOP_PREDICTIONS_TO_STORE,
    ) -> List[Dict[str, Any]]:
        """
        Generate optimal posting schedule predictions

        Args:
            account_id: Social account ID
            days_ahead: Number of days to predict (max 30)
            content_types: List of content types to predict for (default: all)
            hours: List of hours to include (default: all 24 hours)
            top_n: Number of top predictions to return

        Returns:
            List of prediction dictionaries sorted by predicted engagement
        """
        # Validate days_ahead
        days_ahead = min(days_ahead, MAX_PREDICTION_DAYS)

        # Load historical averages if using advanced features
        if self.feature_engineer.use_advanced_features and self.db:
            data_loader = DataLoader(self.db)
            self.historical_averages = data_loader.get_historical_averages(account_id)

        # Generate temporal features for future dates
        temporal_df = generate_future_temporal_features(days_ahead, hours)

        # Get content types to predict
        if content_types is None:
            content_types = generate_content_type_combinations()

        # Create all combinations of temporal features and content types
        predictions = []

        for content_type in content_types:
            # Create copy of temporal features for this content type
            df = temporal_df.copy()
            df["content_type"] = content_type

            # Add default content features (median values)
            df = self._add_default_content_features(df)

            # Add advanced features if needed
            if self.feature_engineer.use_advanced_features and self.historical_averages:
                df = self._add_historical_features(df, content_type)

            # Transform features
            X = self.feature_engineer.transform(df)

            # Make predictions
            y_pred = self.model.predict(X)

            # Combine with original data
            df["predicted_engagement"] = y_pred

            # Convert to prediction records
            for idx, row in df.iterrows():
                predictions.append({
                    "posted_at": row["posted_at"],
                    "hour": int(row["hour"]),
                    "day_of_week": int(row["day_of_week"]),
                    "content_type": content_type,
                    "predicted_engagement": float(row["predicted_engagement"]),
                    "time_of_day": row.get("time_of_day", ""),
                    "is_weekend": bool(row["is_weekend"]),
                })

        # Sort by predicted engagement
        predictions.sort(key=lambda x: x["predicted_engagement"], reverse=True)

        # Return top N
        return predictions[:top_n]

    def predict_single(
        self,
        posted_at: datetime,
        content_type: str,
        caption: str = "",
        account_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Predict engagement for a single post

        Args:
            posted_at: When the post will be published
            content_type: Type of content
            caption: Post caption (optional)
            account_id: Account ID for historical features (optional)

        Returns:
            Prediction dictionary
        """
        # Create DataFrame with single row
        df = pd.DataFrame([{
            "posted_at": posted_at,
            "content_type": content_type,
            "caption": caption,
        }])

        # Add content features
        from ..features.content import extract_content_features
        df = extract_content_features(df)

        # Add advanced features if needed
        if self.feature_engineer.use_advanced_features and account_id and self.db:
            if not self.historical_averages:
                data_loader = DataLoader(self.db)
                self.historical_averages = data_loader.get_historical_averages(account_id)

            df = self._add_historical_features(df, content_type)

        # Transform features
        X = self.feature_engineer.transform(df)

        # Make prediction
        y_pred = self.model.predict(X)

        return {
            "posted_at": posted_at.isoformat(),
            "content_type": content_type,
            "predicted_engagement": float(y_pred[0]),
        }

    def compare_times(
        self,
        times: List[datetime],
        content_type: str,
        account_id: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Compare predicted engagement across different times

        Args:
            times: List of datetime objects to compare
            content_type: Type of content
            account_id: Account ID for historical features (optional)

        Returns:
            List of predictions sorted by engagement
        """
        predictions = []

        for time in times:
            pred = self.predict_single(time, content_type, account_id=account_id)
            predictions.append(pred)

        # Sort by predicted engagement
        predictions.sort(key=lambda x: x["predicted_engagement"], reverse=True)

        return predictions

    def _add_default_content_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Add default content features for prediction

        Uses median/typical values for features that depend on actual content
        """
        df = df.copy()

        # Default caption features (median values from typical posts)
        df["caption"] = ""
        df["caption_length"] = 150  # Typical Instagram caption length
        df["caption_word_count"] = 25
        df["has_caption"] = 1
        df["hashtag_count"] = 5  # Typical hashtag count
        df["hashtag_density"] = 0.2
        df["has_emoji"] = 1  # Most posts have emoji
        df["emoji_count"] = 2
        df["mention_count"] = 0
        df["has_question"] = 0
        df["has_cta"] = 0

        return df

    def _add_historical_features(self, df: pd.DataFrame, content_type: str) -> pd.DataFrame:
        """
        Add historical average features from past performance

        Args:
            df: DataFrame with temporal features
            content_type: Content type for this prediction

        Returns:
            DataFrame with historical features added
        """
        if not self.historical_averages:
            return df

        df = df.copy()

        # Account average
        df["account_avg_engagement"] = self.historical_averages["account_avg_engagement"]

        # Content type average
        content_avg = self.historical_averages["content_type_avg_engagement"].get(
            content_type,
            self.historical_averages["account_avg_engagement"]  # Fallback to account avg
        )
        df["content_type_avg_engagement"] = content_avg

        # Hour averages
        df["hour_avg_engagement"] = df["hour"].map(
            lambda h: self.historical_averages["hour_avg_engagement"].get(
                h,
                self.historical_averages["account_avg_engagement"]
            )
        )

        # Day of week averages
        df["day_avg_engagement"] = df["day_of_week"].map(
            lambda d: self.historical_averages["day_avg_engagement"].get(
                d,
                self.historical_averages["account_avg_engagement"]
            )
        )

        # Recent trend
        df["recent_trend"] = self.historical_averages["recent_trend"]

        return df

    def get_best_times_by_content(
        self,
        account_id: int,
        days_ahead: int = 7,
        top_n: int = 5,
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Get best posting times for each content type

        Args:
            account_id: Social account ID
            days_ahead: Number of days to predict
            top_n: Number of top times per content type

        Returns:
            Dictionary mapping content type to list of best times
        """
        content_types = generate_content_type_combinations()
        results = {}

        for content_type in content_types:
            predictions = self.predict_schedule(
                account_id=account_id,
                days_ahead=days_ahead,
                content_types=[content_type],
                top_n=top_n,
            )
            results[content_type] = predictions

        return results

    def get_weekly_heatmap(
        self,
        account_id: int,
        content_type: str = "photo",
    ) -> Dict[str, Any]:
        """
        Generate weekly heatmap of predicted engagement

        Args:
            account_id: Social account ID
            content_type: Content type to analyze

        Returns:
            Dictionary with heatmap data
        """
        # Generate predictions for next 7 days, all hours
        predictions = self.predict_schedule(
            account_id=account_id,
            days_ahead=7,
            content_types=[content_type],
            top_n=168,  # 7 days * 24 hours
        )

        # Create heatmap matrix [7 days x 24 hours]
        heatmap = np.zeros((7, 24))

        for pred in predictions:
            day = pred["day_of_week"]
            hour = pred["hour"]
            engagement = pred["predicted_engagement"]
            heatmap[day, hour] = engagement

        # Convert to dictionary format
        heatmap_data = {
            "content_type": content_type,
            "data": heatmap.tolist(),
            "day_labels": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
            "hour_labels": [f"{h:02d}:00" for h in range(24)],
            "max_engagement": float(heatmap.max()),
            "min_engagement": float(heatmap.min()),
        }

        return heatmap_data

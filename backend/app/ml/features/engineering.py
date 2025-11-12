"""
Main feature engineering orchestration
"""
import pandas as pd
import numpy as np
from typing import List, Dict, Any, Tuple
from sklearn.preprocessing import StandardScaler, OneHotEncoder
import joblib

from .temporal import extract_temporal_features, add_temporal_interactions
from .content import extract_content_features, add_content_interactions
from ..config import CONTENT_TYPES, should_use_advanced_features


class FeatureEngineer:
    """
    Orchestrates feature engineering for Instagram engagement prediction.
    """

    def __init__(self, use_advanced_features: bool = False):
        """
        Initialize feature engineer

        Args:
            use_advanced_features: Whether to include advanced features (requires more data)
        """
        self.use_advanced_features = use_advanced_features
        self.scaler = StandardScaler()
        self.content_encoder = None
        self.time_of_day_encoder = None
        self.feature_names = []
        self.is_fitted = False

    def fit_transform(self, df: pd.DataFrame, target_col: str = "engagement_score") -> Tuple[np.ndarray, np.ndarray]:
        """
        Fit feature engineering pipeline and transform data

        Args:
            df: DataFrame with raw post data
            target_col: Name of target column

        Returns:
            Tuple of (X, y) - features and target arrays
        """
        df = df.copy()

        # Extract target
        y = df[target_col].values

        # Extract all features
        df = self._extract_all_features(df)

        # Add advanced features if enabled
        if self.use_advanced_features:
            df = self._add_advanced_features(df, target_col)

        # Select feature columns
        feature_df = self._select_features(df)

        # One-hot encode categorical features
        feature_df = self._encode_categorical(feature_df, fit=True)

        # Store feature names
        self.feature_names = feature_df.columns.tolist()

        # Scale features
        X = self.scaler.fit_transform(feature_df.values)

        self.is_fitted = True

        return X, y

    def transform(self, df: pd.DataFrame) -> np.ndarray:
        """
        Transform new data using fitted pipeline

        Args:
            df: DataFrame with raw post data

        Returns:
            Transformed feature array
        """
        if not self.is_fitted:
            raise ValueError("FeatureEngineer must be fitted before transform")

        df = df.copy()

        # Extract all features
        df = self._extract_all_features(df)

        # Add advanced features if enabled
        if self.use_advanced_features:
            # For prediction, we don't have historical engagement
            # Use placeholder values that will be updated by predictor
            df = self._add_advanced_features_predict(df)

        # Select feature columns
        feature_df = self._select_features(df)

        # One-hot encode categorical features
        feature_df = self._encode_categorical(feature_df, fit=False)

        # Ensure columns match training
        feature_df = self._align_columns(feature_df)

        # Scale features
        X = self.scaler.transform(feature_df.values)

        return X

    def _extract_all_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Extract all basic features"""
        # Temporal features
        df = extract_temporal_features(df, timestamp_col="posted_at")

        # Content features
        df = extract_content_features(df)

        # Interaction features
        df = add_temporal_interactions(df)
        df = add_content_interactions(df)

        return df

    def _add_advanced_features(self, df: pd.DataFrame, target_col: str) -> pd.DataFrame:
        """
        Add advanced features based on historical data

        Args:
            df: DataFrame with basic features
            target_col: Name of engagement column

        Returns:
            DataFrame with advanced features added
        """
        df = df.copy()

        # Account-level average engagement
        df["account_avg_engagement"] = df[target_col].mean()

        # Content type average engagement
        content_type_avg = df.groupby("content_type")[target_col].transform("mean")
        df["content_type_avg_engagement"] = content_type_avg

        # Hour average engagement
        hour_avg = df.groupby("hour")[target_col].transform("mean")
        df["hour_avg_engagement"] = hour_avg

        # Day of week average engagement
        day_avg = df.groupby("day_of_week")[target_col].transform("mean")
        df["day_avg_engagement"] = day_avg

        # Rolling average (last 10 posts trend)
        df = df.sort_values("posted_at")
        df["recent_trend"] = df[target_col].rolling(window=10, min_periods=1).mean()

        return df

    def _add_advanced_features_predict(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Add advanced features for prediction (using placeholders)

        These will be updated by the predictor with actual historical values
        """
        df = df.copy()

        # Initialize with zeros - will be populated by predictor
        df["account_avg_engagement"] = 0.0
        df["content_type_avg_engagement"] = 0.0
        df["hour_avg_engagement"] = 0.0
        df["day_avg_engagement"] = 0.0
        df["recent_trend"] = 0.0

        return df

    def _select_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Select features for model training/prediction

        Returns:
            DataFrame with only feature columns
        """
        # Core temporal features
        core_features = [
            "hour", "day_of_week", "is_weekend",
            "hour_sin", "hour_cos", "day_sin", "day_cos",
            "time_of_day",
        ]

        # Core content features
        core_features.extend([
            "content_type", "caption_length", "caption_word_count",
            "hashtag_count", "hashtag_density",
            "has_emoji", "emoji_count",
            "mention_count", "has_question", "has_cta",
        ])

        # Interaction features
        core_features.extend([
            "hour_day_interaction",
            "weekend_evening", "weekend_night",
        ])

        # Advanced features
        if self.use_advanced_features:
            core_features.extend([
                "account_avg_engagement",
                "content_type_avg_engagement",
                "hour_avg_engagement",
                "day_avg_engagement",
                "recent_trend",
            ])

        # Select only features that exist in df
        available_features = [f for f in core_features if f in df.columns]

        return df[available_features]

    def _encode_categorical(self, df: pd.DataFrame, fit: bool = False) -> pd.DataFrame:
        """
        One-hot encode categorical features

        Args:
            df: DataFrame with features
            fit: Whether to fit encoders

        Returns:
            DataFrame with encoded features
        """
        df = df.copy()

        # Encode content_type
        if "content_type" in df.columns:
            if fit:
                self.content_encoder = OneHotEncoder(
                    categories=[CONTENT_TYPES],
                    sparse_output=False,
                    handle_unknown="ignore"
                )
                encoded = self.content_encoder.fit_transform(df[["content_type"]])
            else:
                encoded = self.content_encoder.transform(df[["content_type"]])

            # Create column names
            content_cols = [f"content_type_{ct}" for ct in CONTENT_TYPES]
            encoded_df = pd.DataFrame(encoded, columns=content_cols, index=df.index)

            # Drop original and add encoded
            df = df.drop(columns=["content_type"])
            df = pd.concat([df, encoded_df], axis=1)

        # Encode time_of_day
        if "time_of_day" in df.columns:
            time_categories = ["morning", "afternoon", "evening", "night"]

            if fit:
                self.time_of_day_encoder = OneHotEncoder(
                    categories=[time_categories],
                    sparse_output=False,
                    handle_unknown="ignore"
                )
                encoded = self.time_of_day_encoder.fit_transform(df[["time_of_day"]])
            else:
                encoded = self.time_of_day_encoder.transform(df[["time_of_day"]])

            # Create column names
            time_cols = [f"time_of_day_{t}" for t in time_categories]
            encoded_df = pd.DataFrame(encoded, columns=time_cols, index=df.index)

            # Drop original and add encoded
            df = df.drop(columns=["time_of_day"])
            df = pd.concat([df, encoded_df], axis=1)

        return df

    def _align_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Align DataFrame columns with training features

        Args:
            df: DataFrame to align

        Returns:
            DataFrame with matching columns
        """
        # Add missing columns with zeros
        for col in self.feature_names:
            if col not in df.columns:
                df[col] = 0

        # Select only training columns in correct order
        df = df[self.feature_names]

        return df

    def save(self, filepath: str):
        """Save feature engineer to disk"""
        joblib.dump({
            "scaler": self.scaler,
            "content_encoder": self.content_encoder,
            "time_of_day_encoder": self.time_of_day_encoder,
            "feature_names": self.feature_names,
            "use_advanced_features": self.use_advanced_features,
            "is_fitted": self.is_fitted,
        }, filepath)

    @classmethod
    def load(cls, filepath: str) -> "FeatureEngineer":
        """Load feature engineer from disk"""
        data = joblib.load(filepath)

        engineer = cls(use_advanced_features=data["use_advanced_features"])
        engineer.scaler = data["scaler"]
        engineer.content_encoder = data["content_encoder"]
        engineer.time_of_day_encoder = data["time_of_day_encoder"]
        engineer.feature_names = data["feature_names"]
        engineer.is_fitted = data["is_fitted"]

        return engineer

    def get_feature_names(self) -> List[str]:
        """Get list of feature names"""
        return self.feature_names

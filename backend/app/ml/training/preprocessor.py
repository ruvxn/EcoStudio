"""
Data preprocessing for ML training
"""
import pandas as pd
import numpy as np
from typing import Tuple, Dict, Any
from sklearn.model_selection import train_test_split

from ..config import TRAIN_TEST_SPLIT, MIN_POSTS_REQUIRED


class DataPreprocessor:
    """
    Preprocesses data for ML model training
    """

    def __init__(self, test_size: float = 1 - TRAIN_TEST_SPLIT, random_state: int = 42):
        """
        Initialize preprocessor

        Args:
            test_size: Proportion of data to use for testing
            random_state: Random seed for reproducibility
        """
        self.test_size = test_size
        self.random_state = random_state

    def validate_data(self, df: pd.DataFrame) -> Tuple[bool, str]:
        """
        Validate input data meets requirements

        Args:
            df: DataFrame with post data

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check minimum posts
        if len(df) < MIN_POSTS_REQUIRED:
            return False, f"Insufficient data: {len(df)} posts, minimum required: {MIN_POSTS_REQUIRED}"

        # Check required columns
        required_cols = ["posted_at", "engagement_score", "content_type"]
        missing_cols = [col for col in required_cols if col not in df.columns]
        if missing_cols:
            return False, f"Missing required columns: {missing_cols}"

        # Check for null engagement scores
        null_engagement = df["engagement_score"].isna().sum()
        if null_engagement > 0:
            return False, f"{null_engagement} posts have null engagement scores"

        # Check for engagement score variance
        if df["engagement_score"].std() == 0:
            return False, "All posts have identical engagement scores (zero variance)"

        # Check date column is datetime
        if not pd.api.types.is_datetime64_any_dtype(df["posted_at"]):
            try:
                df["posted_at"] = pd.to_datetime(df["posted_at"])
            except Exception as e:
                return False, f"Invalid datetime format in posted_at: {str(e)}"

        return True, ""

    def clean_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Clean and prepare data for training

        Args:
            df: Raw DataFrame

        Returns:
            Cleaned DataFrame
        """
        df = df.copy()

        # Remove duplicates based on post_id
        if "post_id" in df.columns:
            df = df.drop_duplicates(subset=["post_id"], keep="last")

        # Remove rows with null engagement scores
        df = df.dropna(subset=["engagement_score"])

        # Remove outliers (engagement > 3 std devs from mean)
        mean_engagement = df["engagement_score"].mean()
        std_engagement = df["engagement_score"].std()
        if std_engagement > 0:
            df = df[
                (df["engagement_score"] >= mean_engagement - 3 * std_engagement) &
                (df["engagement_score"] <= mean_engagement + 3 * std_engagement)
            ]

        # Ensure content_type is lowercase string
        if "content_type" in df.columns:
            df["content_type"] = df["content_type"].astype(str).str.lower()

        # Fill missing caption with empty string
        if "caption" in df.columns:
            df["caption"] = df["caption"].fillna("")

        # Reset index
        df = df.reset_index(drop=True)

        return df

    def split_data(
        self,
        df: pd.DataFrame,
        target_col: str = "engagement_score",
        stratify: bool = False,
    ) -> Tuple[pd.DataFrame, pd.DataFrame, pd.Series, pd.Series]:
        """
        Split data into train and test sets

        Args:
            df: DataFrame with features
            target_col: Name of target column
            stratify: Whether to stratify split (useful for classification)

        Returns:
            Tuple of (X_train, X_test, y_train, y_test)
        """
        # Separate features and target
        y = df[target_col]
        X = df.drop(columns=[target_col])

        # Stratify by content type if requested and enough samples
        stratify_col = None
        if stratify and "content_type" in X.columns:
            # Only stratify if each class has at least 2 samples
            content_counts = df["content_type"].value_counts()
            if content_counts.min() >= 2:
                stratify_col = df["content_type"]

        # Split
        X_train, X_test, y_train, y_test = train_test_split(
            X,
            y,
            test_size=self.test_size,
            random_state=self.random_state,
            stratify=stratify_col,
        )

        return X_train, X_test, y_train, y_test

    def get_data_summary(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Generate summary statistics for the dataset

        Args:
            df: DataFrame with data

        Returns:
            Dictionary with summary statistics
        """
        summary = {
            "total_posts": len(df),
            "date_range": {
                "start": df["posted_at"].min().isoformat() if "posted_at" in df else None,
                "end": df["posted_at"].max().isoformat() if "posted_at" in df else None,
                "days": (df["posted_at"].max() - df["posted_at"].min()).days if "posted_at" in df else None,
            },
            "engagement_stats": {
                "mean": float(df["engagement_score"].mean()) if "engagement_score" in df else None,
                "median": float(df["engagement_score"].median()) if "engagement_score" in df else None,
                "std": float(df["engagement_score"].std()) if "engagement_score" in df else None,
                "min": float(df["engagement_score"].min()) if "engagement_score" in df else None,
                "max": float(df["engagement_score"].max()) if "engagement_score" in df else None,
            },
        }

        # Content type distribution
        if "content_type" in df.columns:
            summary["content_types"] = df["content_type"].value_counts().to_dict()

        # Temporal distribution
        if "posted_at" in df.columns:
            df["hour"] = pd.to_datetime(df["posted_at"]).dt.hour
            df["day_of_week"] = pd.to_datetime(df["posted_at"]).dt.dayofweek

            summary["temporal_distribution"] = {
                "posts_by_hour": df["hour"].value_counts().sort_index().to_dict(),
                "posts_by_day": df["day_of_week"].value_counts().sort_index().to_dict(),
            }

        return summary

    def prepare_for_training(
        self,
        df: pd.DataFrame,
        target_col: str = "engagement_score",
    ) -> Tuple[pd.DataFrame, pd.DataFrame, pd.Series, pd.Series, Dict[str, Any]]:
        """
        Complete preprocessing pipeline: validate, clean, split

        Args:
            df: Raw DataFrame
            target_col: Name of target column

        Returns:
            Tuple of (X_train, X_test, y_train, y_test, summary)

        Raises:
            ValueError: If data validation fails
        """
        # Validate
        is_valid, error_msg = self.validate_data(df)
        if not is_valid:
            raise ValueError(f"Data validation failed: {error_msg}")

        # Clean
        df_clean = self.clean_data(df)

        # Generate summary
        summary = self.get_data_summary(df_clean)

        # Check if we still have enough data after cleaning
        if len(df_clean) < MIN_POSTS_REQUIRED:
            raise ValueError(
                f"Insufficient data after cleaning: {len(df_clean)} posts, "
                f"minimum required: {MIN_POSTS_REQUIRED}"
            )

        # Split
        X_train, X_test, y_train, y_test = self.split_data(df_clean, target_col)

        # Add split info to summary
        summary["split"] = {
            "train_size": len(X_train),
            "test_size": len(X_test),
            "test_ratio": self.test_size,
        }

        return X_train, X_test, y_train, y_test, summary

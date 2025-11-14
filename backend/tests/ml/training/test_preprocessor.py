"""
Tests for data preprocessor
"""
import pytest
import pandas as pd
import numpy as np
from datetime import datetime

from app.ml.training.preprocessor import DataPreprocessor
from app.ml.config import MIN_POSTS_REQUIRED


class TestDataPreprocessor:
    """Test DataPreprocessor class"""

    def test_initialization(self):
        """Test DataPreprocessor initialization"""
        preprocessor = DataPreprocessor()

        assert preprocessor.test_size > 0
        assert preprocessor.random_state == 42

    def test_validate_data_success(self, sample_dataframe):
        """Test data validation with valid data"""
        preprocessor = DataPreprocessor()
        df = sample_dataframe.copy()

        is_valid, error_msg = preprocessor.validate_data(df)

        assert is_valid is True
        assert error_msg == ""

    def test_validate_data_insufficient_posts(self):
        """Test validation fails with too few posts"""
        preprocessor = DataPreprocessor()
        df = pd.DataFrame({
            "posted_at": [datetime.now()] * 10,
            "engagement_score": [0.05] * 10,
            "content_type": ["image"] * 10,
        })

        is_valid, error_msg = preprocessor.validate_data(df)

        assert is_valid is False
        assert "Insufficient data" in error_msg

    def test_validate_data_missing_columns(self):
        """Test validation fails with missing columns"""
        preprocessor = DataPreprocessor()
        df = pd.DataFrame({
            "posted_at": [datetime.now()] * 50,
            "engagement_score": [0.05] * 50,
            # Missing content_type
        })

        is_valid, error_msg = preprocessor.validate_data(df)

        assert is_valid is False
        assert "Missing required columns" in error_msg

    def test_validate_data_null_engagement(self):
        """Test validation fails with null engagement scores"""
        preprocessor = DataPreprocessor()
        df = pd.DataFrame({
            "posted_at": [datetime.now()] * 50,
            "engagement_score": [0.05] * 45 + [None] * 5,
            "content_type": ["image"] * 50,
        })

        is_valid, error_msg = preprocessor.validate_data(df)

        assert is_valid is False
        assert "null engagement scores" in error_msg

    def test_validate_data_zero_variance(self):
        """Test validation fails with zero variance in engagement"""
        preprocessor = DataPreprocessor()
        df = pd.DataFrame({
            "posted_at": [datetime.now()] * 50,
            "engagement_score": [0.05] * 50,  # All same value
            "content_type": ["image"] * 50,
        })

        is_valid, error_msg = preprocessor.validate_data(df)

        assert is_valid is False
        assert "zero variance" in error_msg

    def test_clean_data(self, sample_dataframe):
        """Test data cleaning"""
        df = sample_dataframe.copy()

        # Add a duplicate
        df = pd.concat([df, df.iloc[[0]]], ignore_index=True)

        preprocessor = DataPreprocessor()
        df_clean = preprocessor.clean_data(df)

        # Should remove duplicates
        assert len(df_clean) < len(df)

    def test_clean_data_removes_outliers(self):
        """Test that extreme outliers are removed"""
        df = pd.DataFrame({
            "post_id": [f"post_{i}" for i in range(50)],
            "posted_at": [datetime.now()] * 50,
            "engagement_score": [0.05] * 48 + [10.0, -5.0],  # Extreme outliers
            "content_type": ["image"] * 50,
        })

        preprocessor = DataPreprocessor()
        df_clean = preprocessor.clean_data(df)

        # Outliers should be removed
        assert len(df_clean) < 50
        assert df_clean["engagement_score"].max() < 10.0

    def test_split_data(self, sample_dataframe):
        """Test train/test split"""
        df = sample_dataframe.copy()

        preprocessor = DataPreprocessor(test_size=0.2)
        X_train, X_test, y_train, y_test = preprocessor.split_data(df)

        # Check splits
        total_size = len(df)
        assert len(X_train) + len(X_test) == total_size
        assert len(y_train) == len(X_train)
        assert len(y_test) == len(X_test)

        # Check test size ratio (approximately 20%)
        assert 0.15 <= len(X_test) / total_size <= 0.25

    def test_get_data_summary(self, sample_dataframe):
        """Test data summary generation"""
        df = sample_dataframe.copy()

        preprocessor = DataPreprocessor()
        summary = preprocessor.get_data_summary(df)

        assert "total_posts" in summary
        assert "date_range" in summary
        assert "engagement_stats" in summary
        assert "content_types" in summary

        assert summary["total_posts"] == len(df)
        assert "mean" in summary["engagement_stats"]

    def test_prepare_for_training_pipeline(self, sample_dataframe):
        """Test complete preprocessing pipeline"""
        df = sample_dataframe.copy()

        preprocessor = DataPreprocessor()
        X_train, X_test, y_train, y_test, summary = preprocessor.prepare_for_training(df)

        # Check that all outputs are valid
        assert len(X_train) > 0
        assert len(X_test) > 0
        assert len(y_train) == len(X_train)
        assert len(y_test) == len(X_test)
        assert "total_posts" in summary
        assert "split" in summary

    def test_prepare_for_training_with_invalid_data(self):
        """Test that prepare_for_training raises error with invalid data"""
        df = pd.DataFrame({
            "posted_at": [datetime.now()] * 10,  # Too few
            "engagement_score": [0.05] * 10,
            "content_type": ["image"] * 10,
        })

        preprocessor = DataPreprocessor()

        with pytest.raises(ValueError):
            preprocessor.prepare_for_training(df)

    def test_handles_different_content_type_formats(self):
        """Test that content_type is normalized"""
        df = pd.DataFrame({
            "posted_at": [datetime.now()] * 50,
            "engagement_score": np.random.uniform(0.01, 0.05, 50),
            "content_type": ["Photo", "VIDEO", "carousel"] * 16 + ["image"] * 2,
        })

        preprocessor = DataPreprocessor()
        df_clean = preprocessor.clean_data(df)

        # All should be lowercase
        assert all(df_clean["content_type"].str.islower())

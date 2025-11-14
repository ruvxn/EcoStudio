"""
Tests for feature engineering orchestration
"""
import pytest
import pandas as pd
import numpy as np

from app.ml.features.engineering import FeatureEngineer


class TestFeatureEngineer:
    """Test FeatureEngineer class"""

    def test_initialization(self):
        """Test FeatureEngineer initialization"""
        engineer = FeatureEngineer(use_advanced_features=False)

        assert engineer.use_advanced_features is False
        assert engineer.is_fitted is False
        assert engineer.scaler is not None

    def test_fit_transform(self, sample_dataframe):
        """Test fit_transform method"""
        df = sample_dataframe.copy()
        engineer = FeatureEngineer(use_advanced_features=False)

        X, y = engineer.fit_transform(df)

        # Check shapes
        assert X.shape[0] == len(df)
        assert len(y) == len(df)

        # Check that engineer is fitted
        assert engineer.is_fitted is True
        assert len(engineer.get_feature_names()) > 0

    def test_transform_after_fit(self, sample_dataframe):
        """Test transform method after fitting"""
        df = sample_dataframe.copy()
        engineer = FeatureEngineer(use_advanced_features=False)

        # Fit
        X_train, y_train = engineer.fit_transform(df)

        # Transform new data
        df_new = sample_dataframe.head(10).copy()
        X_new = engineer.transform(df_new)

        # Check that feature dimensions match
        assert X_new.shape[1] == X_train.shape[1]

    def test_transform_before_fit_raises_error(self, sample_dataframe):
        """Test that transform raises error if not fitted"""
        df = sample_dataframe.copy()
        engineer = FeatureEngineer(use_advanced_features=False)

        with pytest.raises(ValueError, match="must be fitted"):
            engineer.transform(df)

    def test_advanced_features(self, sample_dataframe):
        """Test with advanced features enabled"""
        df = sample_dataframe.copy()
        engineer = FeatureEngineer(use_advanced_features=True)

        X, y = engineer.fit_transform(df)

        feature_names = engineer.get_feature_names()

        # Check that advanced features are included
        assert any("avg_engagement" in f for f in feature_names)

    def test_feature_names(self, sample_dataframe):
        """Test that feature names are correctly stored"""
        df = sample_dataframe.copy()
        engineer = FeatureEngineer(use_advanced_features=False)

        engineer.fit_transform(df)
        feature_names = engineer.get_feature_names()

        # Should have temporal features
        assert any("hour" in f for f in feature_names)
        assert any("day_of_week" in f for f in feature_names)

        # Should have content type features (one-hot encoded)
        assert any("content_type" in f for f in feature_names)

    def test_save_and_load(self, sample_dataframe, tmp_path):
        """Test saving and loading FeatureEngineer"""
        df = sample_dataframe.copy()
        engineer = FeatureEngineer(use_advanced_features=False)

        # Fit
        X, y = engineer.fit_transform(df)

        # Save
        save_path = tmp_path / "engineer.joblib"
        engineer.save(str(save_path))

        # Load
        engineer_loaded = FeatureEngineer.load(str(save_path))

        # Check that loaded engineer works
        assert engineer_loaded.is_fitted is True
        assert engineer_loaded.get_feature_names() == engineer.get_feature_names()

        # Transform with loaded engineer
        X_loaded = engineer_loaded.transform(df.head(5))
        assert X_loaded.shape[1] == X.shape[1]

    def test_handles_missing_caption(self):
        """Test that missing captions are handled"""
        df = pd.DataFrame({
            "posted_at": [pd.Timestamp("2025-01-01")],
            "content_type": ["image"],
            "caption": [None],
            "engagement_score": [0.05],
        })

        engineer = FeatureEngineer(use_advanced_features=False)
        X, y = engineer.fit_transform(df)

        # Should not raise an error
        assert X.shape[0] == 1

    def test_cyclical_features_present(self, sample_dataframe):
        """Test that cyclical encodings are present"""
        df = sample_dataframe.copy()
        engineer = FeatureEngineer(use_advanced_features=False)

        engineer.fit_transform(df)
        feature_names = engineer.get_feature_names()

        # Check for sin/cos encodings
        assert any("sin" in f for f in feature_names)
        assert any("cos" in f for f in feature_names)

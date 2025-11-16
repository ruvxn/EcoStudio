"""
Model training orchestration with XGBoost
"""
import numpy as np
import pandas as pd
from typing import Dict, Any, Tuple
from datetime import datetime
import joblib
from pathlib import Path

from xgboost import XGBRegressor
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import cross_val_score
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

from .data_loader import DataLoader
from .preprocessor import DataPreprocessor
from ..features.engineering import FeatureEngineer
from ..config import (
    get_model_config,
    get_model_path,
    should_use_advanced_features,
    CV_FOLDS,
    CV_SCORING,
    RANDOM_FOREST_CONFIG,
    TARGET_R2_SCORE,
    MIN_R2_SCORE,
    MODEL_VERSION,
)


class ModelTrainer:
    """
    Orchestrates model training pipeline
    """

    def __init__(self, db_session):
        """
        Initialize trainer

        Args:
            db_session: Database session for data loading
        """
        self.db = db_session
        self.data_loader = DataLoader(db_session)
        self.preprocessor = DataPreprocessor()
        self.feature_engineer = None
        self.model = None
        self.metrics = {}

    def train(
        self,
        account_id: int,
        max_age_days: int = None,
        use_random_forest: bool = False,
    ) -> Dict[str, Any]:
        """
        Train model for an account

        Args:
            account_id: Social account ID
            max_age_days: Only use posts from last N days (optional)
            use_random_forest: Force use of Random Forest instead of XGBoost

        Returns:
            Dictionary with training results and metrics

        Raises:
            ValueError: If training fails
        """
        print(f"Starting training for account {account_id}...")

        # Step 1: Load data
        print("Loading post data...")
        df = self.data_loader.load_posts_for_account(
            account_id=account_id,
            max_age_days=max_age_days,
        )
        print(f"Loaded {len(df)} posts")

        # Step 2: Preprocess
        print("Preprocessing data...")
        X_train, X_test, y_train, y_test, data_summary = self.preprocessor.prepare_for_training(df)
        print(f"Train size: {len(X_train)}, Test size: {len(X_test)}")

        # Step 3: Feature engineering
        print("Engineering features...")
        n_posts = len(df)
        use_advanced = should_use_advanced_features(n_posts)
        self.feature_engineer = FeatureEngineer(use_advanced_features=use_advanced)

        X_train_features, y_train_array = self.feature_engineer.fit_transform(
            pd.concat([X_train, y_train], axis=1)
        )
        X_test_features = self.feature_engineer.transform(X_test)
        y_test_array = y_test.values

        print(f"Features: {len(self.feature_engineer.get_feature_names())}")
        print(f"Using advanced features: {use_advanced}")

        # Step 4: Select and configure model
        if use_random_forest or n_posts <= 50:
            print("Using Random Forest model...")
            self.model = RandomForestRegressor(**RANDOM_FOREST_CONFIG)
            model_type = "random_forest"
        else:
            print("Using XGBoost model...")
            model_config = get_model_config(n_posts)
            self.model = XGBRegressor(**model_config)
            model_type = "xgboost"

        # Step 5: Cross-validation
        print(f"Performing {CV_FOLDS}-fold cross-validation...")

        def _run_cv(estimator):
            return cross_val_score(
                estimator,
                X_train_features,
                y_train_array,
                cv=CV_FOLDS,
                scoring=CV_SCORING,
                n_jobs=-1,
            )

        try:
            cv_scores = _run_cv(self.model)
        except AttributeError as exc:
            if "__sklearn_tags__" in str(exc):
                print("Estimator is missing sklearn tag support. Falling back to Random Forest.")
                self.model = RandomForestRegressor(**RANDOM_FOREST_CONFIG)
                model_type = "random_forest"
                cv_scores = _run_cv(self.model)
            else:
                raise
        cv_mae = -cv_scores.mean()  # Negative because sklearn uses negative MAE
        cv_std = cv_scores.std()

        print(f"CV MAE: {cv_mae:.4f} (+/- {cv_std:.4f})")

        # Step 6: Train final model
        print("Training final model on full training set...")
        self.model.fit(X_train_features, y_train_array)

        # Step 7: Evaluate on test set
        print("Evaluating on test set...")
        y_pred = self.model.predict(X_test_features)

        mae = mean_absolute_error(y_test_array, y_pred)
        mse = mean_squared_error(y_test_array, y_pred)
        rmse = np.sqrt(mse)
        r2 = r2_score(y_test_array, y_pred)

        print(f"Test R²: {r2:.4f}")
        print(f"Test MAE: {mae:.4f}")
        print(f"Test RMSE: {rmse:.4f}")

        # Step 8: Get feature importance
        feature_importance = self._get_feature_importance()

        # Store metrics
        self.metrics = {
            "model_type": model_type,
            "n_posts": n_posts,
            "n_features": len(self.feature_engineer.get_feature_names()),
            "use_advanced_features": use_advanced,
            "cv_mae": float(cv_mae),
            "cv_std": float(cv_std),
            "test_mae": float(mae),
            "test_mse": float(mse),
            "test_rmse": float(rmse),
            "test_r2": float(r2),
            "feature_importance": feature_importance,
            "data_summary": data_summary,
            "trained_at": datetime.utcnow().isoformat(),
            "model_version": MODEL_VERSION,
        }

        # Step 9: Assess performance
        performance_assessment = self._assess_performance(r2)
        self.metrics["performance_assessment"] = performance_assessment

        print(f"\nTraining complete!")
        print(f"Performance: {performance_assessment}")

        return self.metrics

    def save_model(self, account_id: int) -> Path:
        """
        Save trained model and feature engineer to disk

        Args:
            account_id: Social account ID

        Returns:
            Path to saved model file

        Raises:
            ValueError: If model not trained
        """
        if self.model is None or self.feature_engineer is None:
            raise ValueError("Model must be trained before saving")

        # Create timestamp version
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        model_path = get_model_path(account_id, timestamp)

        # Ensure models directory exists
        model_path.parent.mkdir(parents=True, exist_ok=True)

        # Save model bundle
        model_bundle = {
            "model": self.model,
            "feature_engineer": self.feature_engineer,
            "metrics": self.metrics,
            "account_id": account_id,
            "saved_at": datetime.utcnow().isoformat(),
        }

        joblib.dump(model_bundle, model_path)
        print(f"Model saved to: {model_path}")

        # Also save as "latest" for easy loading
        latest_path = get_model_path(account_id, "latest")
        joblib.dump(model_bundle, latest_path)
        print(f"Model saved as latest: {latest_path}")

        return model_path

    @classmethod
    def load_model(cls, account_id: int, version: str = "latest") -> Tuple[Any, FeatureEngineer, Dict[str, Any]]:
        """
        Load trained model from disk

        Args:
            account_id: Social account ID
            version: Model version to load (default: "latest")

        Returns:
            Tuple of (model, feature_engineer, metrics)

        Raises:
            FileNotFoundError: If model file doesn't exist
        """
        model_path = get_model_path(account_id, version)

        if not model_path.exists():
            raise FileNotFoundError(
                f"No trained model found for account {account_id} "
                f"(version: {version}). Please train a model first."
            )

        print(f"Loading model from: {model_path}")
        model_bundle = joblib.load(model_path)

        return (
            model_bundle["model"],
            model_bundle["feature_engineer"],
            model_bundle.get("metrics", {}),
        )

    def _get_feature_importance(self) -> Dict[str, float]:
        """
        Get feature importance from trained model

        Returns:
            Dictionary mapping feature names to importance scores
        """
        if self.model is None:
            return {}

        # Get feature importance array
        if hasattr(self.model, "feature_importances_"):
            importances = self.model.feature_importances_
        else:
            return {}

        # Get feature names
        feature_names = self.feature_engineer.get_feature_names()

        # Create dictionary sorted by importance
        importance_dict = dict(zip(feature_names, importances))
        importance_dict = {
            k: float(v)
            for k, v in sorted(importance_dict.items(), key=lambda x: x[1], reverse=True)
        }

        # Return top 15 features
        top_features = dict(list(importance_dict.items())[:15])

        return top_features

    def _assess_performance(self, r2: float) -> str:
        """
        Assess model performance based on R² score

        Args:
            r2: R² score

        Returns:
            Performance assessment string
        """
        if r2 >= TARGET_R2_SCORE:
            return "excellent"
        elif r2 >= MIN_R2_SCORE:
            return "acceptable"
        elif r2 >= 0.1:
            return "poor"
        else:
            return "very_poor"

    def get_training_recommendations(self, account_id: int) -> Dict[str, Any]:
        """
        Get recommendations for improving model training

        Args:
            account_id: Social account ID

        Returns:
            Dictionary with recommendations
        """
        stats = self.data_loader.get_account_stats(account_id)
        recommendations = []

        # Check post count
        post_count = stats.get("post_count", 0)
        if post_count < 50:
            recommendations.append(
                "Collect more posts (current: {}, recommended: 100+)".format(post_count)
            )
        elif post_count < 100:
            recommendations.append(
                "Good data size, but 100+ posts would improve model"
            )

        # Check date range
        date_range = stats.get("date_range", {})
        if date_range.get("start") and date_range.get("end"):
            start = pd.to_datetime(date_range["start"])
            end = pd.to_datetime(date_range["end"])
            days = (end - start).days

            if days < 30:
                recommendations.append(
                    f"Short date range ({days} days). Collect posts over longer period."
                )

        # Check content diversity
        content_dist = stats.get("content_type_distribution", {})
        if len(content_dist) == 1:
            recommendations.append(
                "All posts are same content type. Try posting different content types."
            )

        return {
            "account_stats": stats,
            "recommendations": recommendations,
            "ready_for_training": stats.get("has_sufficient_data", False),
        }

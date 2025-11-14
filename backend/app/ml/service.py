"""
ML Service - Main entry point for ML operations

This service orchestrates training and prediction workflows.
"""
from typing import Dict, Any, List, Optional
from datetime import datetime
from sqlalchemy.orm import Session

from .training.trainer import ModelTrainer
from .prediction.predictor import Predictor
from .training.data_loader import DataLoader
from .config import DEFAULT_PREDICTION_DAYS, TOP_PREDICTIONS_TO_STORE


class MLService:
    """
    Main service for ML operations

    Provides high-level API for:
    - Training models
    - Generating predictions
    - Getting model info
    """

    def __init__(self, db: Session):
        """
        Initialize ML service

        Args:
            db: Database session
        """
        self.db = db
        self.data_loader = DataLoader(db)

    def train_model(
        self,
        account_id: int,
        max_age_days: Optional[int] = None,
        use_random_forest: bool = False,
    ) -> Dict[str, Any]:
        """
        Train a new model for an account

        Args:
            account_id: Social account ID
            max_age_days: Only use posts from last N days (optional)
            use_random_forest: Force use of Random Forest instead of XGBoost

        Returns:
            Dictionary with training results and metrics

        Raises:
            ValueError: If insufficient data or training fails
        """
        # Initialize trainer
        trainer = ModelTrainer(self.db)

        # Train model
        metrics = trainer.train(
            account_id=account_id,
            max_age_days=max_age_days,
            use_random_forest=use_random_forest,
        )

        # Save model
        model_path = trainer.save_model(account_id)

        # Add save info to metrics
        metrics["model_path"] = str(model_path)
        metrics["account_id"] = account_id

        return metrics

    def get_predictions(
        self,
        account_id: int,
        days_ahead: int = DEFAULT_PREDICTION_DAYS,
        content_types: Optional[List[str]] = None,
        top_n: int = TOP_PREDICTIONS_TO_STORE,
    ) -> Dict[str, Any]:
        """
        Get optimal posting time predictions for an account

        Args:
            account_id: Social account ID
            days_ahead: Number of days to predict (default: 7)
            content_types: List of content types to predict for (default: all)
            top_n: Number of top predictions to return (default: 30)

        Returns:
            Dictionary with predictions and metadata

        Raises:
            FileNotFoundError: If no trained model exists
        """
        # Load trained model
        model, feature_engineer, metrics = ModelTrainer.load_model(account_id)

        # Initialize predictor
        predictor = Predictor(
            model=model,
            feature_engineer=feature_engineer,
            db_session=self.db,
        )

        # Generate predictions
        predictions = predictor.predict_schedule(
            account_id=account_id,
            days_ahead=days_ahead,
            content_types=content_types,
            top_n=top_n,
        )

        # Return predictions with metadata
        return {
            "account_id": account_id,
            "generated_at": datetime.utcnow().isoformat(),
            "days_ahead": days_ahead,
            "predictions_count": len(predictions),
            "predictions": predictions,
            "model_info": {
                "trained_at": metrics.get("trained_at"),
                "model_type": metrics.get("model_type"),
                "test_r2": metrics.get("test_r2"),
                "performance": metrics.get("performance_assessment"),
            }
        }

    def get_best_time_summary(
        self,
        account_id: int,
        days_ahead: int = 7,
    ) -> Dict[str, Any]:
        """
        Get a summary of the best posting times

        Simplified version that returns just the top 3 best times overall.

        Args:
            account_id: Social account ID
            days_ahead: Number of days to look ahead (default: 7)

        Returns:
            Dictionary with top 3 best times and summary info
        """
        # Get predictions
        result = self.get_predictions(
            account_id=account_id,
            days_ahead=days_ahead,
            top_n=3,  # Just top 3 for summary
        )

        predictions = result["predictions"]

        # Calculate summary statistics
        day_map = {
            0: "Monday",
            1: "Tuesday",
            2: "Wednesday",
            3: "Thursday",
            4: "Friday",
            5: "Saturday",
            6: "Sunday",
        }

        # Format best times for easy display
        best_times = []
        for pred in predictions[:3]:
            best_times.append({
                "day": day_map[pred["day_of_week"]],
                "hour": f"{pred['hour']:02d}:00",
                "time_of_day": pred["time_of_day"],
                "content_type": pred["content_type"],
                "predicted_engagement": round(pred["predicted_engagement"], 4),
                "is_weekend": pred["is_weekend"],
            })

        return {
            "account_id": account_id,
            "generated_at": result["generated_at"],
            "best_times": best_times,
            "model_performance": result["model_info"]["performance"],
            "model_trained_at": result["model_info"]["trained_at"],
        }

    def get_predictions_by_content_type(
        self,
        account_id: int,
        days_ahead: int = 7,
        top_n_per_type: int = 5,
    ) -> Dict[str, Any]:
        """
        Get best posting times grouped by content type

        Args:
            account_id: Social account ID
            days_ahead: Number of days to predict
            top_n_per_type: Number of top times per content type

        Returns:
            Dictionary with predictions grouped by content type
        """
        # Load model
        model, feature_engineer, metrics = ModelTrainer.load_model(account_id)

        # Initialize predictor
        predictor = Predictor(
            model=model,
            feature_engineer=feature_engineer,
            db_session=self.db,
        )

        # Get predictions by content type
        by_content = predictor.get_best_times_by_content(
            account_id=account_id,
            days_ahead=days_ahead,
            top_n=top_n_per_type,
        )

        return {
            "account_id": account_id,
            "generated_at": datetime.utcnow().isoformat(),
            "predictions_by_content_type": by_content,
            "model_info": {
                "trained_at": metrics.get("trained_at"),
                "test_r2": metrics.get("test_r2"),
            }
        }

    def get_weekly_heatmap(
        self,
        account_id: int,
        content_type: str = "image",
    ) -> Dict[str, Any]:
        """
        Get weekly heatmap of predicted engagement

        Args:
            account_id: Social account ID
            content_type: Content type to analyze

        Returns:
            Dictionary with heatmap data
        """
        # Load model
        model, feature_engineer, _ = ModelTrainer.load_model(account_id)

        # Initialize predictor
        predictor = Predictor(
            model=model,
            feature_engineer=feature_engineer,
            db_session=self.db,
        )

        # Generate heatmap
        heatmap_data = predictor.get_weekly_heatmap(
            account_id=account_id,
            content_type=content_type,
        )

        return {
            "account_id": account_id,
            "generated_at": datetime.utcnow().isoformat(),
            "heatmap": heatmap_data,
        }

    def get_training_readiness(self, account_id: int) -> Dict[str, Any]:
        """
        Check if account has sufficient data for training

        Args:
            account_id: Social account ID

        Returns:
            Dictionary with readiness status and recommendations
        """
        trainer = ModelTrainer(self.db)
        return trainer.get_training_recommendations(account_id)

    def get_model_info(self, account_id: int) -> Optional[Dict[str, Any]]:
        """
        Get information about trained model

        Args:
            account_id: Social account ID

        Returns:
            Dictionary with model info or None if no model exists
        """
        try:
            _, _, metrics = ModelTrainer.load_model(account_id)
            return metrics
        except FileNotFoundError:
            return None

    def compare_posting_times(
        self,
        account_id: int,
        times: List[datetime],
        content_type: str,
    ) -> List[Dict[str, Any]]:
        """
        Compare predicted engagement for specific times

        Args:
            account_id: Social account ID
            times: List of datetime objects to compare
            content_type: Content type

        Returns:
            List of predictions sorted by engagement
        """
        # Load model
        model, feature_engineer, _ = ModelTrainer.load_model(account_id)

        # Initialize predictor
        predictor = Predictor(
            model=model,
            feature_engineer=feature_engineer,
            db_session=self.db,
        )

        # Compare times
        return predictor.compare_times(
            times=times,
            content_type=content_type,
            account_id=account_id,
        )

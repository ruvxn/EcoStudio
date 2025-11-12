"""
ML Service for Instagram engagement prediction
"""
from typing import Dict, Any, List, Optional
from datetime import datetime, date, timedelta
from sqlalchemy.orm import Session

from app.api.models.predictions import Prediction
from app.api.models.posts import ContentType
from app.api.models.social_accounts import SocialAccount
from app.ml.training.trainer import ModelTrainer
from app.ml.prediction.predictor import Predictor
from app.ml.prediction.confidence import ConfidenceScorer
from app.ml.config import DEFAULT_PREDICTION_DAYS, MODEL_VERSION


class MLService:
    """
    Service layer for ML operations
    """

    def __init__(self, db: Session):
        """
        Initialize ML service

        Args:
            db: Database session
        """
        self.db = db

    def train_model(
        self,
        account_id: int,
        force_retrain: bool = False,
        max_age_days: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Train or retrain model for an account

        Args:
            account_id: Social account ID
            force_retrain: Whether to force retraining even if model exists
            max_age_days: Only use posts from last N days (optional)

        Returns:
            Dictionary with training results

        Raises:
            ValueError: If account not found or training fails
        """
        # Verify account exists
        account = self.db.query(SocialAccount).filter(
            SocialAccount.id == account_id
        ).first()

        if not account:
            raise ValueError(f"Social account {account_id} not found")

        # Check if model already exists
        if not force_retrain:
            try:
                model_path = ModelTrainer.load_model(account_id)
                return {
                    "status": "already_trained",
                    "message": "Model already exists. Use force_retrain=True to retrain.",
                    "account_id": account_id,
                }
            except FileNotFoundError:
                pass  # Model doesn't exist, proceed with training

        # Initialize trainer
        trainer = ModelTrainer(self.db)

        # Train model
        print(f"Training model for account {account_id}...")
        metrics = trainer.train(
            account_id=account_id,
            max_age_days=max_age_days,
        )

        # Save model
        model_path = trainer.save_model(account_id)

        # Generate and store predictions
        print("Generating predictions...")
        predictions = self.generate_predictions(
            account_id=account_id,
            days_ahead=DEFAULT_PREDICTION_DAYS,
            store_in_db=True,
        )

        return {
            "status": "success",
            "message": "Model trained successfully",
            "account_id": account_id,
            "model_path": str(model_path),
            "metrics": metrics,
            "predictions_generated": len(predictions),
        }

    def generate_predictions(
        self,
        account_id: int,
        days_ahead: int = DEFAULT_PREDICTION_DAYS,
        content_types: Optional[List[str]] = None,
        min_confidence: Optional[float] = None,
        store_in_db: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        Generate optimal posting schedule predictions

        Args:
            account_id: Social account ID
            days_ahead: Number of days to predict
            content_types: List of content types (optional)
            min_confidence: Minimum confidence threshold (optional)
            store_in_db: Whether to store predictions in database

        Returns:
            List of prediction dictionaries

        Raises:
            FileNotFoundError: If model not trained
        """
        # Load trained model
        model, feature_engineer, metrics = ModelTrainer.load_model(account_id)

        # Create predictor
        predictor = Predictor(model, feature_engineer, self.db)

        # Generate predictions
        predictions = predictor.predict_schedule(
            account_id=account_id,
            days_ahead=days_ahead,
            content_types=content_types,
        )

        # Calculate confidence scores
        confidence_scorer = ConfidenceScorer(model, feature_engineer, metrics)

        # Transform features for confidence calculation
        from app.ml.features.temporal import extract_temporal_features
        from app.ml.features.content import extract_content_features
        import pandas as pd

        # Prepare data for confidence calculation
        pred_df = pd.DataFrame(predictions)
        pred_df = extract_temporal_features(pred_df)
        pred_df = extract_content_features(pred_df)

        # Add default caption features
        pred_df["caption"] = ""

        # Transform to features
        X = feature_engineer.transform(pred_df)

        # Add confidence to predictions
        predictions = confidence_scorer.add_confidence_to_predictions(predictions, X)

        # Filter by confidence if specified
        if min_confidence:
            predictions = confidence_scorer.filter_by_confidence(
                predictions, min_confidence
            )

        # Store in database if requested
        if store_in_db:
            self._store_predictions(account_id, predictions)

        return predictions

    def get_predictions(
        self,
        account_id: int,
        days_ahead: Optional[int] = None,
        content_type: Optional[str] = None,
        min_confidence: Optional[float] = None,
        limit: int = 30,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve stored predictions from database

        Args:
            account_id: Social account ID
            days_ahead: Filter to predictions within N days
            content_type: Filter by content type
            min_confidence: Minimum confidence threshold
            limit: Maximum number of predictions to return

        Returns:
            List of prediction dictionaries
        """
        query = self.db.query(Prediction).filter(
            Prediction.account_id == account_id
        )

        # Filter by date range
        if days_ahead:
            end_date = date.today() + timedelta(days=days_ahead)
            query = query.filter(Prediction.prediction_date <= end_date)

        # Filter by content type
        if content_type:
            try:
                content_enum = ContentType(content_type)
                query = query.filter(Prediction.content_type == content_enum)
            except ValueError:
                pass  # Invalid content type, skip filter

        # Filter by confidence
        if min_confidence:
            query = query.filter(Prediction.confidence_score >= min_confidence)

        # Order by engagement and limit
        query = query.order_by(Prediction.predicted_engagement.desc()).limit(limit)

        # Execute query
        predictions = query.all()

        # Convert to dictionaries
        return [self._prediction_to_dict(p) for p in predictions]

    def get_model_performance(self, account_id: int) -> Dict[str, Any]:
        """
        Get model performance metrics

        Args:
            account_id: Social account ID

        Returns:
            Dictionary with performance metrics

        Raises:
            FileNotFoundError: If model not trained
        """
        # Load model
        model, feature_engineer, metrics = ModelTrainer.load_model(account_id)

        # Create confidence scorer for summary
        confidence_scorer = ConfidenceScorer(model, feature_engineer, metrics)
        confidence_summary = confidence_scorer.get_confidence_summary()

        return {
            "account_id": account_id,
            "metrics": metrics,
            "confidence": confidence_summary,
            "model_exists": True,
        }

    def get_training_recommendations(self, account_id: int) -> Dict[str, Any]:
        """
        Get recommendations for training a model

        Args:
            account_id: Social account ID

        Returns:
            Dictionary with recommendations
        """
        trainer = ModelTrainer(self.db)
        return trainer.get_training_recommendations(account_id)

    def delete_predictions(self, account_id: int) -> int:
        """
        Delete all predictions for an account

        Args:
            account_id: Social account ID

        Returns:
            Number of predictions deleted
        """
        count = self.db.query(Prediction).filter(
            Prediction.account_id == account_id
        ).delete()

        self.db.commit()

        return count

    def _store_predictions(
        self,
        account_id: int,
        predictions: List[Dict[str, Any]],
    ):
        """
        Store predictions in database

        Args:
            account_id: Social account ID
            predictions: List of prediction dictionaries
        """
        # Delete old predictions for this account
        self.delete_predictions(account_id)

        # Create new prediction records
        for pred in predictions:
            # Parse timestamp
            posted_at = pred["posted_at"]
            if isinstance(posted_at, str):
                posted_at = datetime.fromisoformat(posted_at.replace('Z', '+00:00'))

            # Get content type enum
            content_type_str = pred["content_type"]
            try:
                content_enum = ContentType(content_type_str)
            except ValueError:
                # Try mapping common variations
                type_mapping = {
                    "photo": ContentType.IMAGE,
                    "image": ContentType.IMAGE,
                    "video": ContentType.VIDEO,
                    "carousel": ContentType.CAROUSEL,
                    "reel": ContentType.REEL,
                    "story": ContentType.STORY,
                }
                content_enum = type_mapping.get(content_type_str.lower(), ContentType.IMAGE)

            # Create prediction record
            prediction = Prediction(
                account_id=account_id,
                prediction_date=posted_at.date(),
                day_of_week=pred["day_of_week"],
                hour=pred["hour"],
                content_type=content_enum,
                predicted_engagement=pred["predicted_engagement"],
                confidence_score=pred.get("confidence_score", 0.5),
                model_version=MODEL_VERSION,
            )

            self.db.add(prediction)

        # Commit changes
        self.db.commit()

        print(f"Stored {len(predictions)} predictions for account {account_id}")

    def _prediction_to_dict(self, prediction: Prediction) -> Dict[str, Any]:
        """
        Convert Prediction model to dictionary

        Args:
            prediction: Prediction model instance

        Returns:
            Dictionary representation
        """
        return {
            "id": prediction.id,
            "account_id": prediction.account_id,
            "prediction_date": prediction.prediction_date.isoformat(),
            "day_of_week": prediction.day_of_week,
            "day_name": prediction.day_name,
            "hour": prediction.hour,
            "content_type": prediction.content_type.value,
            "predicted_engagement": prediction.predicted_engagement,
            "confidence_score": prediction.confidence_score,
            "confidence_level": prediction.confidence_level,
            "model_version": prediction.model_version,
            "created_at": prediction.created_at.isoformat(),
        }

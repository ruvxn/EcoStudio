"""
Integration tests for complete ML pipeline
"""
import pytest
from pathlib import Path

from app.ml.training.trainer import ModelTrainer
from app.ml.training.data_loader import DataLoader
from app.ml.prediction.predictor import Predictor
from app.ml.prediction.confidence import ConfidenceScorer
from app.services.ml_service import MLService


class TestMLPipelineIntegration:
    """Test end-to-end ML pipeline"""

    def test_complete_training_pipeline(self, test_db, sample_posts_medium, tmp_path):
        """Test complete training pipeline from data to model"""
        account_id = sample_posts_medium[0].account_id

        # Temporarily set model path to tmp directory
        import app.ml.config as config
        original_dir = config.MODELS_DIR
        config.MODELS_DIR = tmp_path

        try:
            # Initialize trainer
            trainer = ModelTrainer(test_db)

            # Train model
            metrics = trainer.train(account_id)

            # Verify metrics
            assert "model_type" in metrics
            assert "n_posts" in metrics
            assert "test_r2" in metrics
            assert metrics["n_posts"] >= 30

            # Verify model can be saved
            model_path = trainer.save_model(account_id)
            assert Path(model_path).exists()

        finally:
            config.MODELS_DIR = original_dir

    def test_complete_prediction_pipeline(self, test_db, sample_posts_large, tmp_path):
        """Test complete pipeline from training to prediction"""
        account_id = sample_posts_large[0].account_id

        import app.ml.config as config
        original_dir = config.MODELS_DIR
        config.MODELS_DIR = tmp_path

        try:
            # Train model
            trainer = ModelTrainer(test_db)
            metrics = trainer.train(account_id)
            model_path = trainer.save_model(account_id)

            # Load model
            model, feature_engineer, loaded_metrics = ModelTrainer.load_model(account_id)

            assert model is not None
            assert feature_engineer is not None
            assert loaded_metrics["n_posts"] == metrics["n_posts"]

            # Generate predictions
            predictor = Predictor(model, feature_engineer, test_db)
            predictions = predictor.predict_schedule(
                account_id=account_id,
                days_ahead=7,
                top_n=20
            )

            # Verify predictions
            assert len(predictions) > 0
            assert len(predictions) <= 20

            # Check prediction structure
            pred = predictions[0]
            assert "posted_at" in pred
            assert "hour" in pred
            assert "day_of_week" in pred
            assert "content_type" in pred
            assert "predicted_engagement" in pred

        finally:
            config.MODELS_DIR = original_dir

    def test_confidence_scoring_integration(self, test_db, sample_posts_medium, tmp_path):
        """Test confidence scoring in the pipeline"""
        account_id = sample_posts_medium[0].account_id

        import app.ml.config as config
        original_dir = config.MODELS_DIR
        config.MODELS_DIR = tmp_path

        try:
            # Train
            trainer = ModelTrainer(test_db)
            metrics = trainer.train(account_id)
            trainer.save_model(account_id)

            # Load and predict
            model, feature_engineer, loaded_metrics = ModelTrainer.load_model(account_id)
            predictor = Predictor(model, feature_engineer, test_db)

            predictions = predictor.predict_schedule(
                account_id=account_id,
                days_ahead=3,
                top_n=10
            )

            # Add confidence scores
            confidence_scorer = ConfidenceScorer(model, feature_engineer, metrics)

            # Verify confidence summary
            confidence_summary = confidence_scorer.get_confidence_summary()

            assert "base_confidence" in confidence_summary
            assert "confidence_level" in confidence_summary
            assert "model_r2" in confidence_summary

        finally:
            config.MODELS_DIR = original_dir

    def test_ml_service_integration(self, test_db, sample_posts_large, tmp_path):
        """Test MLService end-to-end"""
        account_id = sample_posts_large[0].account_id

        import app.ml.config as config
        original_dir = config.MODELS_DIR
        config.MODELS_DIR = tmp_path

        try:
            ml_service = MLService(test_db)

            # Train model
            result = ml_service.train_model(account_id, force_retrain=True)

            assert result["status"] == "success"
            assert "metrics" in result
            assert result["predictions_generated"] > 0

            # Generate predictions
            predictions = ml_service.generate_predictions(
                account_id=account_id,
                days_ahead=7,
                min_confidence=0.0
            )

            assert len(predictions) > 0

            # Get model performance
            performance = ml_service.get_model_performance(account_id)

            assert "metrics" in performance
            assert "confidence" in performance
            assert performance["model_exists"] is True

        finally:
            config.MODELS_DIR = original_dir

    def test_retrain_model(self, test_db, sample_posts_medium, tmp_path):
        """Test model retraining"""
        account_id = sample_posts_medium[0].account_id

        import app.ml.config as config
        original_dir = config.MODELS_DIR
        config.MODELS_DIR = tmp_path

        try:
            ml_service = MLService(test_db)

            # Train first time
            result1 = ml_service.train_model(account_id)
            assert result1["status"] == "success"

            # Try training again without force_retrain
            result2 = ml_service.train_model(account_id, force_retrain=False)
            assert result2["status"] == "already_trained"

            # Force retrain
            result3 = ml_service.train_model(account_id, force_retrain=True)
            assert result3["status"] == "success"

        finally:
            config.MODELS_DIR = original_dir

    def test_insufficient_data_handling(self, test_db, sample_account):
        """Test that insufficient data is handled gracefully"""
        ml_service = MLService(test_db)

        # Try to train with no posts
        with pytest.raises(ValueError, match="Insufficient data"):
            ml_service.train_model(sample_account.id)

    def test_predictions_with_different_content_types(
        self, test_db, sample_posts_large, tmp_path
    ):
        """Test generating predictions for different content types"""
        account_id = sample_posts_large[0].account_id

        import app.ml.config as config
        original_dir = config.MODELS_DIR
        config.MODELS_DIR = tmp_path

        try:
            ml_service = MLService(test_db)
            ml_service.train_model(account_id)

            # Generate predictions for each content type
            for content_type in ["image", "video", "reel"]:
                predictions = ml_service.generate_predictions(
                    account_id=account_id,
                    days_ahead=3,
                    content_types=[content_type]
                )

                assert len(predictions) > 0
                assert all(p["content_type"] == content_type for p in predictions)

        finally:
            config.MODELS_DIR = original_dir

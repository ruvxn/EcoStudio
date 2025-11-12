"""
Confidence scoring for predictions
"""
import numpy as np
from typing import Dict, Any, List
from sklearn.ensemble import RandomForestRegressor
from xgboost import XGBRegressor

from ..config import CONFIDENCE_HIGH, CONFIDENCE_MEDIUM, CONFIDENCE_LOW


class ConfidenceScorer:
    """
    Calculates confidence scores for predictions
    """

    def __init__(self, model, feature_engineer, metrics: Dict[str, Any]):
        """
        Initialize confidence scorer

        Args:
            model: Trained model
            feature_engineer: Fitted FeatureEngineer
            metrics: Training metrics dictionary
        """
        self.model = model
        self.feature_engineer = feature_engineer
        self.metrics = metrics

    def calculate_confidence(
        self,
        X: np.ndarray,
        y_pred: np.ndarray,
    ) -> np.ndarray:
        """
        Calculate confidence scores for predictions

        Confidence is based on:
        1. Model performance (R² score)
        2. Prediction variance (if available from ensemble models)
        3. Feature uncertainty

        Args:
            X: Feature matrix
            y_pred: Predicted values

        Returns:
            Array of confidence scores (0-1)
        """
        n_samples = len(y_pred)
        confidences = np.zeros(n_samples)

        # Base confidence from model R² score
        r2_score = self.metrics.get("test_r2", 0.0)
        base_confidence = self._r2_to_confidence(r2_score)

        # Get prediction variance if model supports it
        prediction_variance = self._get_prediction_variance(X)

        for i in range(n_samples):
            conf = base_confidence

            # Adjust based on prediction variance
            if prediction_variance is not None:
                variance_penalty = self._variance_to_penalty(prediction_variance[i])
                conf *= (1 - variance_penalty)

            # Ensure confidence is in [0, 1]
            confidences[i] = np.clip(conf, 0.0, 1.0)

        return confidences

    def add_confidence_to_predictions(
        self,
        predictions: List[Dict[str, Any]],
        X: np.ndarray,
    ) -> List[Dict[str, Any]]:
        """
        Add confidence scores and levels to prediction dictionaries

        Args:
            predictions: List of prediction dictionaries
            X: Feature matrix used for predictions

        Returns:
            Predictions with confidence scores added
        """
        # Extract predicted values
        y_pred = np.array([p["predicted_engagement"] for p in predictions])

        # Calculate confidences
        confidences = self.calculate_confidence(X, y_pred)

        # Add to predictions
        for i, pred in enumerate(predictions):
            confidence = float(confidences[i])
            pred["confidence_score"] = confidence
            pred["confidence_level"] = self._score_to_level(confidence)

        return predictions

    def get_confidence_summary(self) -> Dict[str, Any]:
        """
        Get summary of model confidence

        Returns:
            Dictionary with confidence summary
        """
        r2_score = self.metrics.get("test_r2", 0.0)
        base_confidence = self._r2_to_confidence(r2_score)

        return {
            "base_confidence": float(base_confidence),
            "confidence_level": self._score_to_level(base_confidence),
            "model_r2": float(r2_score),
            "model_mae": float(self.metrics.get("test_mae", 0.0)),
            "model_type": self.metrics.get("model_type", "unknown"),
            "n_posts": self.metrics.get("n_posts", 0),
            "interpretation": self._interpret_confidence(base_confidence),
        }

    def _r2_to_confidence(self, r2: float) -> float:
        """
        Convert R² score to confidence score

        Args:
            r2: R² score (-inf to 1)

        Returns:
            Confidence score (0-1)
        """
        if r2 >= 0.7:
            # Excellent model: 85-95% confidence
            return 0.85 + (r2 - 0.7) * 0.33
        elif r2 >= 0.5:
            # Good model: 70-85% confidence
            return 0.70 + (r2 - 0.5) * 0.75
        elif r2 >= 0.3:
            # Acceptable model: 50-70% confidence
            return 0.50 + (r2 - 0.3) * 1.0
        elif r2 >= 0.1:
            # Poor model: 30-50% confidence
            return 0.30 + (r2 - 0.1) * 1.0
        else:
            # Very poor model: 10-30% confidence
            return 0.10 + max(r2, 0) * 2.0

    def _get_prediction_variance(self, X: np.ndarray) -> np.ndarray:
        """
        Get prediction variance from ensemble models

        Args:
            X: Feature matrix

        Returns:
            Array of prediction variances, or None if not available
        """
        # Random Forest: use predictions from individual trees
        if isinstance(self.model, RandomForestRegressor):
            # Get predictions from all trees
            tree_predictions = np.array([
                tree.predict(X) for tree in self.model.estimators_
            ])
            # Calculate variance across trees
            return np.var(tree_predictions, axis=0)

        # XGBoost: approximate variance using prediction margin
        elif isinstance(self.model, XGBRegressor):
            # XGBoost doesn't directly provide variance
            # Use a heuristic based on number of trees and learning rate
            # Lower learning rate and more trees = more stable = lower variance
            n_estimators = self.model.n_estimators
            learning_rate = self.model.learning_rate

            # Stability factor (0-1, higher is more stable)
            stability = min(1.0, (n_estimators * learning_rate) / 10)

            # Estimate variance as inverse of stability
            base_variance = 0.1 * (1 - stability)
            return np.full(len(X), base_variance)

        # Other models: no variance estimate available
        return None

    def _variance_to_penalty(self, variance: float) -> float:
        """
        Convert prediction variance to confidence penalty

        Args:
            variance: Prediction variance

        Returns:
            Penalty factor (0-0.5)
        """
        # High variance = high uncertainty = high penalty
        # Use sigmoid-like function to map variance to penalty
        penalty = 0.5 * (1 - np.exp(-variance * 10))
        return np.clip(penalty, 0.0, 0.5)

    def _score_to_level(self, score: float) -> str:
        """
        Convert confidence score to categorical level

        Args:
            score: Confidence score (0-1)

        Returns:
            Confidence level (high/medium/low)
        """
        if score >= CONFIDENCE_HIGH:
            return "high"
        elif score >= CONFIDENCE_MEDIUM:
            return "medium"
        elif score >= CONFIDENCE_LOW:
            return "low"
        else:
            return "very_low"

    def _interpret_confidence(self, confidence: float) -> str:
        """
        Provide human-readable interpretation of confidence

        Args:
            confidence: Confidence score (0-1)

        Returns:
            Interpretation string
        """
        level = self._score_to_level(confidence)

        interpretations = {
            "high": "Model predictions are highly reliable. The model has learned strong patterns from your data.",
            "medium": "Model predictions are reasonably reliable. Consider collecting more data for improvement.",
            "low": "Model predictions have limited reliability. More data or feature engineering recommended.",
            "very_low": "Model predictions are not reliable. Insufficient data or weak patterns detected.",
        }

        return interpretations.get(level, "Unknown confidence level")

    def filter_by_confidence(
        self,
        predictions: List[Dict[str, Any]],
        min_confidence: float = CONFIDENCE_MEDIUM,
    ) -> List[Dict[str, Any]]:
        """
        Filter predictions by minimum confidence score

        Args:
            predictions: List of predictions with confidence scores
            min_confidence: Minimum confidence threshold

        Returns:
            Filtered list of predictions
        """
        return [
            p for p in predictions
            if p.get("confidence_score", 0) >= min_confidence
        ]

    def get_confidence_distribution(
        self,
        predictions: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Get distribution of confidence levels in predictions

        Args:
            predictions: List of predictions with confidence scores

        Returns:
            Dictionary with confidence distribution
        """
        confidence_scores = [p.get("confidence_score", 0) for p in predictions]

        if not confidence_scores:
            return {
                "count": 0,
                "levels": {"high": 0, "medium": 0, "low": 0, "very_low": 0},
            }

        # Count by level
        level_counts = {"high": 0, "medium": 0, "low": 0, "very_low": 0}
        for pred in predictions:
            level = pred.get("confidence_level", "very_low")
            level_counts[level] = level_counts.get(level, 0) + 1

        return {
            "count": len(predictions),
            "mean": float(np.mean(confidence_scores)),
            "median": float(np.median(confidence_scores)),
            "std": float(np.std(confidence_scores)),
            "min": float(np.min(confidence_scores)),
            "max": float(np.max(confidence_scores)),
            "levels": level_counts,
            "level_percentages": {
                k: round(v / len(predictions) * 100, 1)
                for k, v in level_counts.items()
            },
        }

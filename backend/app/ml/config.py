"""
ML-specific configuration settings for Instagram engagement prediction
"""
from pathlib import Path
from typing import Dict, Any

# Paths
ML_MODULE_DIR = Path(__file__).parent
MODELS_DIR = ML_MODULE_DIR / "models"

# Dataset Requirements
MIN_POSTS_REQUIRED = 30
RECOMMENDED_POSTS = 100
TRAIN_TEST_SPLIT = 0.8  # 80/20 split

# Model Configuration
XGBOOST_CONFIG_SMALL: Dict[str, Any] = {
    # For 30-50 posts
    "n_estimators": 50,
    "max_depth": 2,
    "learning_rate": 0.05,
    "reg_alpha": 1.5,  # L1 regularization
    "reg_lambda": 1.5,  # L2 regularization
    "min_child_weight": 3,
    "subsample": 0.8,
    "colsample_bytree": 0.8,
    "random_state": 42,
    "n_jobs": -1,
}

XGBOOST_CONFIG_MEDIUM: Dict[str, Any] = {
    # For 50-100 posts
    "n_estimators": 100,
    "max_depth": 3,
    "learning_rate": 0.05,
    "reg_alpha": 1.0,
    "reg_lambda": 1.0,
    "min_child_weight": 2,
    "subsample": 0.8,
    "colsample_bytree": 0.8,
    "random_state": 42,
    "n_jobs": -1,
}

XGBOOST_CONFIG_LARGE: Dict[str, Any] = {
    # For 100+ posts
    "n_estimators": 150,
    "max_depth": 4,
    "learning_rate": 0.05,
    "reg_alpha": 0.5,
    "reg_lambda": 0.5,
    "min_child_weight": 1,
    "subsample": 0.8,
    "colsample_bytree": 0.8,
    "random_state": 42,
    "n_jobs": -1,
}

RANDOM_FOREST_CONFIG: Dict[str, Any] = {
    # Backup for very small datasets
    "n_estimators": 100,
    "max_depth": 3,
    "min_samples_split": 5,
    "min_samples_leaf": 2,
    "random_state": 42,
    "n_jobs": -1,
}

# Cross-Validation
CV_FOLDS = 5
CV_SCORING = "neg_mean_absolute_error"

# Feature Engineering
CONTENT_TYPES = ["image", "video", "carousel", "reel", "story"]
TIME_OF_DAY_BINS = {
    "morning": (6, 12),
    "afternoon": (12, 17),
    "evening": (17, 21),
    "night": (21, 6),
}

# Prediction Settings
DEFAULT_PREDICTION_DAYS = 7
MAX_PREDICTION_DAYS = 30
TOP_PREDICTIONS_TO_STORE = 30

# Confidence Thresholds
CONFIDENCE_HIGH = 0.8
CONFIDENCE_MEDIUM = 0.6
CONFIDENCE_LOW = 0.4

# Evaluation Metrics Targets
TARGET_R2_SCORE = 0.5  # Good performance
MIN_R2_SCORE = 0.3    # Minimum acceptable

# Model Versioning
MODEL_VERSION = "1.0"


def get_model_config(n_posts: int) -> Dict[str, Any]:
    """
    Get appropriate model configuration based on dataset size

    Args:
        n_posts: Number of posts in training dataset

    Returns:
        Dictionary of model hyperparameters
    """
    if n_posts < MIN_POSTS_REQUIRED:
        raise ValueError(f"Insufficient data: {n_posts} posts. Minimum required: {MIN_POSTS_REQUIRED}")
    elif n_posts < 50:
        return XGBOOST_CONFIG_SMALL
    elif n_posts < 100:
        return XGBOOST_CONFIG_MEDIUM
    else:
        return XGBOOST_CONFIG_LARGE


def get_model_path(account_id: int, version: str = None) -> Path:
    """
    Get the path for saving/loading a model

    Args:
        account_id: Instagram account ID
        version: Model version timestamp (defaults to 'latest')

    Returns:
        Path to model file
    """
    if version is None:
        version = "latest"

    filename = f"account_{account_id}_v{version}.joblib"
    return MODELS_DIR / filename


def should_use_advanced_features(n_posts: int) -> bool:
    """
    Determine if advanced features should be included

    Args:
        n_posts: Number of posts in dataset

    Returns:
        True if dataset is large enough for advanced features
    """
    return n_posts >= RECOMMENDED_POSTS

"""
API endpoints for ML predictions and model training.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime, timezone
import time
import asyncio
from concurrent.futures import ThreadPoolExecutor

from app.core.database import get_db
from app.api.schemas import (
    PredictionRequest,
    TrainModelRequest,
    PredictionSchedule,
    TrainModelResponse,
    PredictionResponse,
)
from app.services.ml_service import MLService

router = APIRouter()

# Thread pool for CPU-intensive ML operations
ml_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="ml_training")


def _train_model_sync(account_id: int, force_retrain: bool, db: Session):
    """
    Synchronous training function to run in thread pool.

    Args:
        account_id: Social account ID
        force_retrain: Force retraining even if recent model exists
        db: Database session

    Returns:
        Training result dictionary
    """
    ml_service = MLService(db)
    return ml_service.train_model(
        account_id=account_id,
        force_retrain=force_retrain,
    )


@router.post("/train", response_model=TrainModelResponse)
async def train_model(
    request: TrainModelRequest,
    db: Session = Depends(get_db),
):
    """
    Trigger ML model retraining for an account.

    This endpoint runs training in a background thread to avoid blocking
    the async event loop and freezing the application.

    Args:
        request: Training request with account ID
        db: Database session

    Returns:
        Training job status and model metrics
    """
    start_time = time.time()

    try:
        # Run training in thread pool to avoid blocking event loop
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            ml_executor,
            _train_model_sync,
            request.account_id,
            request.force_retrain,
            db
        )

        duration = int(time.time() - start_time)

        metrics = result.get("metrics", {})

        return TrainModelResponse(
            success=True,
            message=result.get("message", "Model trained successfully"),
            model_version=metrics.get("model_version", "unknown"),
            training_samples=metrics.get("n_posts", 0),
            accuracy=metrics.get("test_r2", 0.0),
            training_duration_seconds=duration,
            job_id=None,
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except FileNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Training failed: {str(e)}",
        )


@router.post("/schedule", response_model=PredictionSchedule)
async def get_prediction_schedule(
    request: PredictionRequest,
    db: Session = Depends(get_db),
):
    """
    Get ML predictions for optimal posting times.

    Args:
        request: Prediction request with account ID and time range
        db: Database session

    Returns:
        Scheduled posting times with predicted engagement
    """
    ml_service = MLService(db)

    try:
        # Generate fresh predictions
        predictions = ml_service.generate_predictions(
            account_id=request.account_id,
            days_ahead=request.days,
            content_types=[request.content_type.value],
            min_confidence=request.min_confidence,
            store_in_db=False,  # Don't store on-demand predictions
        )

        if not predictions:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No predictions meet the specified criteria",
            )

        # Convert to response format
        prediction_responses = []
        for pred in predictions:
            # Create a PredictionResponse-like dict
            pred_response = {
                "id": 0,  # Temporary predictions don't have IDs
                "prediction_date": datetime.fromisoformat(pred["posted_at"].replace('Z', '+00:00')).date()
                    if isinstance(pred["posted_at"], str) else pred["posted_at"].date(),
                "day_of_week": pred["day_of_week"],
                "day_name": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"][pred["day_of_week"]],
                "hour": pred["hour"],
                "content_type": pred["content_type"],
                "predicted_engagement": pred["predicted_engagement"],
                "confidence_score": pred.get("confidence_score", 0.5),
                "confidence_level": pred.get("confidence_level", "medium"),
                "model_version": "1.0",
                "created_at": datetime.now(timezone.utc),
            }
            prediction_responses.append(pred_response)

        # Calculate stats
        avg_engagement = sum(p["predicted_engagement"] for p in predictions) / len(predictions)
        dates = [datetime.fromisoformat(p["posted_at"].replace('Z', '+00:00')).date()
                 if isinstance(p["posted_at"], str) else p["posted_at"].date()
                 for p in predictions]

        return PredictionSchedule(
            account_id=request.account_id,
            predictions=prediction_responses,
            total_predictions=len(predictions),
            date_range_start=min(dates),
            date_range_end=max(dates),
            avg_predicted_engagement=avg_engagement,
            model_version="1.0",
        )

    except FileNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Model not trained for this account. Please train the model first.",
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Prediction generation failed: {str(e)}",
        )


@router.get("/{account_id}/latest", response_model=PredictionSchedule)
async def get_latest_predictions(
    account_id: int,
    days: int = 7,
    db: Session = Depends(get_db),
):
    """
    Get the most recent predictions for an account.

    Args:
        account_id: ID of the account
        days: Number of days to retrieve predictions for
        db: Database session

    Returns:
        Latest prediction schedule
    """
    ml_service = MLService(db)

    try:
        # Get stored predictions from database
        predictions = ml_service.get_predictions(
            account_id=account_id,
            days_ahead=days,
            limit=30,
        )

        if not predictions:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No predictions found for this account. Please train the model first.",
            )

        # Convert to response format
        prediction_responses = []
        for pred in predictions:
            prediction_responses.append(PredictionResponse(**pred))

        # Calculate stats
        avg_engagement = sum(p["predicted_engagement"] for p in predictions) / len(predictions)
        from datetime import date as date_type
        dates = [pred["prediction_date"]
                 if isinstance(pred["prediction_date"], date_type)
                 else datetime.fromisoformat(pred["prediction_date"]).date()
                 for pred in predictions]

        return PredictionSchedule(
            account_id=account_id,
            predictions=prediction_responses,
            total_predictions=len(predictions),
            date_range_start=min(dates),
            date_range_end=max(dates),
            avg_predicted_engagement=avg_engagement,
            model_version=predictions[0].get("model_version", "1.0"),
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve predictions: {str(e)}",
        )

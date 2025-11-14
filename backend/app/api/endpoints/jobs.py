"""
Jobs API endpoints for managing background job queue and analytics.
"""
import logging
from datetime import datetime, timedelta
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session
from sqlalchemy import and_, func
from pydantic import BaseModel

from app.core.database import get_db
from app.api.models.job_queue import Job, JobType, JobStatus
from app.api.models.carbon_savings import CarbonSaving

logger = logging.getLogger(__name__)

router = APIRouter()


# Request Models
class ScheduleJobRequest(BaseModel):
    """Request model for scheduling a job."""
    job_type: str
    account_id: Optional[int] = None
    use_green_window: bool = True
    priority: int = 5


# Response Models
class JobResponse(BaseModel):
    """Response model for a single job."""
    id: int
    type: str
    account_id: Optional[int]
    scheduled_for: str
    carbon_intensity: Optional[int]
    carbon_score: Optional[float]
    status: str
    priority: int
    created_at: str
    started_at: Optional[str]
    completed_at: Optional[str]
    duration_seconds: Optional[int]
    error_message: Optional[str]


class JobListResponse(BaseModel):
    """Response model for job list."""
    total: int
    jobs: List[JobResponse]


class CarbonAnalyticsSummary(BaseModel):
    """Summary statistics for carbon analytics."""
    period_days: int
    total_jobs: int
    total_carbon_saved_kg: float
    avg_saved_per_job_grams: float
    total_energy_kwh: float


class DailyBreakdown(BaseModel):
    """Daily carbon savings breakdown."""
    date: str
    saved_grams: int
    job_count: int


class CarbonAnalyticsResponse(BaseModel):
    """Response model for carbon analytics."""
    summary: CarbonAnalyticsSummary
    daily_breakdown: List[DailyBreakdown]


@router.get("", response_model=JobListResponse)
async def get_jobs(
    status: Optional[str] = Query(None, description="Filter by job status"),
    account_id: Optional[int] = Query(None, description="Filter by account ID"),
    job_type: Optional[str] = Query(None, description="Filter by job type"),
    limit: int = Query(50, ge=1, le=200, description="Maximum number of jobs to return"),
    offset: int = Query(0, ge=0, description="Number of jobs to skip"),
    db: Session = Depends(get_db)
):
    """
    Get job queue with optional filters.

    Returns a list of jobs from the queue with optional filtering by
    status, account, or job type.

    Args:
        status: Filter by status (queued, running, completed, failed)
        account_id: Filter by account ID
        job_type: Filter by job type
        limit: Maximum number of results (1-200, default 50)
        offset: Number of results to skip (for pagination)
    """
    try:
        # Build query with filters
        query = db.query(Job)

        if status:
            try:
                status_enum = JobStatus(status.lower())
                query = query.filter(Job.status == status_enum)
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Invalid status: {status}")

        if account_id:
            query = query.filter(Job.account_id == account_id)

        if job_type:
            try:
                type_enum = JobType(job_type.upper())
                query = query.filter(Job.job_type == type_enum)
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Invalid job type: {job_type}")

        # Get total count
        total = query.count()

        # Get paginated results
        jobs = query.order_by(Job.created_at.desc()).offset(offset).limit(limit).all()

        job_responses = [
            JobResponse(
                id=j.id,
                type=j.job_type.value,
                account_id=j.account_id,
                scheduled_for=j.scheduled_for.isoformat(),
                carbon_intensity=j.carbon_intensity,
                carbon_score=round(j.carbon_score, 2) if j.carbon_score else None,
                status=j.status.value,
                priority=j.priority,
                created_at=j.created_at.isoformat(),
                started_at=j.started_at.isoformat() if j.started_at else None,
                completed_at=j.completed_at.isoformat() if j.completed_at else None,
                duration_seconds=j.execution_duration_seconds,
                error_message=j.error_message
            )
            for j in jobs
        ]

        return JobListResponse(total=total, jobs=job_responses)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching jobs: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch jobs")


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(job_id: int, db: Session = Depends(get_db)):
    """
    Get a specific job by ID.

    Args:
        job_id: Job ID to retrieve
    """
    try:
        job = db.query(Job).filter(Job.id == job_id).first()

        if not job:
            raise HTTPException(status_code=404, detail="Job not found")

        return JobResponse(
            id=job.id,
            type=job.job_type.value,
            account_id=job.account_id,
            scheduled_for=job.scheduled_for.isoformat(),
            carbon_intensity=job.carbon_intensity,
            carbon_score=round(job.carbon_score, 2) if job.carbon_score else None,
            status=job.status.value,
            priority=job.priority,
            created_at=job.created_at.isoformat(),
            started_at=job.started_at.isoformat() if job.started_at else None,
            completed_at=job.completed_at.isoformat() if job.completed_at else None,
            duration_seconds=job.execution_duration_seconds,
            error_message=job.error_message
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching job {job_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch job")


@router.post("/schedule")
async def schedule_job(
    request: ScheduleJobRequest,
    req: Request,
    db: Session = Depends(get_db)
):
    """
    Manually schedule a job with carbon optimization.

    Creates a new job in the queue, optionally scheduling it during
    a green window with low carbon intensity.

    Args:
        request: Job scheduling request with type, account_id, and options
    """
    try:
        # Validate job type
        try:
            job_type = JobType(request.job_type.upper())
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid job type: {request.job_type}"
            )

        # Get scheduler from app state
        if not hasattr(req.app.state, 'scheduler'):
            raise HTTPException(
                status_code=503,
                detail="Scheduler not initialized"
            )

        scheduler = req.app.state.scheduler

        # Determine duration based on job type
        duration_map = {
            JobType.RETRAIN_MODEL: 30,
            JobType.GENERATE_CONTENT: 15,
            JobType.SYNC_POSTS: 10,
            JobType.POST_CONTENT: 5,
            JobType.FETCH_CARBON_FORECAST: 5,
            JobType.CALCULATE_ENGAGEMENT: 10,
        }
        duration = duration_map.get(job_type, 30)

        # Schedule the job
        job_id = await scheduler.schedule_job(
            db=db,
            job_type=job_type,
            account_id=request.account_id,
            duration_minutes=duration,
            use_green_window=request.use_green_window,
            priority=request.priority
        )

        return {
            "job_id": job_id,
            "status": "scheduled",
            "message": "Job scheduled successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error scheduling job: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to schedule job")


@router.delete("/{job_id}")
async def cancel_job(job_id: int, db: Session = Depends(get_db)):
    """
    Cancel a queued job.

    Only jobs with status 'queued' can be cancelled. Running or
    completed jobs cannot be cancelled.

    Args:
        job_id: Job ID to cancel
    """
    try:
        job = db.query(Job).filter(Job.id == job_id).first()

        if not job:
            raise HTTPException(status_code=404, detail="Job not found")

        if job.status != JobStatus.QUEUED:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot cancel job with status: {job.status.value}"
            )

        job.status = JobStatus.CANCELLED
        job.completed_at = datetime.utcnow()
        db.commit()

        return {
            "job_id": job_id,
            "status": "cancelled",
            "message": "Job cancelled successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error cancelling job {job_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to cancel job")


@router.get("/analytics/carbon", response_model=CarbonAnalyticsResponse)
async def get_carbon_analytics(
    days: int = Query(30, ge=1, le=365, description="Number of days to analyze"),
    db: Session = Depends(get_db)
):
    """
    Get carbon savings analytics.

    Returns aggregated carbon savings data showing the environmental
    impact of eco-scheduling over the specified time period.

    Args:
        days: Number of days to analyze (1-365, default 30)
    """
    try:
        start_date = datetime.utcnow() - timedelta(days=days)

        # Get summary statistics
        stats = db.query(
            func.count(CarbonSaving.id).label('total_jobs'),
            func.sum(CarbonSaving.carbon_saved_grams).label('total_saved_grams'),
            func.avg(CarbonSaving.carbon_saved_grams).label('avg_saved_per_job'),
            func.sum(CarbonSaving.energy_used_kwh).label('total_energy_kwh')
        ).filter(
            CarbonSaving.created_at >= start_date
        ).first()

        # Get daily breakdown
        daily_stats = db.query(
            func.date(CarbonSaving.created_at).label('date'),
            func.sum(CarbonSaving.carbon_saved_grams).label('saved_grams'),
            func.count(CarbonSaving.id).label('job_count')
        ).filter(
            CarbonSaving.created_at >= start_date
        ).group_by(
            func.date(CarbonSaving.created_at)
        ).order_by(
            func.date(CarbonSaving.created_at).desc()
        ).all()

        # Build response
        summary = CarbonAnalyticsSummary(
            period_days=days,
            total_jobs=stats.total_jobs or 0,
            total_carbon_saved_kg=round((stats.total_saved_grams or 0) / 1000, 2),
            avg_saved_per_job_grams=round(stats.avg_saved_per_job or 0, 1),
            total_energy_kwh=round(stats.total_energy_kwh or 0, 2)
        )

        daily_breakdown = [
            DailyBreakdown(
                date=d.date.isoformat(),
                saved_grams=int(d.saved_grams),
                job_count=d.job_count
            )
            for d in daily_stats
        ]

        return CarbonAnalyticsResponse(
            summary=summary,
            daily_breakdown=daily_breakdown
        )

    except Exception as e:
        logger.error(f"Error fetching carbon analytics: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch carbon analytics")


@router.get("/stats/summary")
async def get_job_stats(db: Session = Depends(get_db)):
    """
    Get summary statistics for the job queue.

    Returns counts of jobs by status and other summary metrics.
    """
    try:
        # Count by status
        status_counts = db.query(
            Job.status,
            func.count(Job.id).label('count')
        ).group_by(Job.status).all()

        status_dict = {s.value: 0 for s in JobStatus}
        for status, count in status_counts:
            status_dict[status.value] = count

        # Get next scheduled job
        next_job = db.query(Job).filter(
            Job.status == JobStatus.QUEUED
        ).order_by(Job.scheduled_for.asc()).first()

        return {
            "status_counts": status_dict,
            "next_scheduled_job": {
                "id": next_job.id,
                "type": next_job.job_type.value,
                "scheduled_for": next_job.scheduled_for.isoformat()
            } if next_job else None,
            "timestamp": datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error(f"Error fetching job stats: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch job stats")

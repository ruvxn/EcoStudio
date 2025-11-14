"""
Eco Scheduler Service for carbon-aware job orchestration.
Manages background job execution during low-carbon windows.
"""
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.api.models.job_queue import Job, JobType, JobStatus
from app.api.models.social_accounts import SocialAccount
from app.services.carbon_forecast_service import CarbonForecastService
from app.services.green_window_finder import GreenWindowFinder

logger = logging.getLogger(__name__)


class EcoScheduler:
    """
    Carbon-aware job scheduler.

    Orchestrates background tasks to execute during low-carbon energy windows,
    reducing the environmental impact of compute-intensive operations.
    """

    def __init__(self, db_session_factory):
        """
        Initialize the eco scheduler.

        Args:
            db_session_factory: Callable that returns a database session
        """
        self.db_session_factory = db_session_factory
        self.scheduler = AsyncIOScheduler()

    async def start(self):
        """Initialize and start the scheduler."""
        logger.info("Starting EcoScheduler...")

        # Job 1: Update carbon forecasts every 6 hours
        self.scheduler.add_job(
            self.update_carbon_forecasts,
            CronTrigger(hour='*/6'),
            id='update_carbon_forecasts',
            name='Update Carbon Forecasts',
            replace_existing=True
        )

        # Job 2: Execute pending jobs every 30 minutes
        self.scheduler.add_job(
            self.execute_pending_jobs,
            IntervalTrigger(minutes=30),
            id='execute_pending_jobs',
            name='Execute Pending Jobs',
            replace_existing=True
        )

        # Job 3: Schedule weekly model retraining (Sundays at midnight UTC)
        self.scheduler.add_job(
            self.schedule_weekly_retraining,
            CronTrigger(day_of_week='sun', hour=0, minute=0),
            id='schedule_weekly_retraining',
            name='Schedule Weekly Retraining',
            replace_existing=True
        )

        # Run initial forecast update
        await self.update_carbon_forecasts()

        # Start the scheduler
        self.scheduler.start()
        logger.info("EcoScheduler started successfully")

    def shutdown(self):
        """Gracefully shut down the scheduler."""
        logger.info("Shutting down EcoScheduler...")
        self.scheduler.shutdown()
        logger.info("EcoScheduler shut down")

    async def update_carbon_forecasts(self):
        """Update carbon forecasts from ElectricityMap API."""
        logger.info(f"[{datetime.utcnow()}] Running scheduled carbon forecast update")

        db = self.db_session_factory()
        try:
            carbon_service = CarbonForecastService(db)
            count = await carbon_service.update_forecasts()
            logger.info(f"Carbon forecast update completed: {count} entries")
        except Exception as e:
            logger.error(f"Error updating carbon forecasts: {e}", exc_info=True)
        finally:
            db.close()

    async def execute_pending_jobs(self):
        """Check for jobs that should execute now."""
        logger.info(f"[{datetime.utcnow()}] Checking for pending jobs...")

        db = self.db_session_factory()
        try:
            # Find jobs whose scheduled time has arrived
            now = datetime.utcnow()
            jobs = db.query(Job).filter(
                and_(
                    Job.status == JobStatus.QUEUED,
                    Job.scheduled_for <= now
                )
            ).order_by(
                Job.priority.asc(),  # Lower priority number = higher priority
                Job.scheduled_for.asc()
            ).all()

            if jobs:
                logger.info(f"Found {len(jobs)} pending jobs to execute")
                for job in jobs:
                    await self.execute_job(job, db)
            else:
                logger.debug("No pending jobs to execute")

        except Exception as e:
            logger.error(f"Error executing pending jobs: {e}", exc_info=True)
        finally:
            db.close()

    async def schedule_weekly_retraining(self):
        """Schedule model retraining for all accounts in green windows."""
        logger.info(f"[{datetime.utcnow()}] Scheduling weekly model retraining...")

        db = self.db_session_factory()
        try:
            # Get all active Instagram accounts
            accounts = db.query(SocialAccount).filter(
                SocialAccount.platform == 'instagram'
            ).all()

            logger.info(f"Found {len(accounts)} accounts for retraining")

            for account in accounts:
                # Schedule retraining before next Sunday midnight
                next_week = datetime.utcnow() + timedelta(days=7)

                job_id = await self.schedule_job(
                    db=db,
                    job_type=JobType.RETRAIN_MODEL,
                    account_id=account.id,
                    before_time=next_week,
                    duration_minutes=30,  # Model retraining ~30 min
                    use_green_window=True,
                    metadata={'scheduled_by': 'weekly_cron'}
                )

                logger.info(f"Scheduled retraining job {job_id} for account {account.id}")

        except Exception as e:
            logger.error(f"Error scheduling weekly retraining: {e}", exc_info=True)
        finally:
            db.close()

    async def schedule_job(
        self,
        db: Session,
        job_type: JobType,
        account_id: Optional[int] = None,
        before_time: Optional[datetime] = None,
        duration_minutes: int = 60,
        use_green_window: bool = True,
        priority: int = 5,
        metadata: Optional[dict] = None
    ) -> int:
        """
        Schedule a job with carbon optimization.

        Args:
            db: Database session
            job_type: Type of job to schedule
            account_id: Account to process (if applicable)
            before_time: Job must complete before this (None = ASAP)
            duration_minutes: Estimated job duration
            use_green_window: Whether to optimize for carbon
            priority: Job priority (1=highest, 10=lowest)
            metadata: Additional job-specific data

        Returns:
            job_id
        """
        if before_time is None:
            before_time = datetime.utcnow() + timedelta(days=7)

        carbon_service = CarbonForecastService(db)
        window_finder = GreenWindowFinder(db)

        optimal_window = None
        scheduled_for = datetime.utcnow()  # Default: immediate
        carbon_intensity = carbon_service.get_current_intensity()
        carbon_score = 0.0

        if use_green_window:
            optimal_window = window_finder.find_optimal_window(
                before_time=before_time,
                duration_minutes=duration_minutes,
                job_type=job_type.value
            )

            if optimal_window:
                scheduled_for = optimal_window['window_start']
                carbon_intensity = optimal_window['carbon_intensity']
                carbon_score = optimal_window['score']
                logger.info(
                    f"Scheduled {job_type.value} in green window: {scheduled_for} "
                    f"({carbon_intensity} gCO2/kWh, score: {carbon_score:.2f})"
                )
            else:
                logger.info(f"No green window found for {job_type.value}, scheduling immediately")

        # Insert job into queue
        job = Job(
            job_type=job_type,
            account_id=account_id,
            scheduled_for=scheduled_for,
            carbon_intensity=carbon_intensity,
            estimated_duration_minutes=duration_minutes,
            optimal_window_start=optimal_window['window_start'] if optimal_window else None,
            optimal_window_end=optimal_window['window_end'] if optimal_window else None,
            carbon_score=carbon_score,
            priority=priority,
            status=JobStatus.QUEUED,
            result=metadata or {}
        )

        db.add(job)
        db.commit()
        db.refresh(job)

        logger.info(f"Created job {job.id}: {job_type.value} scheduled for {scheduled_for}")

        return job.id

    async def execute_job(self, job: Job, db: Session):
        """
        Execute a specific job and log results.

        Args:
            job: Job object to execute
            db: Database session
        """
        logger.info(f"[{datetime.utcnow()}] Executing job {job.id}: {job.job_type.value}")

        # Mark as running
        job.status = JobStatus.RUNNING
        job.started_at = datetime.utcnow()
        db.commit()

        start_time = datetime.utcnow()
        success = False
        error_message = None

        try:
            # Execute based on job type
            if job.job_type == JobType.RETRAIN_MODEL:
                await self._execute_model_retraining(job, db)
                success = True

            elif job.job_type == JobType.GENERATE_CONTENT:
                await self._execute_content_generation(job, db)
                success = True

            elif job.job_type == JobType.SYNC_POSTS:
                await self._execute_post_sync(job, db)
                success = True

            elif job.job_type == JobType.FETCH_CARBON_FORECAST:
                carbon_service = CarbonForecastService(db)
                await carbon_service.update_forecasts()
                success = True

            else:
                error_message = f"Unknown job type: {job.job_type.value}"
                logger.warning(error_message)

        except Exception as e:
            error_message = str(e)
            logger.error(f"Error executing job {job.id}: {e}", exc_info=True)

        # Calculate execution time
        execution_time_seconds = (datetime.utcnow() - start_time).total_seconds()
        execution_time_minutes = int(execution_time_seconds / 60)

        # Update job status
        job.status = JobStatus.COMPLETED if success else JobStatus.FAILED
        job.completed_at = datetime.utcnow()
        job.error_message = error_message
        db.commit()

        # Log carbon savings if successful
        if success and job.carbon_intensity:
            window_finder = GreenWindowFinder(db)
            savings = window_finder.calculate_carbon_savings(
                actual_carbon_intensity=job.carbon_intensity,
                scheduled_time=job.scheduled_for,
                duration_minutes=max(execution_time_minutes, 1),
                job_type=job.job_type.value
            )

            window_finder.store_carbon_savings(job.id, savings)
            logger.info(f"Job {job.id} saved {savings['carbon_saved_grams']}g CO₂")

        result_status = "completed" if success else "failed"
        logger.info(
            f"Job {job.id} {result_status} in {execution_time_seconds:.1f}s"
        )

    async def _execute_model_retraining(self, job: Job, db: Session):
        """Execute model retraining for an account."""
        logger.info(f"Retraining model for account {job.account_id}")

        try:
            # Import here to avoid circular dependency
            from app.ml.service import MLService

            ml_service = MLService(db)
            result = await ml_service.train_model(job.account_id)

            job.result = {
                'model_trained': True,
                'metrics': result.get('metrics', {}),
                'timestamp': datetime.utcnow().isoformat()
            }

            logger.info(f"Model retrained successfully for account {job.account_id}")

        except Exception as e:
            logger.error(f"Error retraining model: {e}", exc_info=True)
            raise

    async def _execute_content_generation(self, job: Job, db: Session):
        """Execute content generation for an account."""
        logger.info(f"Generating content for account {job.account_id}")

        # Will be implemented in Phase 3
        # For now, just log
        job.result = {
            'content_generated': False,
            'message': 'Content generation not yet implemented (Phase 3)',
            'timestamp': datetime.utcnow().isoformat()
        }

        logger.info("Content generation placeholder executed")

    async def _execute_post_sync(self, job: Job, db: Session):
        """Execute post synchronization for an account."""
        logger.info(f"Syncing posts for account {job.account_id}")

        try:
            from app.services.instagram_sync import InstagramSyncService

            sync_service = InstagramSyncService(db)
            result = await sync_service.sync_account_posts(job.account_id)

            job.result = {
                'posts_synced': result.get('count', 0),
                'timestamp': datetime.utcnow().isoformat()
            }

            logger.info(f"Synced {result.get('count', 0)} posts for account {job.account_id}")

        except Exception as e:
            logger.error(f"Error syncing posts: {e}", exc_info=True)
            raise

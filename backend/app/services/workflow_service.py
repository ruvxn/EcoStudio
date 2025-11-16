"""
Workflow Orchestration Service.
Manages end-to-end automation workflows for content generation and posting.
"""

from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.api.models.scheduled_posts import ScheduledPost, PostStatus
from app.api.models.job_queue import Job, JobType, JobStatus
from app.services.content_generation_service import ContentGenerationService
from app.services.ml_service import MLService


class WorkflowService:
    """Service for orchestrating end-to-end content workflows."""

    def __init__(self, db: AsyncSession):
        """
        Initialize workflow service.

        Args:
            db: Async database session
        """
        self.db = db

    async def create_weekly_plan(
        self,
        account_id: int,
        num_posts: int = 7,
        auto_generate: bool = True,
        content_type: str = "IMAGE"
    ) -> Dict:
        """
        SIMPLE weekly posting plan: 7 posts, best times from analytics, content in green windows.

        Flow:
        1. Find best posting times for next 7 days (from ML or default to noon)
        2. Create 7 scheduled posts for those times
        3. Schedule content generation in earliest low-carbon windows
        4. Posts auto-publish at optimal engagement times

        Args:
            account_id: Social account ID
            num_posts: Number of posts (default 7)
            auto_generate: Generate content automatically (default True)
            content_type: IMAGE, VIDEO, etc.

        Returns:
            {
                "scheduled_posts": [post_ids],
                "generation_jobs": [job_ids],
                "post_times": [...],
                "summary": {...}
            }
        """
        now = datetime.now(timezone.utc)

        scheduled_posts = []
        generation_jobs = []
        post_times = []
        post_summaries = []

        # Step 1: Get optimal posting times (try ML, fallback to defaults)
        optimal_times = []
        try:
            # Use sync session for MLService (it requires sync Session)
            from app.core.database import SessionLocal
            sync_db = SessionLocal()
            try:
                ml_service = MLService(sync_db)
                predictions = ml_service.generate_predictions(
                    account_id=account_id,
                    days_ahead=num_posts,
                    store_in_db=False,
                )
                # Use ML predictions if available
                for pred in predictions[:num_posts]:
                    try:
                        post_time = self._parse_prediction_time(pred.get('posted_at') or pred.get('datetime'))
                        engagement = pred.get('predicted_engagement', 0.0)
                        optimal_times.append({
                            'time': post_time,
                            'engagement': engagement,
                            'day_name': post_time.strftime('%A')
                        })
                    except:
                        continue
            finally:
                sync_db.close()
        except Exception as e:
            print(f"⚠️ ML predictions failed ({e}), using default times")

        # Fallback: Use default best times if ML didn't provide enough predictions
        if len(optimal_times) < num_posts:
            print(f"📅 Using default times for {num_posts - len(optimal_times)} posts")
            for i in range(len(optimal_times), num_posts):
                post_time = (now + timedelta(days=i+1)).replace(hour=12, minute=0, second=0, microsecond=0, tzinfo=timezone.utc)
                optimal_times.append({
                    'time': post_time,
                    'engagement': 0.5,  # Default medium engagement
                    'day_name': post_time.strftime('%A')
                })

        # Step 2: Create posts and schedule generation for each day
        for i, time_data in enumerate(optimal_times[:num_posts]):
            post_time = time_data['time']
            day_name = time_data['day_name']

            # Create scheduled post with simple topic
            post = ScheduledPost(
                account_id=account_id,
                scheduled_time=post_time,
                content_type=content_type,
                predicted_engagement=time_data['engagement'],
                status=PostStatus.PENDING,
                auto_post_enabled=True,
                user_approved=False,
                content=None  # Will be generated later in green window
            )

            self.db.add(post)
            await self.db.flush()

            scheduled_posts.append(post.id)
            post_times.append(post_time.isoformat())
            post_summaries.append({
                'post_id': post.id,
                'day': day_name,
                'scheduled_time': post_time.strftime('%Y-%m-%d %I:%M %p'),
                'status': 'Content will be generated in low-carbon window'
            })

            # Step 3: Schedule content generation in GREEN WINDOW
            if auto_generate:
                # Generate 1-24 hours before post time (in earliest green window)
                generate_before = post_time - timedelta(hours=1)

                try:
                    job_id = await self._create_generation_job(
                        scheduled_post_id=post.id,
                        account_id=account_id,
                        content_type=content_type,
                        post_time=post_time,
                        generate_before=generate_before
                    )
                    generation_jobs.append(job_id)
                    post.generation_job_id = job_id
                except Exception as e:
                    import traceback
                    error_details = traceback.format_exc()
                    print(f"⚠️ Failed to schedule generation for {day_name}: {e}")
                    print(f"Full error: {error_details}")
                    # Don't fail the entire weekly plan if job creation fails
                    # The post will still be created, just without auto-generation

        # Commit everything
        await self.db.commit()

        return {
            "scheduled_posts": scheduled_posts,
            "generation_jobs": generation_jobs,
            "post_times": post_times,
            "posts_preview": post_summaries,
            "summary": {
                "total_posts_scheduled": len(scheduled_posts),
                "auto_generation_enabled": auto_generate,
                "generation_jobs_created": len(generation_jobs),
                "date_range": {
                    "start": post_times[0] if post_times else None,
                    "end": post_times[-1] if post_times else None
                },
                "message": f"✅ Created {len(scheduled_posts)} posts. Content will be generated during low-carbon windows and posted at optimal engagement times."
            }
        }

    async def get_workflow_status(self, account_id: int) -> Dict:
        """
        Get overview of automation workflow status for an account.

        Args:
            account_id: Social account ID

        Returns:
            {
                "pending": 5,
                "generated": 3,
                "approved": 2,
                "posted": 10,
                "failed": 1,
                "upcoming_posts": [...],
                "recent_activity": [...]
            }
        """
        # Count posts by status
        status_counts = {}
        for post_status in PostStatus:
            count_query = select(func.count()).select_from(ScheduledPost).where(
                ScheduledPost.account_id == account_id,
                ScheduledPost.status == post_status
            )
            result = await self.db.execute(count_query)
            count = result.scalar()
            status_counts[post_status.value] = count

        # Get upcoming posts (next 7 days)
        now = datetime.now(timezone.utc)
        upcoming_cutoff = now + timedelta(days=7)
        upcoming_query = select(ScheduledPost).where(
            ScheduledPost.account_id == account_id,
            ScheduledPost.scheduled_time >= now,
            ScheduledPost.scheduled_time <= upcoming_cutoff,
            ScheduledPost.status.in_([PostStatus.PENDING, PostStatus.GENERATED, PostStatus.APPROVED])
        ).order_by(ScheduledPost.scheduled_time.asc()).limit(10)
        result = await self.db.execute(upcoming_query)
        upcoming_posts = result.scalars().all()

        # Get recent activity (last 7 days)
        recent_cutoff = now - timedelta(days=7)
        recent_query = select(ScheduledPost).where(
            ScheduledPost.account_id == account_id,
            ScheduledPost.posted_at >= recent_cutoff
        ).order_by(ScheduledPost.posted_at.desc()).limit(10)
        result = await self.db.execute(recent_query)
        recent_posts = result.scalars().all()

        return {
            "status_counts": status_counts,
            "pending": status_counts.get('PENDING', 0),
            "generated": status_counts.get('GENERATED', 0),
            "approved": status_counts.get('APPROVED', 0),
            "posted": status_counts.get('POSTED', 0),
            "failed": status_counts.get('FAILED', 0),
            "upcoming_posts": [
                {
                    "id": p.id,
                    "scheduled_time": p.scheduled_time.isoformat(),
                    "status": p.status.value,
                    "has_content": bool(p.content),
                    "user_approved": p.user_approved
                }
                for p in upcoming_posts
            ],
            "recent_activity": [
                {
                    "id": p.id,
                    "posted_at": p.posted_at.isoformat() if p.posted_at else None,
                    "status": p.status.value,
                    "platform_post_id": p.platform_post_id
                }
                for p in recent_posts
            ]
        }

    async def bulk_approve_content(
        self,
        account_id: int,
        post_ids: Optional[List[int]] = None
    ) -> Dict:
        """
        Bulk approve generated content and schedule posting.

        Args:
            account_id: Social account ID
            post_ids: Optional list of specific post IDs (None = all GENERATED posts)

        Returns:
            {
                "approved_count": 5,
                "posting_jobs_created": 5,
                "approved_post_ids": [...]
            }
        """
        # Build query
        query = select(ScheduledPost).where(
            ScheduledPost.account_id == account_id,
            ScheduledPost.status == PostStatus.GENERATED
        )

        if post_ids:
            query = query.where(ScheduledPost.id.in_(post_ids))

        result = await self.db.execute(query)
        posts = result.scalars().all()

        approved_count = 0
        posting_jobs_created = 0
        approved_post_ids = []

        for post in posts:
            # Approve post
            post.user_approved = True
            post.status = PostStatus.APPROVED

            # Schedule posting job
            try:
                posting_job = Job(
                    job_type=JobType.POST_CONTENT,
                    account_id=account_id,
                    status=JobStatus.QUEUED,
                    scheduled_for=post.scheduled_time,
                    duration_minutes=2,
                    use_green_window=False,  # Post at exact time
                    priority=1,
                    result={'scheduled_post_id': post.id}
                )

                self.db.add(posting_job)
                await self.db.flush()

                post.posting_job_id = posting_job.id
                posting_jobs_created += 1

            except Exception as e:
                print(f"Failed to create posting job for post {post.id}: {e}")

            approved_count += 1
            approved_post_ids.append(post.id)

        await self.db.commit()

        return {
            "approved_count": approved_count,
            "posting_jobs_created": posting_jobs_created,
            "approved_post_ids": approved_post_ids
        }

    async def reschedule_failed_posts(self, account_id: int) -> Dict:
        """
        Automatically reschedule failed posts to next optimal time.

        Args:
            account_id: Social account ID

        Returns:
            {
                "rescheduled_count": 3,
                "new_times": [...]
            }
        """
        ml_service = MLService(self.db)

        # Get failed posts
        query = select(ScheduledPost).where(
            ScheduledPost.account_id == account_id,
            ScheduledPost.status == PostStatus.FAILED
        )
        result = await self.db.execute(query)
        failed_posts = result.scalars().all()

        if not failed_posts:
            return {"rescheduled_count": 0, "new_times": []}

        # Get new optimal times
        predictions = ml_service.generate_predictions(
            account_id=account_id,
            days_ahead=7,
            store_in_db=False,
        )[: len(failed_posts)]

        rescheduled_count = 0
        new_times = []

        for post, pred in zip(failed_posts, predictions):
            new_time = self._parse_prediction_time(pred.get('posted_at') or pred.get('datetime'))

            # Update post
            post.scheduled_time = new_time
            post.status = PostStatus.APPROVED if post.user_approved else PostStatus.GENERATED

            # Create new posting job
            try:
                posting_job = Job(
                    job_type=JobType.POST_CONTENT,
                    account_id=account_id,
                    status=JobStatus.QUEUED,
                    scheduled_for=new_time,
                    duration_minutes=2,
                    use_green_window=False,
                    priority=1,
                    result={'scheduled_post_id': post.id}
                )

                self.db.add(posting_job)
                await self.db.flush()

                post.posting_job_id = posting_job.id
                rescheduled_count += 1
                new_times.append(new_time.isoformat())

            except Exception as e:
                print(f"Failed to reschedule post {post.id}: {e}")

        await self.db.commit()

        return {
            "rescheduled_count": rescheduled_count,
            "new_times": new_times
        }

    async def generate_content_batch(
        self,
        account_id: int,
        num_posts: int = 5,
        topic: Optional[str] = None
    ) -> Dict:
        """
        Generate content for multiple posts at once (useful for batch content creation).

        Args:
            account_id: Social account ID
            num_posts: Number of captions to generate
            topic: Optional topic/theme for all posts

        Returns:
            {
                "generated_count": 5,
                "captions": [...]
            }
        """
        content_service = ContentGenerationService(self.db)

        generated_captions = []

        for i in range(num_posts):
            try:
                result = await content_service.generate_caption(
                    account_id=account_id,
                    topic=topic,
                    content_type="IMAGE"
                )
                generated_captions.append({
                    "caption": result['caption'],
                    "hashtags": result['hashtags'],
                    "tokens_used": result['tokens_used']
                })
            except Exception as e:
                print(f"Failed to generate caption {i+1}: {e}")

        return {
            "generated_count": len(generated_captions),
            "captions": generated_captions
        }

    async def force_generate_content(self, post_id: int) -> Dict:
        """
        Force immediate content generation for a scheduled post.

        Bypasses carbon-aware green window scheduling and generates content
        immediately, updating the post and its associated job (if any).

        Args:
            post_id: Scheduled post ID

        Returns:
            {
                "post_id": int,
                "caption": str,
                "hashtags": [...],
                "status": "generated",
                "generation_time": 1.2,
                "job_updated": bool
            }

        Raises:
            ValueError: If post not found
        """
        # Get the scheduled post
        query = select(ScheduledPost).where(ScheduledPost.id == post_id)
        result = await self.db.execute(query)
        post = result.scalar_one_or_none()

        if not post:
            raise ValueError(f"Scheduled post {post_id} not found")

        # Generate content immediately
        content_service = ContentGenerationService(self.db)

        try:
            # First, generate a unique post idea
            post_idea = await content_service.generate_post_idea(
                account_id=post.account_id,
                content_type=post.content_type or "IMAGE"
            )

            # Then generate the caption based on that specific idea
            generation_result = await content_service.generate_caption(
                account_id=post.account_id,
                content_type=post.content_type or "IMAGE",
                topic=post_idea['topic'],
                target_sentiment=post_idea.get('suggested_sentiment', 'engaging')
            )

            # Update the post with generated content
            post.content = generation_result['caption']
            post.status = PostStatus.GENERATED
            post.generated_at = datetime.now(timezone.utc)

            # Update associated job if it exists
            job_updated = False
            if post.generation_job_id:
                job_query = select(Job).where(Job.id == post.generation_job_id)
                job_result = await self.db.execute(job_query)
                job = job_result.scalar_one_or_none()

                if job:
                    job.status = JobStatus.COMPLETED
                    job.started_at = datetime.now(timezone.utc)
                    job.completed_at = datetime.now(timezone.utc)
                    job.result = {
                        'scheduled_post_id': post_id,
                        'caption': generation_result['caption'],
                        'hashtags': generation_result['hashtags'],
                        'tokens_used': generation_result['tokens_used'],
                        'forced': True
                    }
                    job_updated = True

            await self.db.commit()

            return {
                "post_id": post_id,
                "caption": generation_result['caption'],
                "hashtags": generation_result['hashtags'],
                "status": "generated",
                "generation_time": generation_result['generation_time'],
                "tokens_used": generation_result['tokens_used'],
                "job_updated": job_updated,
                "message": "Content generated successfully and post updated"
            }

        except Exception as e:
            await self.db.rollback()
            raise Exception(f"Failed to generate content: {str(e)}")

    def _parse_prediction_time(self, value):
        """
        Normalize prediction timestamps from various formats to timezone-aware datetime.
        """
        if not value:
            raise ValueError("Prediction did not return a timestamp.")

        # Handle datetime objects
        if isinstance(value, datetime):
            # If timezone-naive, assume UTC
            if value.tzinfo is None:
                return value.replace(tzinfo=timezone.utc)
            return value

        # Handle pandas Timestamp
        if hasattr(value, "to_pydatetime"):
            dt = value.to_pydatetime()
            # If timezone-naive, assume UTC
            if dt.tzinfo is None:
                return dt.replace(tzinfo=timezone.utc)
            return dt

        # Handle string
        if isinstance(value, str):
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                return dt.replace(tzinfo=timezone.utc)
            return dt

        raise ValueError(f"Unsupported datetime value: {value}")

    async def _create_generation_job(
        self,
        scheduled_post_id: int,
        account_id: int,
        content_type: str,
        post_time: datetime,
        generate_before: datetime
    ) -> int:
        """
        Create a content generation job with green window scheduling.

        Args:
            scheduled_post_id: ID of the scheduled post
            account_id: Social account ID
            content_type: Type of content
            post_time: When the post will be published
            generate_before: Latest time to generate content

        Returns:
            Job ID
        """
        from app.services.green_window_finder import GreenWindowFinder
        from app.core.database import SessionLocal

        # Find optimal green window (GreenWindowFinder requires sync session)
        duration_minutes = 5  # Content generation is quick
        optimal_window = None

        sync_db = SessionLocal()
        try:
            window_finder = GreenWindowFinder(sync_db)
            optimal_window = window_finder.find_optimal_window(
                before_time=generate_before,
                duration_minutes=duration_minutes,
                job_type='generate_content'
            )
        finally:
            sync_db.close()

        # Set scheduled time based on green window or immediately
        now = datetime.now(timezone.utc)
        if optimal_window:
            # Ensure window times are timezone-aware
            window_start = optimal_window['window_start']
            window_end = optimal_window['window_end']
            if isinstance(window_start, datetime) and window_start.tzinfo is None:
                window_start = window_start.replace(tzinfo=timezone.utc)
            if isinstance(window_end, datetime) and window_end.tzinfo is None:
                window_end = window_end.replace(tzinfo=timezone.utc)

            scheduled_for = window_start
            optimal_start = window_start
            optimal_end = window_end
            carbon_intensity = optimal_window['carbon_intensity']
            carbon_score = optimal_window['score']
        else:
            # No green window found, schedule immediately
            scheduled_for = now
            optimal_start = None
            optimal_end = None
            carbon_intensity = None
            carbon_score = None

        # Create job
        job = Job(
            job_type=JobType.GENERATE_CONTENT,
            account_id=account_id,
            status=JobStatus.QUEUED,
            scheduled_for=scheduled_for,
            estimated_duration_minutes=duration_minutes,
            optimal_window_start=optimal_start,
            optimal_window_end=optimal_end,
            carbon_intensity=carbon_intensity,
            carbon_score=carbon_score,
            priority=3,  # Medium-high priority
            result={
                'scheduled_post_id': scheduled_post_id,
                'content_type': content_type,
                'post_time': post_time.isoformat()
            }
        )

        self.db.add(job)
        await self.db.flush()  # Get ID without committing

        return job.id

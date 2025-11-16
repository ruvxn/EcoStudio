"""
API endpoints for scheduled post management.
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import and_, select
from typing import Optional
from datetime import datetime, timedelta

from app.core.database import get_db, get_async_db
from app.api.schemas import (
    SchedulePostRequest,
    UpdateScheduledPostRequest,
    ScheduledPostResponse,
    ScheduledPostList,
)
from app.api.models.scheduled_posts import ScheduledPost, PostStatus
from app.services.content_generation_service import ContentGenerationService
from app.services.instagram_posting_service import InstagramPostingService
from app.services.eco_scheduler import EcoScheduler
from app.services.runway_image_service import RunwayImageService
from app.api.validators import validate_account_exists, validate_scheduled_post_exists

router = APIRouter()


@router.get("/scheduled", response_model=ScheduledPostList)
async def list_scheduled_posts(
    account_id: Optional[int] = None,
    status: Optional[PostStatus] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_async_db),
):
    """
    List scheduled posts with optional filtering.

    Args:
        account_id: Filter by account ID
        status: Filter by post status
        page: Page number (1-indexed)
        page_size: Number of items per page
        db: Database session

    Returns:
        List of scheduled posts with pagination info
    """
    from app.api.models.job_queue import Job, JobType, JobStatus as JStatus
    from sqlalchemy import func

    # Build query with filters
    query = select(ScheduledPost)

    if account_id:
        query = query.where(ScheduledPost.account_id == account_id)

    if status:
        query = query.where(ScheduledPost.status == status)

    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar()

    # Apply pagination
    offset = (page - 1) * page_size
    query = query.order_by(
        ScheduledPost.scheduled_time.desc()
    ).offset(offset).limit(page_size)

    result = await db.execute(query)
    posts = result.scalars().all()

    has_more = (offset + len(posts)) < total

    # Enrich posts with job scheduling info
    post_responses = []
    for post in posts:
        post_dict = ScheduledPostResponse.from_orm(post).model_dump()

        # Find related content generation job
        job_query = select(Job).where(
            Job.job_type == JobType.GENERATE_CONTENT,
            Job.status.in_([JStatus.QUEUED, JStatus.RUNNING])
        ).order_by(Job.created_at.desc()).limit(1)

        job_result = await db.execute(job_query)
        job = job_result.scalar_one_or_none()

        if job:
            post_dict['generation_scheduled_for'] = job.scheduled_for
            post_dict['green_window_start'] = job.optimal_window_start
            post_dict['green_window_end'] = job.optimal_window_end

        post_responses.append(ScheduledPostResponse(**post_dict))

    return ScheduledPostList(
        posts=post_responses,
        total=total,
        page=page,
        page_size=page_size,
        has_more=has_more,
    )


@router.post("/schedule", response_model=ScheduledPostResponse)
async def schedule_post(
    request: SchedulePostRequest,
    db: AsyncSession = Depends(get_async_db),
):
    """
    Schedule a new post for future publication.

    Args:
        request: Scheduling request with post details
        db: Database session

    Returns:
        Created scheduled post
    """
    # VALIDATION: Verify account exists
    await validate_account_exists(db, request.account_id)

    # Create scheduled post
    post = ScheduledPost(
        account_id=request.account_id,
        scheduled_time=request.scheduled_time,
        content=request.content,
        image_url=request.image_url,
        content_type=request.content_type or "IMAGE",
        status=PostStatus.PENDING,
        user_approved=False,
        auto_post_enabled=request.auto_post_enabled,
    )

    db.add(post)
    await db.commit()
    await db.refresh(post)

    # If auto-generation requested and no content provided
    if request.auto_generate and not request.content:
        content_service = ContentGenerationService(db)

        # Schedule generation 1 hour before post time (green window preference)
        generate_before = request.scheduled_time - timedelta(hours=1)

        try:
            job_id = await content_service.schedule_generation_job(
                scheduled_post_id=post.id,
                generate_before=generate_before
            )
            post.generation_job_id = job_id
            await db.commit()
        except Exception as e:
            # Log error but don't fail the scheduling
            print(f"Failed to schedule content generation: {e}")

    return ScheduledPostResponse.from_orm(post)


@router.get("/{post_id}", response_model=ScheduledPostResponse)
async def get_scheduled_post(
    post_id: int,
    db: AsyncSession = Depends(get_async_db),
):
    """
    Get details of a specific scheduled post.

    Args:
        post_id: ID of the scheduled post
        db: Database session

    Returns:
        Scheduled post details
    """
    # VALIDATION: Verify post exists (raises HTTPException if not found)
    post = await validate_scheduled_post_exists(db, post_id)

    return ScheduledPostResponse.from_orm(post)


@router.patch("/{post_id}", response_model=ScheduledPostResponse)
async def update_scheduled_post(
    post_id: int,
    request: UpdateScheduledPostRequest,
    db: AsyncSession = Depends(get_async_db),
):
    """
    Update a scheduled post (content, time, or status).

    Args:
        post_id: ID of the scheduled post
        request: Update fields
        db: Database session

    Returns:
        Updated scheduled post
    """
    # VALIDATION: Verify post exists (raises HTTPException if not found)
    post = await validate_scheduled_post_exists(db, post_id)

    # Update fields if provided
    if request.content is not None:
        post.content = request.content
        post.user_edited = True

    if request.scheduled_time is not None:
        post.scheduled_time = request.scheduled_time

    if request.image_url is not None:
        post.image_url = request.image_url

    if request.user_approved is not None:
        post.user_approved = request.user_approved

        # If approved, schedule posting job
        if request.user_approved and post.status == PostStatus.GENERATED:
            post.status = PostStatus.APPROVED

            # Schedule posting job at exact scheduled time
            try:
                from app.api.models.job_queue import Job, JobType, JobStatus

                posting_job = Job(
                    job_type=JobType.POST_CONTENT,
                    account_id=post.account_id,
                    status=JobStatus.QUEUED,
                    scheduled_for=post.scheduled_time,
                    duration_minutes=2,
                    use_green_window=False,  # Post at exact time
                    priority=1,  # High priority
                    result={'scheduled_post_id': post.id}
                )

                db.add(posting_job)
                post.posting_job_id = posting_job.id
            except Exception as e:
                print(f"Failed to schedule posting job: {e}")

    await db.commit()
    await db.refresh(post)

    return ScheduledPostResponse.from_orm(post)


@router.delete("/{post_id}")
async def cancel_scheduled_post(
    post_id: int,
    db: AsyncSession = Depends(get_async_db),
):
    """
    Cancel a scheduled post.

    Args:
        post_id: ID of the scheduled post
        db: Database session

    Returns:
        Success confirmation
    """
    posting_service = InstagramPostingService(db)

    try:
        await posting_service.cancel_scheduled_post(post_id)
        return {"success": True, "message": f"Post {post_id} cancelled successfully"}
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post("/{post_id}/regenerate", response_model=ScheduledPostResponse)
async def regenerate_content(
    post_id: int,
    topic: Optional[str] = None,
    custom_instructions: Optional[str] = None,
    db: AsyncSession = Depends(get_async_db),
):
    """
    Regenerate AI content for a scheduled post.

    Args:
        post_id: ID of the scheduled post
        topic: Optional new topic
        custom_instructions: Additional generation instructions
        db: Database session

    Returns:
        Updated scheduled post with new content
    """
    # VALIDATION: Verify post exists (raises HTTPException if not found)
    post = await validate_scheduled_post_exists(db, post_id)

    content_service = ContentGenerationService(db)

    try:
        result = await content_service.regenerate_caption(
            scheduled_post_id=post_id,
            topic=topic,
            custom_instructions=custom_instructions
        )

        # Update post with new content
        post.content = result['caption']
        post.status = PostStatus.GENERATED
        post.user_approved = False  # Reset approval

        await db.commit()
        await db.refresh(post)

        return ScheduledPostResponse.from_orm(post)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to regenerate content: {str(e)}",
        )


@router.post("/{post_id}/publish", response_model=dict)
async def publish_now(
    post_id: int,
    db: AsyncSession = Depends(get_async_db),
):
    """
    Immediately publish a scheduled post (bypass scheduled time).

    Args:
        post_id: ID of the scheduled post
        db: Database session

    Returns:
        Publication result
    """
    posting_service = InstagramPostingService(db)

    try:
        result = await posting_service.publish_scheduled_post(post_id)
        return result
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to publish post: {str(e)}",
        )


@router.post("/{post_id}/generate-image", response_model=dict)
async def generate_image_for_post(
    post_id: int,
    style: str = Query("realistic", description="Image style: realistic, artistic, minimalist, vibrant"),
    regenerate: bool = Query(False, description="Regenerate even if image exists"),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Generate an AI image for a scheduled post using Runway AI.

    This endpoint will:
    1. Get the post caption
    2. Generate an optimized image prompt
    3. Call Runway AI to generate the image
    4. Update the post with the image URL

    Args:
        post_id: ID of the scheduled post
        style: Image generation style (realistic, artistic, minimalist, vibrant)
        regenerate: Force regeneration even if image exists
        db: Database session

    Returns:
        Image generation result with URL
    """
    runway_service = RunwayImageService(db)

    try:
        result = await runway_service.generate_image_for_post(
            scheduled_post_id=post_id,
            style=style,
            regenerate=regenerate
        )
        return result
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate image: {str(e)}",
        )


@router.post("/generate-missing-images", response_model=dict)
async def generate_missing_images(
    account_id: Optional[int] = Query(None, description="Filter by account ID"),
    limit: int = Query(10, ge=1, le=50, description="Max posts to process"),
    style: str = Query("realistic", description="Image style: realistic, artistic, minimalist, vibrant"),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Batch generate images for all posts that have captions but no images.

    This is useful for:
    - Fixing posts that failed image generation
    - Adding images to posts created before image generation was enabled
    - Bulk processing multiple posts at once

    Args:
        account_id: Optional filter by account ID
        limit: Maximum number of posts to process (1-50)
        style: Image generation style
        db: Database session

    Returns:
        List of generation results
    """
    runway_service = RunwayImageService(db)

    try:
        results = await runway_service.generate_images_for_pending_posts(
            account_id=account_id,
            limit=limit,
            style=style
        )

        successful = len([r for r in results if r.get('status') == 'generated'])
        failed = len([r for r in results if r.get('status') == 'failed'])
        skipped = len([r for r in results if r.get('status') == 'skipped'])

        return {
            "total_processed": len(results),
            "successful": successful,
            "failed": failed,
            "skipped": skipped,
            "results": results
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate images: {str(e)}",
        )

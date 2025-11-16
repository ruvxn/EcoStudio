"""
API endpoints for workflow automation.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List
from pydantic import BaseModel

from app.core.database import get_async_db
from app.services.workflow_service import WorkflowService

router = APIRouter()


class WeeklyPlanRequest(BaseModel):
    account_id: int
    num_posts: int = 7
    auto_generate: bool = True
    content_type: str = "IMAGE"


class BulkApproveRequest(BaseModel):
    account_id: int
    post_ids: Optional[List[int]] = None


@router.post("/weekly-plan")
async def create_weekly_plan(
    request: WeeklyPlanRequest,
    db: AsyncSession = Depends(get_async_db),
):
    """
    Create a complete weekly posting schedule with AI content generation.

    Args:
        account_id: Social account ID
        num_posts: Number of posts to schedule (default 7)
        auto_generate: Whether to auto-generate content
        content_type: Type of content (IMAGE, VIDEO, etc.)
        db: Database session

    Returns:
        Weekly plan details with scheduled posts and generation jobs
    """
    workflow_service = WorkflowService(db)

    try:
        result = await workflow_service.create_weekly_plan(
            account_id=request.account_id,
            num_posts=request.num_posts,
            auto_generate=request.auto_generate,
            content_type=request.content_type
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
            detail=f"Failed to create weekly plan: {str(e)}",
        )


@router.get("/status/{account_id}")
async def get_workflow_status(
    account_id: int,
    db: AsyncSession = Depends(get_async_db),
):
    """
    Get overview of automation workflow status.

    Args:
        account_id: Social account ID
        db: Database session

    Returns:
        Workflow status with counts and upcoming/recent posts
    """
    workflow_service = WorkflowService(db)

    try:
        result = await workflow_service.get_workflow_status(account_id)
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get workflow status: {str(e)}",
        )


@router.post("/bulk-approve")
async def bulk_approve_content(
    request: BulkApproveRequest,
    db: AsyncSession = Depends(get_async_db),
):
    """
    Bulk approve generated content and schedule posting.

    Args:
        account_id: Social account ID
        post_ids: Optional list of specific post IDs (None = all GENERATED posts)
        db: Database session

    Returns:
        Approval results
    """
    workflow_service = WorkflowService(db)

    try:
        result = await workflow_service.bulk_approve_content(
            account_id=request.account_id,
            post_ids=request.post_ids
        )
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to bulk approve: {str(e)}",
        )


@router.post("/reschedule-failed/{account_id}")
async def reschedule_failed_posts(
    account_id: int,
    db: AsyncSession = Depends(get_async_db),
):
    """
    Automatically reschedule failed posts to next optimal times.

    Args:
        account_id: Social account ID
        db: Database session

    Returns:
        Rescheduling results
    """
    workflow_service = WorkflowService(db)

    try:
        result = await workflow_service.reschedule_failed_posts(account_id)
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to reschedule failed posts: {str(e)}",
        )


@router.post("/generate-batch")
async def generate_content_batch(
    account_id: int,
    num_posts: int = 5,
    topic: Optional[str] = None,
    db: AsyncSession = Depends(get_async_db),
):
    """
    Generate content for multiple posts at once.

    Args:
        account_id: Social account ID
        num_posts: Number of captions to generate
        topic: Optional topic/theme
        db: Database session

    Returns:
        Generated captions
    """
    workflow_service = WorkflowService(db)

    try:
        result = await workflow_service.generate_content_batch(
            account_id=account_id,
            num_posts=num_posts,
            topic=topic
        )
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate batch content: {str(e)}",
        )


@router.post("/force-generate/{post_id}")
async def force_generate_content(
    post_id: int,
    db: AsyncSession = Depends(get_async_db),
):
    """
    Force immediate content generation for a scheduled post.

    Bypasses the carbon-aware green window scheduling and triggers
    content generation immediately.

    Args:
        post_id: Scheduled post ID
        db: Database session

    Returns:
        Generation result
    """
    workflow_service = WorkflowService(db)

    try:
        result = await workflow_service.force_generate_content(post_id)
        return result
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to force generate content: {str(e)}",
        )

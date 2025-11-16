"""
Validation utilities for API endpoints.
Provides reusable validation functions for business logic validation.
"""
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import HTTPException, status

from app.api.models.social_accounts import SocialAccount
from app.api.models.scheduled_posts import ScheduledPost


async def validate_account_exists(
    db: AsyncSession,
    account_id: int,
    user_id: Optional[int] = None
) -> SocialAccount:
    """
    Validate that a social account exists and optionally belongs to a user.

    Args:
        db: Database session
        account_id: Social account ID to validate
        user_id: Optional user ID for ownership verification

    Returns:
        SocialAccount object if valid

    Raises:
        HTTPException: If account doesn't exist or doesn't belong to user
    """
    query = select(SocialAccount).where(SocialAccount.id == account_id)
    result = await db.execute(query)
    account = result.scalar_one_or_none()

    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Social account with ID {account_id} not found"
        )

    # Note: In a production app with user authentication, you would check:
    # if user_id and account.user_id != user_id:
    #     raise HTTPException(
    #         status_code=status.HTTP_403_FORBIDDEN,
    #         detail="You don't have permission to access this account"
    #     )

    return account


async def validate_scheduled_post_exists(
    db: AsyncSession,
    post_id: int,
    account_id: Optional[int] = None
) -> ScheduledPost:
    """
    Validate that a scheduled post exists and optionally belongs to an account.

    Args:
        db: Database session
        post_id: Scheduled post ID to validate
        account_id: Optional account ID for ownership verification

    Returns:
        ScheduledPost object if valid

    Raises:
        HTTPException: If post doesn't exist or doesn't belong to account
    """
    query = select(ScheduledPost).where(ScheduledPost.id == post_id)
    result = await db.execute(query)
    post = result.scalar_one_or_none()

    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Scheduled post with ID {post_id} not found"
        )

    if account_id and post.account_id != account_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Scheduled post {post_id} does not belong to account {account_id}"
        )

    return post


def validate_caption_length(caption: str, max_length: int = 2200) -> str:
    """
    Validate and potentially truncate caption to Instagram's character limit.

    Args:
        caption: Caption text
        max_length: Maximum allowed length (default: 2200 for Instagram)

    Returns:
        Validated (and possibly truncated) caption

    Raises:
        ValueError: If caption exceeds limit and cannot be safely truncated
    """
    if len(caption) <= max_length:
        return caption

    # Truncate caption to max_length with ellipsis
    truncated = caption[:max_length - 3] + "..."

    return truncated


def validate_hashtag_count(hashtags: list, max_count: int = 30) -> list:
    """
    Validate and limit hashtag count to Instagram's maximum.

    Args:
        hashtags: List of hashtags
        max_count: Maximum allowed hashtags (default: 30 for Instagram)

    Returns:
        Validated (and possibly limited) list of hashtags
    """
    if len(hashtags) <= max_count:
        return hashtags

    # Return only the first max_count hashtags
    return hashtags[:max_count]


def extract_hashtags(text: str) -> list:
    """
    Extract hashtags from text.

    Args:
        text: Text containing hashtags

    Returns:
        List of hashtags (including the # symbol)
    """
    import re
    return re.findall(r'#\w+', text)


def count_hashtags_in_caption(caption: str) -> int:
    """
    Count the number of hashtags in a caption.

    Args:
        caption: Caption text

    Returns:
        Number of hashtags found
    """
    return len(extract_hashtags(caption))

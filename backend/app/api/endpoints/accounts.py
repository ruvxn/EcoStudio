"""
API endpoints for social media account management.
Handles OAuth connections, data sync, and account statistics.
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List

from app.core.database import get_db
from app.core.config import settings
from app.api.models import SocialAccount, Post, PlatformType
from app.api.schemas import (
    SocialAccountConnect,
    SocialAccountSync,
    SocialAccountResponse,
    SocialAccountStats,
    OAuthCallbackResponse,
)
from app.services.instagram_oauth import (
    instagram_oauth_service,
    InstagramOAuthError,
)
from app.services.instagram_sync import instagram_sync_service, InstagramSyncError

router = APIRouter()


@router.get("", response_model=List[SocialAccountResponse])
async def list_accounts(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    """
    List all connected social media accounts.

    Args:
        skip: Number of records to skip (pagination)
        limit: Maximum number of records to return
        db: Database session

    Returns:
        List of connected accounts
    """
    accounts = db.query(SocialAccount).offset(skip).limit(limit).all()
    return accounts


@router.post("/connect")
async def connect_account(
    request: SocialAccountConnect,
):
    """
    Initiate OAuth flow to connect a social media account.

    Args:
        request: Connection request with platform type
        db: Database session

    Returns:
        OAuth authorization URL to redirect user to
    """
    if request.platform == PlatformType.INSTAGRAM:
        # Generate authorization URL
        auth_url = instagram_oauth_service.get_authorization_url()

        return {
            "authorization_url": auth_url,
            "message": "Redirect user to this URL to begin OAuth flow",
        }
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Platform {request.platform} not yet supported",
        )


@router.get("/auth/instagram/callback", response_model=OAuthCallbackResponse)
async def instagram_oauth_callback(
    code: str = Query(..., description="Authorization code from Instagram"),
    db: Session = Depends(get_db),
):
    """
    Handle OAuth callback from Instagram.

    This endpoint is called by Instagram after user approves permissions.

    Args:
        code: Authorization code from Instagram
        db: Database session

    Returns:
        Success response with account ID
    """
    try:
        # Exchange code for access token
        token_data = await instagram_oauth_service.exchange_code_for_token(code)

        # Fetch user profile
        profile = await instagram_oauth_service.get_user_profile(
            token_data["access_token"]
        )

        # Save account
        account = await instagram_oauth_service.save_account(
            db=db,
            access_token=token_data["access_token"],
            user_id=profile["id"],
            expires_in=token_data["expires_in"],
            username=profile.get("username"),
        )

        return OAuthCallbackResponse(
            success=True,
            message=f"Successfully connected Instagram account @{profile.get('username')}",
            account_id=account.id,
            redirect_to=f"{settings.FRONTEND_URL}/dashboard?connected=true",
        )

    except InstagramOAuthError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"OAuth failed: {str(e)}",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected error: {str(e)}",
        )


@router.get("/{account_id}", response_model=SocialAccountResponse)
async def get_account(
    account_id: int,
    db: Session = Depends(get_db),
):
    """
    Get details of a specific social media account.

    Args:
        account_id: ID of the account
        db: Database session

    Returns:
        Account details
    """
    account = db.query(SocialAccount).filter(SocialAccount.id == account_id).first()

    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Account not found",
        )

    return account


@router.post("/{account_id}/sync")
async def sync_account_data(
    account_id: int,
    request: SocialAccountSync,
    db: Session = Depends(get_db),
):
    """
    Sync historical posts from social media platform.

    Args:
        account_id: ID of the account to sync
        request: Sync configuration (days to sync, force refresh)
        db: Database session

    Returns:
        Sync job status
    """
    # Get account
    account = db.query(SocialAccount).filter(SocialAccount.id == account_id).first()

    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Account not found",
        )

    if account.platform != PlatformType.INSTAGRAM:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Sync not yet supported for platform {account.platform}",
        )

    try:
        # Perform sync
        result = await instagram_sync_service.sync_posts(
            db=db,
            account=account,
            days=request.days,
            force_refresh=request.force_refresh,
        )

        return {
            "success": True,
            "message": f"Successfully synced {result['posts_fetched']} posts",
            **result,
        }

    except InstagramSyncError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Sync failed: {str(e)}",
        )


@router.get("/{account_id}/stats", response_model=SocialAccountStats)
async def get_account_stats(
    account_id: int,
    db: Session = Depends(get_db),
):
    """
    Get engagement statistics for an account.

    Args:
        account_id: ID of the account
        db: Database session

    Returns:
        Account statistics including best posting times
    """
    # Get account
    account = db.query(SocialAccount).filter(SocialAccount.id == account_id).first()

    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Account not found",
        )

    # Get all posts for this account
    posts = db.query(Post).filter(Post.account_id == account_id).all()

    if not posts:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No posts found for this account. Run sync first.",
        )

    # Calculate statistics
    total_posts = len(posts)
    total_likes = sum(p.likes for p in posts)
    total_comments = sum(p.comments for p in posts)
    total_shares = sum(p.shares for p in posts)
    avg_engagement = sum(p.engagement_score for p in posts if p.engagement_score) / total_posts

    # Find best posting hour
    hour_engagement = {}
    for post in posts:
        hour = post.post_time.hour
        if hour not in hour_engagement:
            hour_engagement[hour] = []
        if post.engagement_score:
            hour_engagement[hour].append(post.engagement_score)

    best_hour = max(
        hour_engagement.items(),
        key=lambda x: sum(x[1]) / len(x[1]) if x[1] else 0
    )[0]

    # Find best posting day
    day_engagement = {}
    for post in posts:
        day = post.post_time.weekday()
        if day not in day_engagement:
            day_engagement[day] = []
        if post.engagement_score:
            day_engagement[day].append(post.engagement_score)

    best_day = max(
        day_engagement.items(),
        key=lambda x: sum(x[1]) / len(x[1]) if x[1] else 0
    )[0]

    # Get date range
    date_range_start = min(p.post_time for p in posts)
    date_range_end = max(p.post_time for p in posts)

    return SocialAccountStats(
        total_posts=total_posts,
        avg_engagement=avg_engagement,
        best_posting_hour=best_hour,
        best_posting_day=best_day,
        total_likes=total_likes,
        total_comments=total_comments,
        total_shares=total_shares,
        date_range_start=date_range_start,
        date_range_end=date_range_end,
    )


@router.delete("/{account_id}")
async def disconnect_account(
    account_id: int,
    db: Session = Depends(get_db),
):
    """
    Disconnect a social media account and delete all associated data.

    Args:
        account_id: ID of the account to disconnect
        db: Database session

    Returns:
        Success confirmation
    """
    account = db.query(SocialAccount).filter(SocialAccount.id == account_id).first()

    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Account not found",
        )

    # Delete account (cascade will delete related posts, predictions, etc.)
    db.delete(account)
    db.commit()

    return {
        "success": True,
        "message": f"Successfully disconnected {account.platform} account",
    }

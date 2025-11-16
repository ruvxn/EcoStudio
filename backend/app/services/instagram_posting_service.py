"""
Instagram posting automation service.
Handles media upload, container creation, and publishing via Instagram Graph API.
"""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, Optional, Union
import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.api.models.scheduled_posts import ScheduledPost, PostStatus
from app.api.models.social_accounts import SocialAccount


class InstagramPostingService:
    """Service for publishing content to Instagram."""

    def __init__(self, db: Union[Session, AsyncSession]):
        """
        Initialize Instagram posting service.

        Args:
            db: Database session (sync or async)
        """
        self.db = db
        self.graph_api_url = "https://graph.facebook.com/v18.0"
        self.timeout = 60.0  # seconds

    async def post_to_instagram(
        self,
        account_id: int,
        caption: str,
        image_url: str,
        media_type: str = "IMAGE"
    ) -> Dict:
        """
        Publish content to Instagram via Graph API.

        Args:
            account_id: Database social account ID
            caption: Post caption text
            image_url: Publicly accessible image URL
            media_type: IMAGE, VIDEO, CAROUSEL

        Returns:
            {
                "instagram_post_id": "123456789",
                "permalink": "https://instagram.com/p/...",
                "posted_at": "2024-01-15T10:30:00"
            }

        Raises:
            ValueError: If account not found or invalid credentials
            Exception: For API errors
        """
        # Get account credentials
        query = select(SocialAccount).where(SocialAccount.id == account_id)
        result = await self.db.execute(query)
        account = result.scalar_one_or_none()

        if not account:
            raise ValueError(f"Account {account_id} not found")

        if not account.access_token or not account.instagram_user_id:
            raise ValueError(f"Account {account_id} missing credentials")

        # Check token expiry
        await self._ensure_valid_token(account)

        instagram_user_id = account.instagram_user_id
        access_token = account.access_token

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                # Step 1: Create media container
                container_id = await self._create_media_container(
                    client, instagram_user_id, access_token,
                    image_url, caption, media_type
                )

                # Step 2: Wait for container to be ready (Instagram processes the media)
                await asyncio.sleep(2)

                # Step 3: Publish media
                media_id = await self._publish_media(
                    client, instagram_user_id, access_token, container_id
                )

                # Step 4: Get permalink
                permalink = await self._get_media_permalink(
                    client, media_id, access_token
                )

                return {
                    "instagram_post_id": media_id,
                    "permalink": permalink,
                    "posted_at": datetime.utcnow().isoformat()
                }

            except httpx.HTTPStatusError as e:
                error_msg = f"Instagram API error: {e.response.status_code} - {e.response.text}"
                raise Exception(error_msg)
            except Exception as e:
                raise Exception(f"Failed to post to Instagram: {str(e)}")

    async def _create_media_container(
        self,
        client: httpx.AsyncClient,
        instagram_user_id: str,
        access_token: str,
        image_url: str,
        caption: str,
        media_type: str
    ) -> str:
        """
        Create media container on Instagram.

        Returns:
            container_id (creation_id)
        """
        container_url = f"{self.graph_api_url}/{instagram_user_id}/media"

        # Build parameters based on media type
        params = {
            "caption": caption,
            "access_token": access_token
        }

        if media_type == "VIDEO":
            params["media_type"] = "VIDEO"
            params["video_url"] = image_url
        else:  # IMAGE (default)
            params["image_url"] = image_url

        response = await client.post(container_url, data=params)
        response.raise_for_status()

        data = response.json()
        return data['id']

    async def _publish_media(
        self,
        client: httpx.AsyncClient,
        instagram_user_id: str,
        access_token: str,
        creation_id: str
    ) -> str:
        """
        Publish media container to Instagram feed.

        Returns:
            media_id (Instagram post ID)
        """
        publish_url = f"{self.graph_api_url}/{instagram_user_id}/media_publish"

        params = {
            "creation_id": creation_id,
            "access_token": access_token
        }

        response = await client.post(publish_url, data=params)
        response.raise_for_status()

        data = response.json()
        return data['id']

    async def _get_media_permalink(
        self,
        client: httpx.AsyncClient,
        media_id: str,
        access_token: str
    ) -> str:
        """
        Get permalink URL for published media.

        Returns:
            permalink URL
        """
        media_url = f"{self.graph_api_url}/{media_id}"

        params = {
            "fields": "permalink",
            "access_token": access_token
        }

        response = await client.get(media_url, params=params)
        response.raise_for_status()

        data = response.json()
        return data.get('permalink', '')

    async def _ensure_valid_token(self, account: SocialAccount):
        """
        Check token expiry and refresh if needed.

        Args:
            account: Social account object
        """
        if not account.token_expires_at:
            return

        # Refresh if less than 7 days remaining
        days_until_expiry = (account.token_expires_at - datetime.utcnow()).days

        if days_until_expiry < 7:
            from app.services.instagram_oauth import InstagramOAuthService

            oauth_service = InstagramOAuthService(self.db)
            try:
                await oauth_service.refresh_access_token(account.id)
                # Refresh account object
                await self.db.refresh(account)
            except Exception as e:
                raise Exception(f"Failed to refresh access token: {str(e)}")

    async def publish_scheduled_post(self, scheduled_post_id: int) -> Dict:
        """
        Publish a scheduled post to Instagram.

        Args:
            scheduled_post_id: ID of scheduled post

        Returns:
            Publication result dictionary

        Raises:
            ValueError: If post not found or not approved
            Exception: For posting errors
        """
        # Get scheduled post
        query = select(ScheduledPost).where(ScheduledPost.id == scheduled_post_id)
        result = await self.db.execute(query)
        post = result.scalar_one_or_none()

        if not post:
            raise ValueError(f"Scheduled post {scheduled_post_id} not found")

        if not post.user_approved:
            raise ValueError(f"Post {scheduled_post_id} not approved by user")

        if not post.content:
            raise ValueError(f"Post {scheduled_post_id} has no content")

        if not post.image_url:
            raise ValueError(f"Post {scheduled_post_id} has no image URL")

        # Post to Instagram
        try:
            result = await self.post_to_instagram(
                account_id=post.account_id,
                caption=post.content,
                image_url=post.image_url,
                media_type=post.content_type or "IMAGE"
            )

            # Update scheduled post status
            post.status = PostStatus.POSTED
            post.posted_at = datetime.utcnow()
            post.platform_post_id = result['instagram_post_id']

            await self.db.commit()
            await self.db.refresh(post)

            return {
                "success": True,
                "scheduled_post_id": scheduled_post_id,
                "instagram_post_id": result['instagram_post_id'],
                "permalink": result['permalink'],
                "posted_at": result['posted_at']
            }

        except Exception as e:
            # Mark as failed
            post.status = PostStatus.FAILED
            await self.db.commit()

            raise Exception(f"Failed to publish post {scheduled_post_id}: {str(e)}")

    async def cancel_scheduled_post(self, scheduled_post_id: int):
        """
        Cancel a scheduled post by deleting it.

        Args:
            scheduled_post_id: ID of scheduled post to cancel

        Raises:
            ValueError: If post not found or already posted
        """
        query = select(ScheduledPost).where(ScheduledPost.id == scheduled_post_id)
        result = await self.db.execute(query)
        post = result.scalar_one_or_none()

        if not post:
            raise ValueError(f"Scheduled post {scheduled_post_id} not found")

        if post.status == PostStatus.POSTED:
            raise ValueError(f"Cannot cancel post {scheduled_post_id} - already posted")

        await self.db.delete(post)
        await self.db.commit()

    async def retry_failed_post(self, scheduled_post_id: int) -> Dict:
        """
        Retry a failed post.

        Args:
            scheduled_post_id: ID of failed post

        Returns:
            Publication result dictionary
        """
        query = select(ScheduledPost).where(ScheduledPost.id == scheduled_post_id)
        result = await self.db.execute(query)
        post = result.scalar_one_or_none()

        if not post:
            raise ValueError(f"Scheduled post {scheduled_post_id} not found")

        if post.status != PostStatus.FAILED:
            raise ValueError(f"Post {scheduled_post_id} is not in FAILED status")

        # Reset status and retry
        post.status = PostStatus.APPROVED
        await self.db.commit()

        return await self.publish_scheduled_post(scheduled_post_id)

    async def get_post_insights(
        self,
        account_id: int,
        instagram_post_id: str
    ) -> Dict:
        """
        Get engagement insights for a published post.

        Args:
            account_id: Database social account ID
            instagram_post_id: Instagram media ID

        Returns:
            {
                "likes": 150,
                "comments": 20,
                "reach": 500,
                "engagement_score": 0.34
            }
        """
        # Get account credentials
        query = select(SocialAccount).where(SocialAccount.id == account_id)
        result = await self.db.execute(query)
        account = result.scalar_one_or_none()

        if not account:
            raise ValueError(f"Account {account_id} not found")

        access_token = account.access_token
        media_url = f"{self.graph_api_url}/{instagram_post_id}"

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                # Get insights
                params = {
                    "fields": "like_count,comments_count,insights.metric(reach,impressions,engagement)",
                    "access_token": access_token
                }

                response = await client.get(media_url, params=params)
                response.raise_for_status()

                data = response.json()

                likes = data.get('like_count', 0)
                comments = data.get('comments_count', 0)

                # Extract insights if available
                insights = data.get('insights', {}).get('data', [])
                reach = 0
                impressions = 0

                for insight in insights:
                    if insight['name'] == 'reach':
                        reach = insight['values'][0]['value']
                    elif insight['name'] == 'impressions':
                        impressions = insight['values'][0]['value']

                # Calculate engagement score
                engagement_score = (likes + comments) / reach if reach > 0 else 0

                return {
                    "likes": likes,
                    "comments": comments,
                    "reach": reach,
                    "impressions": impressions,
                    "engagement_score": round(engagement_score, 4)
                }

            except httpx.HTTPStatusError as e:
                # Insights might not be available immediately
                if e.response.status_code == 400:
                    return {
                        "likes": 0,
                        "comments": 0,
                        "reach": 0,
                        "impressions": 0,
                        "engagement_score": 0.0,
                        "error": "Insights not yet available"
                    }
                raise

    async def validate_image_url(self, image_url: str) -> bool:
        """
        Validate that image URL is accessible.

        Args:
            image_url: URL to validate

        Returns:
            True if accessible, False otherwise
        """
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                response = await client.head(image_url)
                return response.status_code == 200
            except:
                return False

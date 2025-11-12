"""
Instagram data synchronization service for fetching historical posts.

Fetches posts from Instagram Graph API and stores them in the database
for ML model training.
"""
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import httpx
import re
from sqlalchemy.orm import Session

from app.core.config import settings
from app.api.models import SocialAccount, Post, ContentType
from app.services.instagram_oauth import instagram_oauth_service, InstagramOAuthError


class InstagramSyncError(Exception):
    """Raised when Instagram data sync fails."""
    pass


class InstagramSyncService:
    """
    Service for syncing Instagram post data.

    Responsibilities:
    - Fetch media (posts) from Instagram Graph API
    - Parse engagement metrics (likes, comments, etc.)
    - Calculate engagement scores
    - Store posts in database
    - Handle pagination for large datasets
    """

    def __init__(self):
        self.graph_api_url = "https://graph.instagram.com"
        self.rate_limit_delay = 1  # Seconds between requests

    async def sync_posts(
        self,
        db: Session,
        account: SocialAccount,
        days: int = 90,
        force_refresh: bool = False,
    ) -> Dict[str, any]:
        """
        Sync posts from Instagram for the specified time period.

        Args:
            db: Database session
            account: SocialAccount to sync
            days: Number of days to sync (1-365)
            force_refresh: If True, re-fetch even if recently synced

        Returns:
            Dictionary with sync results:
            - posts_fetched: Number of posts retrieved
            - posts_new: Number of new posts added
            - posts_updated: Number of existing posts updated
            - oldest_post: Timestamp of oldest post
            - newest_post: Timestamp of newest post

        Raises:
            InstagramSyncError: If sync fails
        """
        # Check if we should skip (recently synced)
        if not force_refresh and account.last_sync_at:
            hours_since_sync = (
                datetime.utcnow() - account.last_sync_at
            ).total_seconds() / 3600
            if hours_since_sync < 6:  # Don't sync more than once every 6 hours
                raise InstagramSyncError(
                    f"Account synced {hours_since_sync:.1f} hours ago. "
                    f"Use force_refresh=True to override."
                )

        # Ensure valid access token
        access_token = await instagram_oauth_service.ensure_valid_token(
            db, account
        )

        # Fetch posts from Instagram
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        posts_data = await self._fetch_all_media(access_token, cutoff_date)

        # Process and store posts
        posts_new = 0
        posts_updated = 0
        oldest_post = None
        newest_post = None

        for post_data in posts_data:
            post_time = datetime.fromisoformat(
                post_data["timestamp"].replace("Z", "+00:00")
            )

            # Track date range
            if not oldest_post or post_time < oldest_post:
                oldest_post = post_time
            if not newest_post or post_time > newest_post:
                newest_post = post_time

            # Check if post already exists
            existing = (
                db.query(Post)
                .filter(Post.post_id == post_data["id"])
                .first()
            )

            if existing:
                # Update existing post
                self._update_post_from_data(
                    existing, post_data, account.follower_count or 1000
                )
                posts_updated += 1
            else:
                # Create new post
                post = self._create_post_from_data(
                    post_data, account.id, account.follower_count or 1000
                )
                db.add(post)
                posts_new += 1

        # Update account sync timestamp
        account.last_sync_at = datetime.utcnow()
        db.commit()

        return {
            "posts_fetched": len(posts_data),
            "posts_new": posts_new,
            "posts_updated": posts_updated,
            "oldest_post": oldest_post,
            "newest_post": newest_post,
        }

    async def _fetch_all_media(
        self, access_token: str, cutoff_date: datetime
    ) -> List[Dict]:
        """
        Fetch all media items from Instagram with pagination.

        Instagram API returns results in pages (default 25 items per page).
        We fetch all pages until we reach the cutoff date or run out of posts.

        Args:
            access_token: Valid Instagram access token
            cutoff_date: Stop fetching posts older than this date

        Returns:
            List of media items (posts)
        """
        all_media = []
        url = f"{self.graph_api_url}/me/media"
        params = {
            "fields": "id,caption,media_type,media_url,thumbnail_url,permalink,"
            "timestamp,like_count,comments_count,username",
            "access_token": access_token,
            "limit": 100,  # Max items per request
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            while url:
                try:
                    response = await client.get(url, params=params if params else None)
                    response.raise_for_status()
                    data = response.json()

                    media_items = data.get("data", [])

                    # Filter posts by date
                    for item in media_items:
                        post_time = datetime.fromisoformat(
                            item["timestamp"].replace("Z", "+00:00")
                        )
                        if post_time >= cutoff_date:
                            all_media.append(item)
                        else:
                            # Reached cutoff date, stop fetching
                            return all_media

                    # Check for next page
                    paging = data.get("paging", {})
                    url = paging.get("next")
                    params = None  # Next URL already includes params

                    # Respect rate limits
                    if url:
                        await asyncio.sleep(self.rate_limit_delay)

                except httpx.HTTPStatusError as e:
                    raise InstagramSyncError(
                        f"Failed to fetch media: {e.response.text}"
                    )

        return all_media

    def _create_post_from_data(
        self, post_data: Dict, account_id: int, follower_count: int
    ) -> Post:
        """
        Create Post object from Instagram API data.

        Args:
            post_data: Raw data from Instagram API
            account_id: ID of the SocialAccount
            follower_count: Current follower count for engagement calculation

        Returns:
            Post instance (not yet committed)
        """
        caption = post_data.get("caption", "")

        post = Post(
            account_id=account_id,
            post_id=post_data["id"],
            content=caption,
            post_time=datetime.fromisoformat(
                post_data["timestamp"].replace("Z", "+00:00")
            ),
            likes=post_data.get("like_count", 0),
            comments=post_data.get("comments_count", 0),
            shares=0,  # Instagram API doesn't provide share count
            content_type=self._map_content_type(post_data.get("media_type")),
            caption_length=len(caption) if caption else 0,
            hashtag_count=self._count_hashtags(caption),
            has_emoji=1 if self._contains_emoji(caption) else 0,
            media_url=post_data.get("media_url") or post_data.get("thumbnail_url"),
        )

        # Calculate engagement score
        post.engagement_score = post.calculate_engagement_score(follower_count)

        return post

    def _update_post_from_data(
        self, post: Post, post_data: Dict, follower_count: int
    ):
        """
        Update existing Post with fresh data from Instagram API.

        Updates engagement metrics which may have changed since last sync.

        Args:
            post: Existing Post instance
            post_data: Fresh data from Instagram API
            follower_count: Current follower count
        """
        post.likes = post_data.get("like_count", 0)
        post.comments = post_data.get("comments_count", 0)
        post.engagement_score = post.calculate_engagement_score(follower_count)
        post.updated_at = datetime.utcnow()

    def _map_content_type(self, media_type: str) -> ContentType:
        """
        Map Instagram media type to our ContentType enum.

        Args:
            media_type: Instagram media type (IMAGE, VIDEO, CAROUSEL_ALBUM)

        Returns:
            ContentType enum value
        """
        mapping = {
            "IMAGE": ContentType.IMAGE,
            "VIDEO": ContentType.VIDEO,
            "CAROUSEL_ALBUM": ContentType.CAROUSEL,
        }
        return mapping.get(media_type, ContentType.IMAGE)

    def _count_hashtags(self, text: Optional[str]) -> int:
        """
        Count number of hashtags in text.

        Args:
            text: Caption text

        Returns:
            Number of hashtags found
        """
        if not text:
            return 0
        return len(re.findall(r"#\w+", text))

    def _contains_emoji(self, text: Optional[str]) -> bool:
        """
        Check if text contains emoji characters.

        Uses Unicode ranges for emoji detection.

        Args:
            text: Caption text

        Returns:
            True if text contains emojis
        """
        if not text:
            return False

        # Unicode ranges for emojis
        emoji_pattern = re.compile(
            "["
            "\U0001F600-\U0001F64F"  # emoticons
            "\U0001F300-\U0001F5FF"  # symbols & pictographs
            "\U0001F680-\U0001F6FF"  # transport & map symbols
            "\U0001F1E0-\U0001F1FF"  # flags
            "\U00002702-\U000027B0"
            "\U000024C2-\U0001F251"
            "]+",
            flags=re.UNICODE,
        )
        return bool(emoji_pattern.search(text))

    async def get_follower_count(
        self, db: Session, account: SocialAccount
    ) -> int:
        """
        Fetch current follower count for an Instagram account.

        Note: Instagram Basic Display API doesn't provide follower count.
        For business/creator accounts, use Instagram Graph API.
        For now, we'll return a placeholder or stored value.

        Args:
            db: Database session
            account: SocialAccount instance

        Returns:
            Follower count (or default 1000 if unavailable)
        """
        # TODO: Implement proper follower count fetch for business accounts
        # For now, return stored value or default
        return account.follower_count or 1000


# Import asyncio for sleep
import asyncio

# Singleton instance
instagram_sync_service = InstagramSyncService()

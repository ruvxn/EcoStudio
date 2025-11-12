"""
Data loader for extracting posts from database for ML training
"""
import pandas as pd
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Optional, Dict, Any
from datetime import datetime, timedelta

from app.api.models.posts import Post
from app.api.models.social_accounts import SocialAccount
from ..config import MIN_POSTS_REQUIRED


class DataLoader:
    """
    Loads post data from database for ML training
    """

    def __init__(self, db: Session):
        """
        Initialize data loader

        Args:
            db: Database session
        """
        self.db = db

    def load_posts_for_account(
        self,
        account_id: int,
        min_posts: int = MIN_POSTS_REQUIRED,
        max_age_days: Optional[int] = None,
    ) -> pd.DataFrame:
        """
        Load posts for a specific account

        Args:
            account_id: Social account ID
            min_posts: Minimum number of posts required
            max_age_days: Only include posts from the last N days (optional)

        Returns:
            DataFrame with post data

        Raises:
            ValueError: If insufficient posts found
        """
        # Build query
        query = self.db.query(Post).filter(
            Post.account_id == account_id,
            Post.engagement_score.isnot(None),  # Only posts with engagement data
        )

        # Filter by age if specified
        if max_age_days:
            cutoff_date = datetime.utcnow() - timedelta(days=max_age_days)
            query = query.filter(Post.post_time >= cutoff_date)

        # Order by post time
        query = query.order_by(Post.post_time.desc())

        # Execute query
        posts = query.all()

        # Check minimum posts
        if len(posts) < min_posts:
            raise ValueError(
                f"Insufficient data: Found {len(posts)} posts, minimum required is {min_posts}"
            )

        # Convert to DataFrame
        df = self._posts_to_dataframe(posts)

        return df

    def _posts_to_dataframe(self, posts: list) -> pd.DataFrame:
        """
        Convert list of Post objects to DataFrame

        Args:
            posts: List of Post model instances

        Returns:
            DataFrame with post data
        """
        data = []

        for post in posts:
            # Map ContentType enum to string
            content_type = post.content_type.value if hasattr(post.content_type, 'value') else str(post.content_type)

            # Map field names to match our feature engineering expectations
            data.append({
                "post_id": post.post_id,
                "posted_at": post.post_time,  # Note: post_time -> posted_at
                "content_type": content_type.lower(),
                "caption": post.content or "",  # Note: content -> caption
                "likes": post.likes or 0,
                "comments": post.comments or 0,
                "shares": post.shares or 0,
                "views": post.views or 0,
                "saves": post.saves or 0,
                "engagement_score": post.engagement_score,
                # Copy pre-calculated features if available
                "caption_length": post.caption_length,
                "hashtag_count": post.hashtag_count or 0,
                "has_emoji": post.has_emoji or 0,
            })

        df = pd.DataFrame(data)

        # Ensure posted_at is datetime
        df["posted_at"] = pd.to_datetime(df["posted_at"])

        # Sort by time
        df = df.sort_values("posted_at").reset_index(drop=True)

        return df

    def get_account_stats(self, account_id: int) -> Dict[str, Any]:
        """
        Get statistics about account's post data

        Args:
            account_id: Social account ID

        Returns:
            Dictionary with account statistics
        """
        # Get post count
        post_count = self.db.query(func.count(Post.id)).filter(
            Post.account_id == account_id,
            Post.engagement_score.isnot(None),
        ).scalar()

        # Get date range
        date_range = self.db.query(
            func.min(Post.post_time),
            func.max(Post.post_time),
        ).filter(
            Post.account_id == account_id,
            Post.engagement_score.isnot(None),
        ).first()

        # Get average engagement
        avg_engagement = self.db.query(
            func.avg(Post.engagement_score)
        ).filter(
            Post.account_id == account_id,
            Post.engagement_score.isnot(None),
        ).scalar()

        # Get content type distribution
        content_type_dist = {}
        content_types = self.db.query(
            Post.content_type,
            func.count(Post.id)
        ).filter(
            Post.account_id == account_id,
            Post.engagement_score.isnot(None),
        ).group_by(Post.content_type).all()

        for content_type, count in content_types:
            type_str = content_type.value if hasattr(content_type, 'value') else str(content_type)
            content_type_dist[type_str] = count

        return {
            "post_count": post_count or 0,
            "date_range": {
                "start": date_range[0].isoformat() if date_range[0] else None,
                "end": date_range[1].isoformat() if date_range[1] else None,
            },
            "avg_engagement": float(avg_engagement) if avg_engagement else 0.0,
            "content_type_distribution": content_type_dist,
            "has_sufficient_data": (post_count or 0) >= MIN_POSTS_REQUIRED,
        }

    def get_historical_averages(
        self,
        account_id: int,
    ) -> Dict[str, Any]:
        """
        Calculate historical averages for advanced features

        Args:
            account_id: Social account ID

        Returns:
            Dictionary with historical averages
        """
        posts_df = self.load_posts_for_account(account_id)

        # Account average
        account_avg = posts_df["engagement_score"].mean()

        # Content type averages
        content_type_avg = posts_df.groupby("content_type")["engagement_score"].mean().to_dict()

        # Hour averages (extract hour first)
        posts_df["hour"] = pd.to_datetime(posts_df["posted_at"]).dt.hour
        hour_avg = posts_df.groupby("hour")["engagement_score"].mean().to_dict()

        # Day of week averages
        posts_df["day_of_week"] = pd.to_datetime(posts_df["posted_at"]).dt.dayofweek
        day_avg = posts_df.groupby("day_of_week")["engagement_score"].mean().to_dict()

        # Recent trend (last 10 posts)
        recent_trend = posts_df.tail(10)["engagement_score"].mean()

        return {
            "account_avg_engagement": float(account_avg),
            "content_type_avg_engagement": {k: float(v) for k, v in content_type_avg.items()},
            "hour_avg_engagement": {int(k): float(v) for k, v in hour_avg.items()},
            "day_avg_engagement": {int(k): float(v) for k, v in day_avg.items()},
            "recent_trend": float(recent_trend),
        }

    def check_data_quality(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Check data quality and return warnings/issues

        Args:
            df: DataFrame with post data

        Returns:
            Dictionary with quality check results
        """
        issues = []
        warnings = []

        # Check for missing values
        missing_engagement = df["engagement_score"].isna().sum()
        if missing_engagement > 0:
            issues.append(f"{missing_engagement} posts missing engagement scores")

        # Check for zero variance in engagement
        if df["engagement_score"].std() == 0:
            warnings.append("All posts have same engagement score (zero variance)")

        # Check date range
        date_range = (df["posted_at"].max() - df["posted_at"].min()).days
        if date_range < 7:
            warnings.append(f"Short date range: only {date_range} days of data")

        # Check content type diversity
        content_types = df["content_type"].nunique()
        if content_types == 1:
            warnings.append("All posts are same content type")

        # Check for duplicates
        duplicates = df["post_id"].duplicated().sum()
        if duplicates > 0:
            issues.append(f"{duplicates} duplicate posts found")

        return {
            "is_valid": len(issues) == 0,
            "issues": issues,
            "warnings": warnings,
            "post_count": len(df),
            "date_range_days": date_range,
            "content_types": content_types,
        }

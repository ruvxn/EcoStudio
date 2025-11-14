"""
Tests for data loader
"""
import pytest
from datetime import datetime, timedelta

from app.ml.training.data_loader import DataLoader
from app.ml.config import MIN_POSTS_REQUIRED


class TestDataLoader:
    """Test DataLoader class"""

    def test_initialization(self, test_db):
        """Test DataLoader initialization"""
        loader = DataLoader(test_db)
        assert loader.db == test_db

    def test_load_posts_with_sufficient_data(self, test_db, sample_posts_medium):
        """Test loading posts with sufficient data"""
        loader = DataLoader(test_db)
        account_id = sample_posts_medium[0].account_id

        df = loader.load_posts_for_account(account_id)

        assert len(df) >= MIN_POSTS_REQUIRED
        assert "posted_at" in df.columns
        assert "engagement_score" in df.columns
        assert "content_type" in df.columns

    def test_load_posts_insufficient_data_raises_error(self, test_db, sample_account):
        """Test that insufficient data raises ValueError"""
        loader = DataLoader(test_db)

        # Don't create enough posts
        with pytest.raises(ValueError, match="Insufficient data"):
            loader.load_posts_for_account(sample_account.id)

    def test_load_posts_with_max_age_filter(self, test_db, sample_posts_large):
        """Test loading posts with age filter"""
        loader = DataLoader(test_db)
        account_id = sample_posts_large[0].account_id

        # Load only recent posts (last 30 days)
        df = loader.load_posts_for_account(account_id, max_age_days=30)

        # Check that all posts are within the time range
        oldest_post = df["posted_at"].min()
        days_old = (datetime.utcnow() - oldest_post).days

        assert days_old <= 35  # Some buffer for test execution time

    def test_posts_to_dataframe_mapping(self, test_db, sample_posts_small):
        """Test that Post model fields are correctly mapped to DataFrame"""
        loader = DataLoader(test_db)
        posts = sample_posts_small[:5]

        df = loader._posts_to_dataframe(posts)

        # Check column mappings
        assert "posted_at" in df.columns  # post_time -> posted_at
        assert "caption" in df.columns     # content -> caption
        assert df["caption"].iloc[0] == posts[0].content

    def test_get_account_stats(self, test_db, sample_posts_medium):
        """Test getting account statistics"""
        loader = DataLoader(test_db)
        account_id = sample_posts_medium[0].account_id

        stats = loader.get_account_stats(account_id)

        assert "post_count" in stats
        assert "date_range" in stats
        assert "avg_engagement" in stats
        assert "content_type_distribution" in stats
        assert "has_sufficient_data" in stats

        assert stats["post_count"] >= MIN_POSTS_REQUIRED
        assert stats["has_sufficient_data"] is True

    def test_get_account_stats_insufficient_data(self, test_db, sample_account):
        """Test stats with insufficient data"""
        loader = DataLoader(test_db)

        stats = loader.get_account_stats(sample_account.id)

        assert stats["post_count"] == 0
        assert stats["has_sufficient_data"] is False

    def test_get_historical_averages(self, test_db, sample_posts_medium):
        """Test calculation of historical averages"""
        loader = DataLoader(test_db)
        account_id = sample_posts_medium[0].account_id

        averages = loader.get_historical_averages(account_id)

        assert "account_avg_engagement" in averages
        assert "content_type_avg_engagement" in averages
        assert "hour_avg_engagement" in averages
        assert "day_avg_engagement" in averages
        assert "recent_trend" in averages

        # Check types
        assert isinstance(averages["account_avg_engagement"], float)
        assert isinstance(averages["content_type_avg_engagement"], dict)

    def test_check_data_quality(self, test_db, sample_posts_medium):
        """Test data quality checking"""
        loader = DataLoader(test_db)
        account_id = sample_posts_medium[0].account_id

        df = loader.load_posts_for_account(account_id)
        quality = loader.check_data_quality(df)

        assert "is_valid" in quality
        assert "issues" in quality
        assert "warnings" in quality
        assert "post_count" in quality

        # Should be valid with sample data
        assert quality["is_valid"] is True

    def test_dataframe_sorted_by_time(self, test_db, sample_posts_medium):
        """Test that returned DataFrame is sorted by time"""
        loader = DataLoader(test_db)
        account_id = sample_posts_medium[0].account_id

        df = loader.load_posts_for_account(account_id)

        # Check that times are in ascending order
        assert (df["posted_at"].diff().dropna() >= timedelta(0)).all()

"""
Pytest configuration and fixtures for ML tests
"""
import os
import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from typing import Generator
from dotenv import load_dotenv
from pathlib import Path

# Load test environment variables
test_env = Path(__file__).parent.parent / ".env.test"
if test_env.exists():
    load_dotenv(test_env)

from app.core.database import Base
from app.api.models.posts import Post, ContentType
from app.api.models.social_accounts import SocialAccount


# Database fixtures
@pytest.fixture(scope="function")
def test_db() -> Generator[Session, None, None]:
    """Create a test database session"""
    # Use in-memory SQLite for tests
    engine = create_engine("sqlite:///:memory:")

    # Only create tables that are SQLite-compatible
    # Skip tables with JSONB columns (job_queue, etc.)
    tables_to_create = [
        table for table in Base.metadata.sorted_tables
        if table.name not in ['job_queue', 'carbon_forecasts']  # Skip PostgreSQL-specific tables
    ]

    for table in tables_to_create:
        table.create(engine, checkfirst=True)

    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = TestingSessionLocal()

    try:
        yield db
    finally:
        db.close()
        for table in reversed(tables_to_create):
            table.drop(engine, checkfirst=True)


@pytest.fixture
def sample_account(test_db: Session) -> SocialAccount:
    """Create a sample social account"""
    account = SocialAccount(
        id=1,
        platform="instagram",
        account_id="test_account_123",
        username="test_account",
        access_token="test_token",
        follower_count=10000,
    )
    test_db.add(account)
    test_db.commit()
    test_db.refresh(account)
    return account


@pytest.fixture
def sample_posts_small(test_db: Session, sample_account: SocialAccount) -> list:
    """Create 30 sample posts (minimum for training)"""
    return _create_sample_posts(test_db, sample_account, n_posts=30)


@pytest.fixture
def sample_posts_medium(test_db: Session, sample_account: SocialAccount) -> list:
    """Create 75 sample posts (medium dataset)"""
    return _create_sample_posts(test_db, sample_account, n_posts=75)


@pytest.fixture
def sample_posts_large(test_db: Session, sample_account: SocialAccount) -> list:
    """Create 150 sample posts (large dataset with advanced features)"""
    return _create_sample_posts(test_db, sample_account, n_posts=150)


def _create_sample_posts(db: Session, account: SocialAccount, n_posts: int = 50) -> list:
    """Helper to create sample posts with realistic engagement patterns"""
    posts = []
    base_date = datetime.utcnow() - timedelta(days=n_posts)

    content_types = [ContentType.IMAGE, ContentType.VIDEO, ContentType.CAROUSEL, ContentType.REEL]

    for i in range(n_posts):
        # Create realistic temporal patterns
        post_date = base_date + timedelta(days=i)
        hour = np.random.choice([9, 12, 15, 18, 21], p=[0.15, 0.25, 0.20, 0.30, 0.10])
        post_date = post_date.replace(hour=hour, minute=np.random.randint(0, 60))

        content_type = content_types[np.random.randint(0, len(content_types))]

        # Generate caption
        caption_length = np.random.randint(50, 300)
        hashtag_count = np.random.randint(0, 15)
        has_emoji = np.random.choice([0, 1], p=[0.3, 0.7])

        # Simulate engagement with patterns
        is_weekend = post_date.weekday() >= 5
        is_evening = 17 <= hour <= 21
        is_video = content_type in [ContentType.VIDEO, ContentType.REEL]
        good_hashtags = 5 <= hashtag_count <= 10

        base_engagement = 0.02  # 2% base engagement rate

        if is_evening:
            base_engagement *= 1.5
        if is_weekend:
            base_engagement *= 1.3
        if is_video:
            base_engagement *= 1.4
        if good_hashtags:
            base_engagement *= 1.2
        if has_emoji:
            base_engagement *= 1.1

        # Add some noise
        engagement_score = base_engagement * np.random.uniform(0.7, 1.3)

        # Calculate raw metrics from engagement score
        likes = int(engagement_score * account.follower_count * 0.7)
        comments = int(engagement_score * account.follower_count * 0.15)
        shares = int(engagement_score * account.follower_count * 0.05)

        post = Post(
            account_id=account.id,
            post_id=f"test_post_{i}",
            content=f"Test post {i} " + "#test " * hashtag_count,
            post_time=post_date,
            likes=likes,
            comments=comments,
            shares=shares,
            views=likes * 3 if is_video else None,
            saves=int(likes * 0.1),
            engagement_score=engagement_score,
            content_type=content_type.value,
            caption_length=caption_length,
            hashtag_count=hashtag_count,
            has_emoji=has_emoji,
        )

        db.add(post)
        posts.append(post)

    db.commit()
    return posts


@pytest.fixture
def sample_dataframe() -> pd.DataFrame:
    """Create a sample DataFrame for testing feature engineering"""
    n_samples = 50

    data = {
        "post_id": [f"post_{i}" for i in range(n_samples)],
        "posted_at": [
            datetime(2025, 1, 1) + timedelta(days=i, hours=np.random.randint(0, 24))
            for i in range(n_samples)
        ],
        "content_type": np.random.choice(["image", "video", "carousel"], n_samples),
        "caption": [f"Test caption {i} #test #instagram" for i in range(n_samples)],
        "likes": np.random.randint(100, 1000, n_samples),
        "comments": np.random.randint(10, 100, n_samples),
        "shares": np.random.randint(5, 50, n_samples),
        "engagement_score": np.random.uniform(0.01, 0.05, n_samples),
    }

    return pd.DataFrame(data)


@pytest.fixture
def trained_model_path(tmp_path):
    """Create a temporary directory for model storage"""
    model_dir = tmp_path / "models"
    model_dir.mkdir()
    return model_dir

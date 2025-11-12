"""
Content-based feature engineering for Instagram posts
"""
import re
import pandas as pd
import numpy as np
from typing import List, Dict, Any

from ..config import CONTENT_TYPES


def extract_content_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Extract features from post content

    Args:
        df: DataFrame with content columns (content_type, caption, etc.)

    Returns:
        DataFrame with additional content features
    """
    df = df.copy()

    # Content type features (one-hot encoding will be done in main engineering)
    if "content_type" in df.columns:
        df["content_type"] = df["content_type"].fillna("photo").str.lower()
        # Ensure valid content types
        df["content_type"] = df["content_type"].apply(
            lambda x: x if x in CONTENT_TYPES else "photo"
        )

    # Caption features
    if "caption" in df.columns:
        df["caption"] = df["caption"].fillna("")
        df["caption_length"] = df["caption"].apply(len)
        df["caption_word_count"] = df["caption"].apply(lambda x: len(x.split()))
        df["has_caption"] = (df["caption_length"] > 0).astype(int)

        # Hashtag features
        df["hashtag_count"] = df["caption"].apply(count_hashtags)
        df["hashtag_density"] = df.apply(
            lambda row: row["hashtag_count"] / max(row["caption_word_count"], 1),
            axis=1
        )

        # Emoji features
        df["has_emoji"] = df["caption"].apply(contains_emoji).astype(int)
        df["emoji_count"] = df["caption"].apply(count_emojis)

        # Mention features
        df["mention_count"] = df["caption"].apply(count_mentions)

        # Question features
        df["has_question"] = df["caption"].apply(contains_question).astype(int)

        # Call-to-action features
        df["has_cta"] = df["caption"].apply(contains_cta).astype(int)

    return df


def count_hashtags(text: str) -> int:
    """Count number of hashtags in text"""
    return len(re.findall(r'#\w+', text))


def count_mentions(text: str) -> int:
    """Count number of @mentions in text"""
    return len(re.findall(r'@\w+', text))


def contains_emoji(text: str) -> bool:
    """Check if text contains emojis"""
    # Simple emoji detection using Unicode ranges
    emoji_pattern = re.compile(
        "["
        "\U0001F600-\U0001F64F"  # emoticons
        "\U0001F300-\U0001F5FF"  # symbols & pictographs
        "\U0001F680-\U0001F6FF"  # transport & map symbols
        "\U0001F1E0-\U0001F1FF"  # flags
        "\U00002702-\U000027B0"
        "\U000024C2-\U0001F251"
        "]+",
        flags=re.UNICODE
    )
    return bool(emoji_pattern.search(text))


def count_emojis(text: str) -> int:
    """Count number of emojis in text"""
    emoji_pattern = re.compile(
        "["
        "\U0001F600-\U0001F64F"
        "\U0001F300-\U0001F5FF"
        "\U0001F680-\U0001F6FF"
        "\U0001F1E0-\U0001F1FF"
        "\U00002702-\U000027B0"
        "\U000024C2-\U0001F251"
        "]+",
        flags=re.UNICODE
    )
    return len(emoji_pattern.findall(text))


def contains_question(text: str) -> bool:
    """Check if text contains a question"""
    return '?' in text


def contains_cta(text: str) -> bool:
    """
    Check if text contains call-to-action phrases

    Common CTAs: link in bio, click link, shop now, learn more, swipe up, comment below
    """
    cta_patterns = [
        r'link in bio',
        r'click link',
        r'shop now',
        r'learn more',
        r'swipe up',
        r'comment below',
        r'tag a friend',
        r'double tap',
        r'check out',
        r'visit',
        r'dm us',
        r'dm me',
    ]

    text_lower = text.lower()
    return any(re.search(pattern, text_lower) for pattern in cta_patterns)


def add_content_interactions(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add interaction features between content variables

    Args:
        df: DataFrame with content features

    Returns:
        DataFrame with interaction features added
    """
    df = df.copy()

    # Caption length × content type (will be expanded with one-hot encoding)
    if "caption_length" in df.columns and "content_type" in df.columns:
        df["caption_content_interaction"] = df["caption_length"] * df["content_type"].apply(
            lambda x: CONTENT_TYPES.index(x) if x in CONTENT_TYPES else 0
        )

    # Hashtag count × has emoji
    if "hashtag_count" in df.columns and "has_emoji" in df.columns:
        df["hashtag_emoji_interaction"] = df["hashtag_count"] * df["has_emoji"]

    return df


def get_content_stats(df: pd.DataFrame, engagement_col: str = "engagement_score") -> Dict[str, Any]:
    """
    Calculate content statistics for the dataset

    Args:
        df: DataFrame with content features and engagement
        engagement_col: Name of the engagement score column

    Returns:
        Dictionary of content statistics
    """
    stats = {
        "avg_engagement_by_content_type": (
            df.groupby("content_type")[engagement_col].mean().to_dict()
            if "content_type" in df else {}
        ),
        "content_type_distribution": (
            df["content_type"].value_counts().to_dict()
            if "content_type" in df else {}
        ),
        "caption_stats": {
            "avg_length": df["caption_length"].mean() if "caption_length" in df else None,
            "avg_hashtags": df["hashtag_count"].mean() if "hashtag_count" in df else None,
            "pct_with_emoji": df["has_emoji"].mean() * 100 if "has_emoji" in df else None,
            "pct_with_cta": df["has_cta"].mean() * 100 if "has_cta" in df else None,
        },
        "engagement_by_features": {
            "with_emoji": df[df["has_emoji"] == 1][engagement_col].mean() if "has_emoji" in df else None,
            "without_emoji": df[df["has_emoji"] == 0][engagement_col].mean() if "has_emoji" in df else None,
            "with_cta": df[df["has_cta"] == 1][engagement_col].mean() if "has_cta" in df else None,
            "without_cta": df[df["has_cta"] == 0][engagement_col].mean() if "has_cta" in df else None,
        }
    }

    return stats


def generate_content_type_combinations(content_types: List[str] = None) -> List[str]:
    """
    Generate list of content types for prediction

    Args:
        content_types: Optional list of specific content types to use

    Returns:
        List of content types
    """
    if content_types is None:
        # Default to most common types
        return ["photo", "video", "carousel", "reel"]

    # Filter to valid types only
    return [ct for ct in content_types if ct in CONTENT_TYPES]

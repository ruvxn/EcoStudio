"""
Tests for content feature engineering
"""
import pytest
import pandas as pd

from app.ml.features.content import (
    extract_content_features,
    count_hashtags,
    count_mentions,
    contains_emoji,
    count_emojis,
    contains_question,
    contains_cta,
    generate_content_type_combinations,
)


class TestContentFeatureExtraction:
    """Test content feature extraction"""

    def test_basic_content_features(self):
        """Test extraction of basic content features"""
        df = pd.DataFrame({
            "content_type": ["image", "video"],
            "caption": [
                "Check out this image! #instagram #photography",
                "New video 🎥 Link in bio!"
            ]
        })

        result = extract_content_features(df)

        # Check caption length
        assert result["caption_length"].iloc[0] > 0
        assert result["caption_word_count"].iloc[0] > 0

        # Check hashtag count
        assert result["hashtag_count"].iloc[0] == 2
        assert result["hashtag_count"].iloc[1] == 0

    def test_emoji_detection(self):
        """Test emoji detection"""
        df = pd.DataFrame({
            "caption": [
                "No emojis here",
                "With emoji 😊",
                "Multiple emojis 🎉🎊🎈"
            ]
        })

        result = extract_content_features(df)

        assert result["has_emoji"].tolist() == [0, 1, 1]
        assert result["emoji_count"].tolist() == [0, 1, 3]

    def test_mention_detection(self):
        """Test @mention counting"""
        df = pd.DataFrame({
            "caption": [
                "No mentions",
                "Thanks @user1",
                "Shoutout to @user1 and @user2"
            ]
        })

        result = extract_content_features(df)

        assert result["mention_count"].tolist() == [0, 1, 2]

    def test_question_detection(self):
        """Test question detection"""
        df = pd.DataFrame({
            "caption": [
                "This is a statement",
                "What do you think?",
                "How are you? Let me know!"
            ]
        })

        result = extract_content_features(df)

        assert result["has_question"].tolist() == [0, 1, 1]

    def test_cta_detection(self):
        """Test call-to-action detection"""
        df = pd.DataFrame({
            "caption": [
                "Just a regular post",
                "Link in bio for more info!",
                "Shop now at our store"
            ]
        })

        result = extract_content_features(df)

        assert result["has_cta"].tolist() == [0, 1, 1]


class TestHashtagFunctions:
    """Test hashtag-related functions"""

    def test_count_hashtags(self):
        assert count_hashtags("") == 0
        assert count_hashtags("#test") == 1
        assert count_hashtags("#test #instagram #photo") == 3
        assert count_hashtags("No hashtags here") == 0

    def test_hashtag_density(self):
        """Test hashtag density calculation"""
        df = pd.DataFrame({
            "caption": ["Five words and two hashtags #test #photo"]
        })

        result = extract_content_features(df)

        # 2 hashtags / 7 words ≈ 0.286
        assert 0.25 <= result["hashtag_density"].iloc[0] <= 0.35


class TestMentionFunctions:
    """Test mention-related functions"""

    def test_count_mentions(self):
        assert count_mentions("") == 0
        assert count_mentions("@user") == 1
        assert count_mentions("Thanks @user1 and @user2") == 2


class TestEmojiFunctions:
    """Test emoji-related functions"""

    def test_contains_emoji(self):
        assert contains_emoji("No emoji") is False
        assert contains_emoji("With emoji 😊") is True
        assert contains_emoji("🎉") is True

    def test_count_emojis(self):
        assert count_emojis("No emoji") == 0
        assert count_emojis("One 😊") == 1
        assert count_emojis("Multiple 🎉🎊🎈") == 3


class TestQuestionFunction:
    """Test question detection"""

    def test_contains_question(self):
        assert contains_question("Statement") is False
        assert contains_question("Question?") is True
        assert contains_question("What do you think?") is True


class TestCTAFunction:
    """Test CTA detection"""

    def test_contains_cta(self):
        assert contains_cta("Regular post") is False
        assert contains_cta("Link in bio!") is True
        assert contains_cta("Shop now at our store") is True
        assert contains_cta("Click link for more") is True
        assert contains_cta("Comment below!") is True
        assert contains_cta("Tag a friend") is True


class TestContentTypeCombinations:
    """Test content type generation"""

    def test_generate_content_types(self):
        """Test content type combinations"""
        types = generate_content_type_combinations()

        assert "image" in types
        assert "video" in types
        assert "carousel" in types
        assert "reel" in types

    def test_filter_invalid_types(self):
        """Test filtering of invalid content types"""
        types = generate_content_type_combinations(["image", "invalid_type", "video"])

        assert "image" in types
        assert "video" in types
        assert "invalid_type" not in types

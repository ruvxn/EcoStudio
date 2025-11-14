"""
Generate mock Instagram posts for ML model training.

This script creates realistic mock posts based on patterns from real Instagram data.
"""
import sys
import os
from datetime import datetime, timedelta, timezone
from random import randint, choice, uniform
import asyncio

# Add backend directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.core.database import SessionLocal
from app.api.models import Post, ContentType


def generate_mock_posts(account_id: int, num_posts: int = 50, follower_count: int = 1880):
    """
    Generate mock Instagram posts with realistic patterns.

    Args:
        account_id: ID of the social account
        num_posts: Number of mock posts to generate
        follower_count: Account follower count for engagement calculation
    """
    db = SessionLocal()

    try:
        # Define posting patterns (higher weight = more likely)
        # Based on your real data: best hour is 12 PM, best day is Saturday (5)
        hour_weights = {
            8: 0.5, 9: 0.7, 10: 0.9, 11: 1.2, 12: 2.0,  # Morning peak at 12 PM
            13: 1.5, 14: 1.3, 15: 1.0, 16: 0.8, 17: 0.9,
            18: 1.1, 19: 1.2, 20: 1.0, 21: 0.6
        }

        day_weights = {
            0: 0.7,  # Monday
            1: 0.8,  # Tuesday
            2: 0.9,  # Wednesday
            3: 1.0,  # Thursday
            4: 1.1,  # Friday
            5: 1.5,  # Saturday (best day)
            6: 1.3,  # Sunday
        }

        content_types = [
            ContentType.IMAGE,
            ContentType.VIDEO,
            ContentType.REEL,
            ContentType.CAROUSEL,
        ]

        # Sample captions with varying characteristics
        captions = [
            "Weekend vibes ✨ #weekend #lifestyle",
            "New post! Check it out 📸",
            "Throwback to better times 🌟 #tbt #memories",
            "Feeling grateful today 🙏 #gratitude #positivevibes",
            "Adventure awaits! 🌍 #travel #explore",
            "Coffee and coding ☕💻 #developer #tech",
            "Sunset views 🌅 #nature #photography",
            "Fitness journey update 💪 #fitness #health #motivation",
            "Foodie moments 🍕 #food #foodporn",
            "Monday motivation! Let's do this 🚀 #motivation #goals",
            "Behind the scenes 🎬 #bts",
            "New year, new goals! #newyear #resolutions #2024",
            "Summer vibes 🏖️☀️ #summer #beach",
            "Product launch day! 🎉 #launch #newproduct",
            "Team work makes the dream work 👥 #teamwork #collaboration",
        ]

        # Generate posts over the past 90 days
        start_date = datetime.now(timezone.utc) - timedelta(days=90)

        posts_created = 0

        for i in range(num_posts):
            # Generate random date/time with weighted distribution
            days_offset = randint(0, 89)

            # Choose hour based on weights
            hour = choice(list(hour_weights.keys()))
            post_date = start_date + timedelta(
                days=days_offset,
                hours=hour,
                minutes=randint(0, 59)
            )

            # Adjust engagement based on day of week and hour
            day_weight = day_weights.get(post_date.weekday(), 1.0)
            hour_weight = hour_weights.get(post_date.hour, 1.0)
            engagement_multiplier = day_weight * hour_weight

            # Base engagement (4-5% average like rate, 0.5-1% comment rate)
            base_like_rate = uniform(0.03, 0.06)
            base_comment_rate = uniform(0.003, 0.012)

            # Apply multipliers
            likes = int(follower_count * base_like_rate * engagement_multiplier * uniform(0.8, 1.2))
            comments = int(follower_count * base_comment_rate * engagement_multiplier * uniform(0.7, 1.3))

            # Choose caption and content type
            caption = choice(captions)
            content_type = choice(content_types)

            # Reels typically get higher engagement
            if content_type == ContentType.REEL:
                likes = int(likes * uniform(1.3, 1.8))
                comments = int(comments * uniform(1.2, 1.6))

            # Create post
            post = Post(
                account_id=account_id,
                post_id=f"mock_{i}_{int(post_date.timestamp())}",
                content=caption,
                post_time=post_date,
                likes=max(1, likes),
                comments=max(0, comments),
                shares=0,
                content_type=content_type,
                caption_length=len(caption),
                hashtag_count=caption.count('#'),
                has_emoji=1 if any(char for char in caption if ord(char) > 127) else 0,
                media_url=f"https://mock.instagram.com/{i}.jpg",
            )

            # Calculate engagement score
            post.engagement_score = post.calculate_engagement_score(follower_count)

            db.add(post)
            posts_created += 1

            if posts_created % 10 == 0:
                print(f"Generated {posts_created}/{num_posts} posts...")

        db.commit()
        print(f"\n✅ Successfully created {posts_created} mock posts!")
        print(f"Date range: {start_date.date()} to {datetime.now(timezone.utc).date()}")

        # Show statistics
        all_posts = db.query(Post).filter(Post.account_id == account_id).all()
        total_posts = len(all_posts)
        avg_engagement = sum(p.engagement_score for p in all_posts if p.engagement_score) / total_posts

        print(f"\nAccount Statistics:")
        print(f"Total posts: {total_posts}")
        print(f"Average engagement: {avg_engagement:.2%}")
        print(f"Mock posts: {posts_created}")
        print(f"Real posts: {total_posts - posts_created}")

    except Exception as e:
        print(f"❌ Error: {e}")
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Generate mock Instagram posts")
    parser.add_argument("--account-id", type=int, default=1, help="Social account ID")
    parser.add_argument("--num-posts", type=int, default=50, help="Number of mock posts to generate")
    parser.add_argument("--followers", type=int, default=1880, help="Follower count")

    args = parser.parse_args()

    print(f"Generating {args.num_posts} mock posts for account {args.account_id}...")
    generate_mock_posts(args.account_id, args.num_posts, args.followers)

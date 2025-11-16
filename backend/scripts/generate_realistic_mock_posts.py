"""
Generate realistic mock Instagram posts with learnable patterns.

This creates data with clear engagement patterns that ML models can learn:
- Multiple peak times (morning and evening)
- Day of week effects
- Content type preferences
- Realistic noise and variance
"""
import sys
import os
from datetime import datetime, timedelta, timezone
from random import randint, choices, uniform, gauss
import numpy as np

# Add backend directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.core.database import SessionLocal
from app.api.models import Post, ContentType


def generate_realistic_mock_posts(account_id: int, num_posts: int = 300, follower_count: int = 1880):
    """
    Generate mock posts with realistic Instagram engagement patterns.

    Patterns designed:
    - Peak hours: 7-9 AM (morning routine), 12-2 PM (lunch), 7-9 PM (evening)
    - Weekends slightly better than weekdays
    - Reels > Videos > Images > Carousels
    - Realistic variance (not all posts at peak times perform well)

    Args:
        account_id: Social account ID
        num_posts: Number of posts to generate
        follower_count: Account follower count
    """
    db = SessionLocal()

    try:
        print("=" * 60)
        print("Realistic Instagram Mock Data Generator")
        print("=" * 60)

        # Delete existing posts first
        existing_count = db.query(Post).filter(Post.account_id == account_id).count()
        if existing_count > 0:
            print(f"Deleting {existing_count} existing posts...")
            db.query(Post).filter(Post.account_id == account_id).delete()
            db.commit()

        # Engagement multipliers by hour (realistic Instagram patterns)
        # Peak times: 7-9 AM, 12-2 PM, 7-9 PM
        hour_engagement = {
            0: 0.4, 1: 0.3, 2: 0.3, 3: 0.3, 4: 0.4, 5: 0.5,
            6: 0.7, 7: 1.2, 8: 1.3, 9: 1.1,  # Morning peak
            10: 0.9, 11: 1.0, 12: 1.4, 13: 1.3, 14: 1.0,  # Lunch peak
            15: 0.9, 16: 0.9, 17: 1.0, 18: 1.1,
            19: 1.4, 20: 1.3, 21: 1.2,  # Evening peak
            22: 0.8, 23: 0.5,
        }

        # Day of week multipliers (0=Monday, 6=Sunday)
        day_engagement = {
            0: 0.9,   # Monday (lower)
            1: 0.95,  # Tuesday
            2: 1.0,   # Wednesday
            3: 1.0,   # Thursday
            4: 1.05,  # Friday (higher)
            5: 1.15,  # Saturday (best)
            6: 1.1,   # Sunday
        }

        # Content type engagement multipliers and distribution
        content_types_data = [
            (ContentType.REEL, 1.4, 0.35),      # 35% reels, 1.4x engagement
            (ContentType.IMAGE, 1.0, 0.30),     # 30% images, 1.0x engagement
            (ContentType.VIDEO, 1.2, 0.20),     # 20% videos, 1.2x engagement
            (ContentType.CAROUSEL, 0.95, 0.15), # 15% carousels, 0.95x engagement
        ]

        # Captions with varying qualities (affects engagement)
        caption_templates = [
            ("Weekend vibes ✨ #weekend #lifestyle #saturday", 1.1),
            ("Check this out! 📸", 0.8),
            ("Throwback to amazing times 🌟 #tbt #memories #throwback", 1.05),
            ("Grateful for this moment 🙏 #gratitude #positivevibes #blessed", 1.0),
            ("Adventure time! 🌍 #travel #explore #wanderlust", 1.15),
            ("Coffee fuels everything ☕💻 #coffee #morning #motivation", 1.1),
            ("Golden hour magic 🌅 #sunset #photography #nature", 1.2),
            ("Fitness update! 💪 #fitness #gym #health #workout #fitfam", 1.05),
            ("Food goals 🍕 #food #foodie #foodporn #yum", 1.0),
            ("Monday vibes 🚀 #monday #motivation #goals #hustle", 0.9),
            ("Behind the scenes 🎬 #bts #backstage", 0.95),
            ("New beginnings ✨ #newyear #goals #fresh", 1.0),
            ("Summer forever 🏖️☀️ #summer #beach #vacation #sun", 1.15),
            ("Big announcement! 🎉 #news #exciting #launch", 1.25),
            ("Teamwork! 👥 #team #collaboration #work", 0.85),
        ]

        # Generate posts over past 180 days for good temporal spread
        start_date = datetime.now(timezone.utc) - timedelta(days=180)
        posts_created = 0

        # Generate posts spread across different hours (not just peak times)
        all_hours = list(range(24))
        hour_weights = [hour_engagement.get(h, 0.5) for h in all_hours]

        print(f"\nGenerating {num_posts} posts with realistic patterns...")
        print(f"Date range: {start_date.date()} to {datetime.now(timezone.utc).date()}")
        print(f"Follower count: {follower_count:,}")
        print()

        for i in range(num_posts):
            # Random date within range
            days_offset = randint(0, 179)

            # Choose hour with weighted probability (more posts at peak times, but not exclusively)
            hour = choices(all_hours, weights=hour_weights, k=1)[0]

            # Create post datetime
            post_date = start_date + timedelta(
                days=days_offset,
                hours=hour,
                minutes=randint(0, 59),
                seconds=randint(0, 59)
            )

            # Get multipliers
            day_of_week = post_date.weekday()
            hour_mult = hour_engagement.get(hour, 0.5)
            day_mult = day_engagement.get(day_of_week, 1.0)

            # Choose content type with weighted distribution
            content_type, content_mult, _ = choices(
                content_types_data,
                weights=[prob for _, _, prob in content_types_data],
                k=1
            )[0]

            # Choose caption
            caption, caption_mult = choices(caption_templates, k=1)[0]

            # Base engagement rate with realistic variance
            # Use normal distribution centered at 7% with some spread
            base_rate = gauss(0.07, 0.02)
            base_rate = max(0.01, min(0.20, base_rate))  # Clamp between 1% and 20%

            # Apply all multipliers
            total_mult = hour_mult * day_mult * content_mult * caption_mult

            # Add random variance (some posts just don't perform well, even at peak times)
            random_variance = gauss(1.0, 0.15)
            random_variance = max(0.5, min(1.5, random_variance))

            # Final engagement rate
            engagement_rate = base_rate * total_mult * random_variance
            engagement_rate = max(0.005, min(0.25, engagement_rate))

            # Calculate metrics from engagement rate
            total_engagement = int(follower_count * engagement_rate)

            # Distribute across likes, comments, shares
            likes = int(total_engagement * uniform(0.75, 0.90))
            comments = int(total_engagement * uniform(0.08, 0.15))
            shares = int(total_engagement * uniform(0.00, 0.05))

            # Ensure minimum engagement
            likes = max(5, likes)
            comments = max(0, comments)

            # Create post
            post = Post(
                account_id=account_id,
                post_id=f"realistic_mock_{i}_{int(post_date.timestamp())}",
                content=caption,
                post_time=post_date,
                likes=likes,
                comments=comments,
                shares=shares,
                views=likes * randint(8, 15) if content_type in [ContentType.VIDEO, ContentType.REEL] else None,
                saves=int(likes * uniform(0.05, 0.12)),
                engagement_score=engagement_rate,
                content_type=content_type.value,
                caption_length=len(caption),
                hashtag_count=caption.count('#'),
                has_emoji=1 if any(ord(c) > 127 for c in caption) else 0,
                media_url=f"https://mock.instagram.com/realistic/{i}.jpg",
            )

            db.add(post)
            posts_created += 1

            # Commit in batches
            if posts_created % 50 == 0:
                db.commit()
                print(f"  Created {posts_created}/{num_posts} posts...")

        # Final commit
        db.commit()

        print()
        print("=" * 60)
        print("✅ Data Generation Complete!")
        print("=" * 60)

        # Calculate and display statistics
        all_posts = db.query(Post).filter(Post.account_id == account_id).all()

        # Engagement by hour
        from collections import defaultdict
        hour_stats = defaultdict(list)
        day_stats = defaultdict(list)
        content_stats = defaultdict(list)

        for post in all_posts:
            hour_stats[post.post_time.hour].append(post.engagement_score)
            day_stats[post.post_time.weekday()].append(post.engagement_score)
            content_stats[post.content_type].append(post.engagement_score)

        print(f"\nDataset Statistics:")
        print(f"Total posts: {len(all_posts)}")
        print(f"Average engagement: {np.mean([p.engagement_score for p in all_posts]):.2%}")
        print(f"Engagement std dev: {np.std([p.engagement_score for p in all_posts]):.2%}")

        print(f"\nTop 5 Hours by Engagement:")
        hour_avgs = {h: np.mean(scores) for h, scores in hour_stats.items()}
        for hour, avg in sorted(hour_avgs.items(), key=lambda x: x[1], reverse=True)[:5]:
            print(f"  {hour:02d}:00 - {avg:.2%} avg engagement ({len(hour_stats[hour])} posts)")

        print(f"\nTop Days by Engagement:")
        day_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        day_avgs = {d: np.mean(scores) for d, scores in day_stats.items()}
        for day, avg in sorted(day_avgs.items(), key=lambda x: x[1], reverse=True):
            print(f"  {day_names[day]}: {avg:.2%} avg engagement ({len(day_stats[day])} posts)")

        print(f"\nContent Type Performance:")
        content_avgs = {c: np.mean(scores) for c, scores in content_stats.items()}
        for content_type, avg in sorted(content_avgs.items(), key=lambda x: x[1], reverse=True):
            print(f"  {content_type}: {avg:.2%} avg engagement ({len(content_stats[content_type])} posts)")

        print()
        print("=" * 60)
        print("Next Steps:")
        print("=" * 60)
        print("1. Train the ML model:")
        print(f"   curl -X POST http://localhost:8000/api/v1/predictions/train \\")
        print(f"     -H 'Content-Type: application/json' \\")
        print(f"     -d '{{\"account_id\": {account_id}, \"force_retrain\": true}}'")
        print()
        print("2. View predictions:")
        print(f"   curl http://localhost:8000/api/v1/predictions/{account_id}/latest")
        print()

        return posts_created

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Generate realistic mock Instagram posts")
    parser.add_argument("--account-id", type=int, default=1, help="Social account ID")
    parser.add_argument("--num-posts", type=int, default=300, help="Number of posts to generate")
    parser.add_argument("--followers", type=int, default=1880, help="Follower count")

    args = parser.parse_args()

    generate_realistic_mock_posts(args.account_id, args.num_posts, args.followers)

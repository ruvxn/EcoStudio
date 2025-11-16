"""
Create mock historical jobs with carbon savings data for analytics demo.
"""
import asyncio
import os
import random
from datetime import datetime, timedelta, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Add parent directory to path for imports
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.api.models.job_queue import Job, JobType, JobStatus
from app.api.models.carbon_savings import CarbonSaving
from app.core.database import Base

# Database setup
DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://ruveenjayasinghe@127.0.0.1:5432/ecostudio_db')
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)


def create_mock_historical_jobs():
    """Create mock completed jobs with carbon savings over the past 30 days."""

    db = SessionLocal()

    try:
        now = datetime.now(timezone.utc)

        # Job types with their typical durations and energy consumption
        job_configs = [
            (JobType.GENERATE_CONTENT, 15, 0.5),  # 15 min, 0.5 kWh
            (JobType.RETRAIN_MODEL, 30, 2.0),     # 30 min, 2.0 kWh
            (JobType.SYNC_POSTS, 10, 0.3),        # 10 min, 0.3 kWh
            (JobType.CALCULATE_ENGAGEMENT, 10, 0.4),  # 10 min, 0.4 kWh
            (JobType.POST_CONTENT, 5, 0.1),       # 5 min, 0.1 kWh
        ]

        created_jobs = []

        # Create 50 historical jobs over the past 30 days
        for i in range(50):
            # Random day in past 30 days
            days_ago = random.randint(0, 29)

            # Random time of day
            hour = random.randint(0, 23)
            minute = random.randint(0, 59)

            # Create job timestamp
            completed_time = now - timedelta(days=days_ago, hours=24-hour, minutes=60-minute)
            started_time = completed_time - timedelta(minutes=random.randint(5, 30))
            scheduled_time = started_time - timedelta(minutes=random.randint(0, 5))
            created_time = scheduled_time - timedelta(hours=random.randint(1, 48))

            # Random job type
            job_type, duration_min, energy_kwh = random.choice(job_configs)

            # Simulate carbon-aware scheduling:
            # 70% of jobs scheduled during green windows (low carbon)
            # 30% scheduled at higher carbon times
            is_green = random.random() < 0.7

            if is_green:
                # Green window: 150-300 gCO2/kWh
                actual_carbon = random.randint(150, 300)
                baseline_carbon = random.randint(350, 600)  # What it would have been
            else:
                # Medium window: 300-450 gCO2/kWh
                actual_carbon = random.randint(300, 450)
                baseline_carbon = random.randint(450, 650)

            # Calculate savings
            carbon_saved_grams = int((baseline_carbon - actual_carbon) * energy_kwh)

            # Create job
            job = Job(
                job_type=job_type,
                account_id=1,  # Default account
                scheduled_for=scheduled_time,
                carbon_intensity=actual_carbon,
                estimated_duration_minutes=duration_min,
                carbon_score=random.uniform(0.6, 0.95),
                status=JobStatus.COMPLETED,
                priority=random.randint(3, 7),
                created_at=created_time,
                started_at=started_time,
                completed_at=completed_time,
            )

            db.add(job)
            db.flush()  # Get the job ID

            # Create carbon savings record
            savings = CarbonSaving(
                job_id=job.id,
                scheduled_carbon_intensity=actual_carbon,
                average_carbon_intensity=int((actual_carbon + baseline_carbon) / 2),
                baseline_carbon_intensity=baseline_carbon,
                carbon_saved_grams=carbon_saved_grams,
                energy_used_kwh=energy_kwh,
                calculation_method="baseline_comparison",
                created_at=completed_time,
            )

            db.add(savings)
            created_jobs.append(job.id)

            print(f"Created job {job.id}: {job_type.value} - "
                  f"Saved {carbon_saved_grams}g CO2 "
                  f"({actual_carbon} vs {baseline_carbon} gCO2/kWh)")

        db.commit()

        # Summary
        total_saved = db.query(CarbonSaving).count()
        total_grams = sum([s.carbon_saved_grams for s in db.query(CarbonSaving).all()])
        total_kg = total_grams / 1000.0

        print(f"\n✅ Created {len(created_jobs)} mock historical jobs")
        print(f"📊 Total carbon savings records: {total_saved}")
        print(f"🌱 Total CO2 saved: {total_kg:.2f} kg ({total_grams} grams)")
        print(f"🌳 Equivalent to: {(total_kg/20):.2f} trees planted")
        print(f"🚗 Equivalent to: {(total_kg/0.404):.0f} miles not driven")

        return created_jobs

    except Exception as e:
        db.rollback()
        print(f"❌ Error creating mock jobs: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    print("Creating mock historical jobs with carbon savings data...\n")
    create_mock_historical_jobs()
    print("\n✨ Done! Refresh your analytics dashboard to see the data.")

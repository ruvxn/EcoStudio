"""
Tests for Carbon Forecast Service.
"""
import pytest
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.services.carbon_forecast_service import CarbonForecastService
from app.api.models.carbon_forecasts import CarbonForecast
from app.api.models.green_windows import GreenWindow


# Test database setup
TEST_DATABASE_URL = "sqlite:///:memory:"


@pytest.fixture
def db_session():
    """Create a test database session."""
    engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)

    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = SessionLocal()

    yield session

    session.close()
    Base.metadata.drop_all(bind=engine)


@pytest.mark.asyncio
async def test_generate_mock_forecast(db_session):
    """Test generating mock forecast data."""
    service = CarbonForecastService(db_session)

    forecasts = service._generate_mock_forecast(hours=24)

    assert len(forecasts) == 24
    assert all('forecast_time' in f for f in forecasts)
    assert all('carbon_intensity' in f for f in forecasts)
    assert all(200 <= f['carbon_intensity'] <= 600 for f in forecasts)


def test_store_forecasts(db_session):
    """Test storing forecast data in database."""
    service = CarbonForecastService(db_session)

    now = datetime.utcnow()
    forecasts = [
        {
            'forecast_time': now + timedelta(hours=i),
            'carbon_intensity': 300 + (i * 10),
            'is_renewable_high': (300 + (i * 10)) < 300
        }
        for i in range(5)
    ]

    count = service.store_forecasts(forecasts)

    assert count == 5

    # Verify stored in database
    stored = db_session.query(CarbonForecast).count()
    assert stored == 5


def test_get_current_intensity(db_session):
    """Test getting current carbon intensity."""
    service = CarbonForecastService(db_session)

    now = datetime.utcnow()
    forecast = CarbonForecast(
        region='AU-VIC',
        forecast_time=now,
        carbon_intensity=350,
        source='test'
    )
    db_session.add(forecast)
    db_session.commit()

    intensity = service.get_current_intensity()

    assert intensity == 350


def test_generate_green_windows(db_session):
    """Test green window generation."""
    service = CarbonForecastService(db_session)

    # Create forecasts with some low-carbon periods
    now = datetime.utcnow()
    for i in range(24):
        # Create a low-carbon window from hour 2-6
        if 2 <= i <= 6:
            intensity = 250
        else:
            intensity = 450

        forecast = CarbonForecast(
            region='AU-VIC',
            forecast_time=now + timedelta(hours=i),
            carbon_intensity=intensity,
            source='test'
        )
        db_session.add(forecast)

    db_session.commit()

    # Generate windows
    window_count = service.generate_green_windows(hours_ahead=24)

    assert window_count >= 1

    # Verify windows created
    windows = db_session.query(GreenWindow).all()
    assert len(windows) >= 1
    assert all(w.avg_carbon_intensity < 300 for w in windows)


@pytest.mark.asyncio
async def test_update_forecasts(db_session):
    """Test full forecast update flow."""
    service = CarbonForecastService(db_session)

    count = await service.update_forecasts()

    # Should generate mock data when API key not present
    assert count > 0

    # Verify data stored
    forecasts = db_session.query(CarbonForecast).count()
    assert forecasts > 0


def test_get_forecasts(db_session):
    """Test retrieving forecasts."""
    service = CarbonForecastService(db_session)

    now = datetime.utcnow()
    for i in range(10):
        forecast = CarbonForecast(
            region='AU-VIC',
            forecast_time=now + timedelta(hours=i),
            carbon_intensity=300 + (i * 10),
            source='test'
        )
        db_session.add(forecast)

    db_session.commit()

    forecasts = service.get_forecasts(hours=5)

    assert len(forecasts) <= 5

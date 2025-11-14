# Phase 2: Carbon-Aware Job Orchestration - Implementation Complete

## Overview

Phase 2 adds the sustainability layer to EcoStudio by integrating carbon intensity forecasting and intelligent job scheduling. All compute-intensive operations (model retraining, content generation) now execute during low-carbon energy windows.

## What's New in Phase 2

### Backend Components

#### 1. **Carbon Forecast Service** ([carbon_forecast_service.py](backend/app/services/carbon_forecast_service.py))
- Fetches 72-hour carbon intensity forecasts from ElectricityMap API
- Generates mock data when API key not available (for development)
- Automatically updates every 6 hours via scheduled job
- Identifies and stores green windows for optimal job scheduling

#### 2. **Green Window Finder** ([green_window_finder.py](backend/app/services/green_window_finder.py))
- Finds optimal execution windows with low carbon intensity
- Calculates carbon savings by comparing against baseline
- Stores carbon savings metrics for analytics

#### 3. **Eco Scheduler** ([eco_scheduler.py](backend/app/services/eco_scheduler.py))
- Carbon-aware job orchestration using APScheduler
- Schedules jobs during green windows automatically
- Executes jobs based on priority and carbon score
- Background tasks:
  - Update carbon forecasts every 6 hours
  - Execute pending jobs every 30 minutes
  - Schedule weekly model retraining on Sundays

#### 4. **Database Models**
- **green_windows**: Stores optimal execution periods
- **carbon_savings**: Tracks environmental impact
- **system_config**: Dynamic configuration settings
- **Enhanced job_queue**: Added carbon-related fields
- **Enhanced carbon_forecasts**: Added renewable energy indicator

#### 5. **API Endpoints**

**Carbon APIs** ([/api/v1/carbon](backend/app/api/endpoints/carbon.py)):
- `GET /current` - Current carbon intensity
- `GET /forecast?hours=72` - 72-hour carbon forecast
- `GET /windows?hours_ahead=72` - Green windows for scheduling
- `POST /forecast/update` - Manually trigger forecast update

**Jobs APIs** ([/api/v1/jobs](backend/app/api/endpoints/jobs.py)):
- `GET /` - List jobs with filters (status, account, type)
- `GET /{job_id}` - Get specific job details
- `POST /schedule` - Schedule a job with carbon optimization
- `DELETE /{job_id}` - Cancel a queued job
- `GET /analytics/carbon?days=30` - Carbon savings analytics
- `GET /stats/summary` - Job queue summary statistics

## Getting Started

### Prerequisites

1. **ElectricityMap API Key** (Optional but recommended)
   - Sign up at [https://www.electricitymap.org/api](https://www.electricitymap.org/api)
   - Free tier includes 100 requests/day
   - Without API key, system uses mock data

2. **Python 3.11+** with dependencies from [requirements.txt](backend/requirements.txt)

3. **PostgreSQL 15+** database

### Installation Steps

1. **Copy environment variables**:
   ```bash
   cp .env.example .env
   ```

2. **Configure your .env file**:
   ```bash
   # Required
   DATABASE_URL=postgresql://postgres:postgres@localhost:5432/ecotrainer

   # Optional - for real carbon data
   ELECTRICITY_MAP_API_KEY=your-api-key-here
   ELECTRICITY_MAP_REGION=AU-VIC  # Your grid region

   # Instagram OAuth (from Meta Developers)
   INSTAGRAM_CLIENT_ID=your-client-id
   INSTAGRAM_CLIENT_SECRET=your-client-secret
   ```

3. **Run database migrations**:
   ```bash
   cd backend
   alembic upgrade head
   ```

4. **Start with Docker Compose**:
   ```bash
   docker-compose up -d
   ```

   Or manually:
   ```bash
   # Backend
   cd backend
   uvicorn app.main:app --reload

   # Frontend (in separate terminal)
   cd frontend
   npm run dev
   ```

5. **Access the application**:
   - Backend API: [http://localhost:8000](http://localhost:8000)
   - API Docs: [http://localhost:8000/docs](http://localhost:8000/docs)
   - Frontend: [http://localhost:3000](http://localhost:3000)
   - Health Check: [http://localhost:8000/health](http://localhost:8000/health)

## How It Works

### Carbon-Aware Scheduling Flow

```
1. Carbon Forecast Service fetches data every 6 hours
   ↓
2. Green Window Finder identifies low-carbon periods
   ↓
3. User/System schedules a job (e.g., model retraining)
   ↓
4. Eco Scheduler finds optimal green window
   ↓
5. Job waits until green window arrives
   ↓
6. Job executes during low-carbon period
   ↓
7. Carbon savings calculated and logged
```

### Example: Scheduling a Job

```python
# Via API
POST /api/v1/jobs/schedule
{
  "job_type": "RETRAIN_MODEL",
  "account_id": 123,
  "use_green_window": true,
  "priority": 5
}

# System automatically:
# 1. Finds greenest window in next 7 days
# 2. Schedules job for that time
# 3. Executes when window arrives
# 4. Logs carbon savings
```

### Monitoring Carbon Impact

```bash
# Get current carbon intensity
curl http://localhost:8000/api/v1/carbon/current

# View 72-hour forecast
curl http://localhost:8000/api/v1/carbon/forecast?hours=72

# Check green windows
curl http://localhost:8000/api/v1/carbon/windows

# View carbon savings analytics
curl http://localhost:8000/api/v1/jobs/analytics/carbon?days=30
```

## Testing

### Run Backend Tests

```bash
cd backend
pytest tests/test_services/test_carbon_forecast_service.py -v
```

### Manual Testing

1. **Trigger forecast update**:
   ```bash
   curl -X POST http://localhost:8000/api/v1/carbon/forecast/update
   ```

2. **Schedule a test job**:
   ```bash
   curl -X POST http://localhost:8000/api/v1/jobs/schedule \
     -H "Content-Type: application/json" \
     -d '{"job_type": "RETRAIN_MODEL", "account_id": 1, "use_green_window": true}'
   ```

3. **Check job status**:
   ```bash
   curl http://localhost:8000/api/v1/jobs
   ```

4. **View carbon analytics**:
   ```bash
   curl http://localhost:8000/api/v1/jobs/analytics/carbon?days=7
   ```

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    ENHANCED BACKEND                              │
│                                                                   │
│  Services:                                                        │
│  • CarbonForecastService - Fetch & store ElectricityMap data     │
│  • EcoScheduler - Job orchestration in green windows             │
│  • GreenWindowFinder - Optimize scheduling based on carbon       │
│                                                                   │
│  New Tables:                                                      │
│  • green_windows - Optimal execution periods                     │
│  • carbon_savings - Environmental impact tracking                │
│  • system_config - Dynamic configuration                         │
│                                                                   │
│  Routes:                                                          │
│  • /api/v1/carbon/* - Carbon data endpoints                      │
│  • /api/v1/jobs/* - Job management & analytics                   │
└───────────────────────────────────────────────────────────────────┘
```

## Configuration

### System Configuration (stored in database)

The following settings can be configured in the `system_config` table:

| Key | Default | Description |
|-----|---------|-------------|
| `carbon_threshold_low` | 300 gCO2/kWh | Carbon intensity considered low |
| `carbon_threshold_high` | 600 gCO2/kWh | Carbon intensity considered high |
| `scheduler_enabled` | true | Enable automatic job scheduling |
| `green_window_preference` | 0.7 | Priority for green windows (0-1) |
| `default_region` | AU-VIC | Electricity grid region |
| `forecast_update_interval_hours` | 6 | Forecast update frequency |

### Electricity Regions

Common region codes for ElectricityMap:
- `AU-VIC` - Victoria, Australia
- `AU-NSW` - New South Wales, Australia
- `US-CAL` - California, USA
- `DE` - Germany
- `GB` - Great Britain
- `FR` - France

See [ElectricityMap zones](https://github.com/electricitymaps/electricitymaps-contrib/blob/master/config/zones.yaml) for full list.

## Performance & Sustainability Metrics

### Expected Carbon Savings

Based on typical grid carbon intensity patterns:
- **25-40% reduction** vs random scheduling
- **Higher savings** in regions with renewable energy peaks
- **Actual savings** depend on grid mix and timing flexibility

### Job Duration Estimates

Used for scheduling calculations:
| Job Type | Estimated Duration | Energy (kWh/job) |
|----------|-------------------|------------------|
| Model Retraining | 30 minutes | 2.0 |
| Content Generation | 15 minutes | 0.5 |
| Post Sync | 10 minutes | 0.1 |
| Carbon Forecast | 5 minutes | 0.05 |

## Troubleshooting

### Scheduler Not Starting

```bash
# Check logs
docker-compose logs backend | grep -i scheduler

# Verify health check
curl http://localhost:8000/health
```

### No Carbon Data

```bash
# Check if API key is set
docker-compose exec backend env | grep ELECTRICITY_MAP

# Trigger manual update
curl -X POST http://localhost:8000/api/v1/carbon/forecast/update

# Check database
docker-compose exec postgres psql -U postgres -d ecotrainer -c "SELECT COUNT(*) FROM carbon_forecasts;"
```

### Jobs Not Executing

```bash
# Check job queue
curl http://localhost:8000/api/v1/jobs?status=queued

# Check scheduler status
curl http://localhost:8000/health

# View logs
docker-compose logs backend | grep -i "executing job"
```

## Next Steps: Phase 3

Phase 3 will add AI-powered content generation:
- OpenAI integration for caption writing
- Image analysis and hashtag suggestions
- Content scheduling recommendations
- A/B testing capabilities

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development guidelines.

## License

MIT License - See [LICENSE](LICENSE)

## Support

- Documentation: [docs/](docs/)
- Issues: [GitHub Issues](https://github.com/yourusername/EcoStudio/issues)
- API Docs: http://localhost:8000/docs (when running)

# EcoTrainer Studio - Phase 2 Architecture

## System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                         Frontend (Next.js 14)                   │
│                        http://localhost:3000                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────┐ │
│  │  EcoTimeline     │  │ CarbonAnalytics  │  │  JobQueue    │ │
│  │  - 72hr forecast │  │ - CO₂ savings    │  │ - Real-time  │ │
│  │  - Job markers   │  │ - Impact metrics │  │ - Filtering  │ │
│  └──────────────────┘  └──────────────────┘  └──────────────┘ │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │          CurrentCarbonIndicator                         │   │
│  │          - Live intensity • Color-coded status          │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
└──────────────────────┬──────────────────────────────────────────┘
                       │ HTTP/REST API
                       │ Axios + SWR
                       ▼
┌─────────────────────────────────────────────────────────────────┐
│                     Backend (FastAPI)                           │
│                   http://localhost:8000                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  API Endpoints                       Background Services        │
│  ┌────────────────────┐             ┌────────────────────┐    │
│  │ /carbon/current    │             │   EcoScheduler     │    │
│  │ /carbon/forecast   │◄────────────┤   - Forecast fetcher   │
│  │ /carbon/windows    │             │   - Job executor   │    │
│  │                    │             │   - Weekly cron    │    │
│  │ /jobs              │◄────────────┤                    │    │
│  │ /jobs/schedule     │             │   APScheduler      │    │
│  │ /jobs/analytics    │             │   (AsyncIO)        │    │
│  └────────────────────┘             └────────────────────┘    │
│           │                                   │                │
│           ▼                                   ▼                │
│  ┌─────────────────────────────────────────────────────┐      │
│  │              Core Services                          │      │
│  │                                                     │      │
│  │  ┌──────────────────────┐  ┌──────────────────┐   │      │
│  │  │ CarbonForecastService │  │ GreenWindowFinder│   │      │
│  │  │ - ElectricityMap API │  │ - Optimal windows│   │      │
│  │  │ - Forecast caching   │  │ - Carbon savings │   │      │
│  │  └──────────────────────┘  └──────────────────┘   │      │
│  │                                                     │      │
│  │  ┌──────────────────────┐  ┌──────────────────┐   │      │
│  │  │     MLService        │  │ InstagramSync    │   │      │
│  │  │ - Model training     │  │ - Post sync      │   │      │
│  │  │ - Predictions        │  │ - OAuth          │   │      │
│  │  └──────────────────────┘  └──────────────────┘   │      │
│  └─────────────────────────────────────────────────────┘      │
│                                                                 │
└──────────────────────┬──────────────────────────────────────────┘
                       │ SQLAlchemy ORM
                       ▼
┌─────────────────────────────────────────────────────────────────┐
│                   PostgreSQL Database                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Core Tables              Carbon Intelligence Tables            │
│  ┌──────────────────┐    ┌──────────────────┐                 │
│  │ social_accounts  │    │ carbon_forecasts │                 │
│  │ posts            │    │ green_windows    │                 │
│  │ predictions      │    │ carbon_savings   │                 │
│  │ scheduled_posts  │    │ job_queue        │                 │
│  │ execution_logs   │    │ system_config    │                 │
│  └──────────────────┘    └──────────────────┘                 │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
                       ▲
                       │ Data Fetch
                       │
┌─────────────────────────────────��────────────────────────────┐
│               External APIs                                  │
├──────────────────────────────────────────────────────────────┤
│  ElectricityMap API          Instagram Graph API            │
│  - Carbon forecasts          - Post data                    │
│  - Renewable % data          - Engagement metrics           │
└──────────────────────────────────────────────────────────────┘
```

## Data Flow

### 1. Carbon Forecast Collection
```
EcoScheduler (every 6h)
    ↓
CarbonForecastService.update_forecasts()
    ↓
ElectricityMap API (fetch 72h forecast)
    ↓
Store in carbon_forecasts table
    ↓
GreenWindowFinder.identify_windows()
    ↓
Store in green_windows table
```

### 2. Job Scheduling
```
User → POST /api/v1/jobs/schedule
    ↓
JobsAPI.schedule_job()
    ↓
EcoScheduler.schedule_job()
    ↓
GreenWindowFinder.find_optimal_window()
    ↓
Insert into job_queue table
    ↓
Return job_id to frontend
```

### 3. Job Execution
```
EcoScheduler (every 30min)
    ↓
Check for due jobs in job_queue
    ↓
Execute job (e.g., MLService.train_model())
    ↓
Calculate carbon savings
    ↓
Store in carbon_savings table
    ↓
Update job status in job_queue
```

### 4. Dashboard Updates
```
Frontend components (auto-refresh)
    ↓
GET /api/v1/carbon/forecast
GET /api/v1/jobs
GET /api/v1/jobs/analytics/carbon
    ↓
Parse and visualize data
    ↓
Display in dashboard
```

## Component Relationships

### Backend Services
- **EcoScheduler**: Orchestrates all background tasks
  - Uses: CarbonForecastService, GreenWindowFinder, MLService
  - Manages: Job queue, forecast updates, weekly retraining

- **CarbonForecastService**: Carbon data management
  - External: ElectricityMap API
  - Storage: carbon_forecasts table

- **GreenWindowFinder**: Optimization engine
  - Reads: carbon_forecasts
  - Writes: green_windows, carbon_savings
  - Calculates: Optimal scheduling windows

- **MLService**: Machine learning operations
  - Reads: posts, predictions
  - Executes: Model training (compute-intensive)
  - Scheduled by: EcoScheduler in green windows

### Frontend Components
- **EcoTimeline**: Primary visualization
  - Data: Carbon forecasts + scheduled jobs
  - Updates: Every 5 minutes
  - Interactive: Hover for details

- **CarbonAnalytics**: Impact dashboard
  - Data: Aggregated carbon savings
  - Displays: Summary stats, daily breakdown
  - Period: Selectable (7/30/90 days)

- **JobQueue**: Job monitoring
  - Data: Job queue with filters
  - Updates: Every 30 seconds
  - Actions: View details, cancel jobs

## API Endpoints Map

### Carbon Endpoints
```
GET    /api/v1/carbon/current         → Current carbon intensity
GET    /api/v1/carbon/forecast        → 72-hour forecast
GET    /api/v1/carbon/windows         → Green scheduling windows
POST   /api/v1/carbon/forecast/update → Manual forecast refresh
```

### Job Endpoints
```
GET    /api/v1/jobs                   → List jobs (with filters)
GET    /api/v1/jobs/{id}              → Get specific job
POST   /api/v1/jobs/schedule          → Schedule new job
DELETE /api/v1/jobs/{id}              → Cancel job
GET    /api/v1/jobs/analytics/carbon  → Carbon savings analytics
GET    /api/v1/jobs/stats/summary     → Queue statistics
```

### System Endpoints
```
GET    /health                        → System health check
GET    /docs                          → OpenAPI documentation
GET    /                              → API information
```

## Technology Stack

### Backend
- **Framework**: FastAPI 0.115.5
- **Database**: PostgreSQL + SQLAlchemy 2.0.36
- **Scheduler**: APScheduler 3.10.4 (AsyncIO)
- **ML**: scikit-learn 1.6.0 + XGBoost 2.1.3
- **HTTP**: httpx 0.28.1 (async)

### Frontend
- **Framework**: Next.js 14 (App Router)
- **Language**: TypeScript 5.x
- **Styling**: Tailwind CSS 3.x
- **Charts**: Recharts 2.x
- **HTTP**: Axios 1.x + SWR 2.x
- **Dates**: date-fns 2.x

## Deployment Architecture

```
┌────────────────────────────────────────────────┐
│              Production (Future)               │
├────────────────────────────────────────────────┤
│                                                │
│  Frontend: Vercel (Next.js)                   │
│  Backend:  Railway/Fly.io (FastAPI + uvicorn) │
│  Database: Supabase/Railway (PostgreSQL)      │
│  Cron:     Built-in APScheduler               │
│                                                │
└────────────────────────────────────────────────┘
```

## Current Development Setup

```
┌────────────────────────────────────────────────┐
│               Local Development                │
├────────────────────────────────────────────────┤
│                                                │
│  Frontend: localhost:3000 (npm run dev)       │
│  Backend:  localhost:8000 (uvicorn)           │
│  Database: PostgreSQL (local/Docker)          │
│  Scheduler: APScheduler (in-process)          │
│                                                │
└────────────────────────────────────────────────┘
```

---

Built with for sustainable AI training

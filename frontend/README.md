# EcoTrainer Studio Frontend

Phase 2 Dashboard for carbon-aware AI training and job scheduling.

## Features

### Real-Time Carbon Monitoring
- Live carbon intensity indicator
- 72-hour carbon forecast visualization
- Green window identification

### 📊 Carbon Analytics Dashboard
- Total CO₂ savings tracking
- Environmental impact metrics (trees planted equivalent, miles not driven)
- Daily breakdown charts
- Period selection (7/30/90 days)

### ⚡ Job Queue Management
- Real-time job monitoring
- Status filtering (queued, running, completed, failed)
- Carbon intensity per job
- Auto-refresh every 30 seconds

## Tech Stack

- **Framework**: Next.js 14 (App Router)
- **Language**: TypeScript
- **Styling**: Tailwind CSS
- **Charts**: Recharts
- **HTTP Client**: Axios
- **Data Fetching**: SWR
- **Date Handling**: date-fns

## Getting Started

### Prerequisites

- Node.js 18+ installed
- Backend API running on `http://localhost:8000`

### Installation

```bash
# Install dependencies
npm install

# Set up environment variables
cp .env.local.example .env.local
# Edit .env.local if your backend is on a different URL

# Start development server
npm run dev
```

The app will be available at [http://localhost:3000](http://localhost:3000)

### Build for Production

```bash
# Build
npm run build

# Start production server
npm start
```

## API Integration

The frontend connects to the FastAPI backend via the API client in `lib/api.ts`.

### Available Endpoints

- `GET /api/v1/carbon/current` - Current carbon intensity
- `GET /api/v1/carbon/forecast` - Carbon forecast
- `GET /api/v1/carbon/windows` - Green scheduling windows
- `GET /api/v1/jobs` - Job queue with filters
- `POST /api/v1/jobs/schedule` - Schedule a new job
- `GET /api/v1/jobs/analytics/carbon` - Carbon analytics

## Component Overview

### EcoTimeline
- Displays 72-hour carbon intensity forecast
- Shows scheduled jobs as markers on the timeline
- Color-coded intensity zones (green/yellow/red)

### CarbonAnalytics
- Summary cards: Total CO₂ saved, jobs optimized, avg savings, energy
- Environmental impact equivalents
- Daily breakdown bar chart

### JobQueue
- Lists all jobs with status filtering
- Real-time updates every 30 seconds
- Shows job metadata: type, schedule time, carbon intensity, duration

---

Built with and for a sustainable future

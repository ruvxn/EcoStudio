# EcoTrainer Studio

An AI-powered content scheduler that predicts optimal posting times using machine learning and executes compute-intensive tasks during low-carbon energy windows to reduce environmental impact.

## Overview

EcoTrainer Studio automates your social media content strategy with a weekly cycle:
1. **Analyze** - Fetch engagement data from Instagram/YouTube
2. **Retrain** - Update ML prediction model (scheduled during green energy windows)
3. **Predict** - Forecast best posting times for the upcoming week
4. **Generate** - Create content for scheduled posts (during green energy windows)
5. **Post** - Auto-publish at predicted optimal times

**Key Innovation:** Compute-heavy operations are scheduled during periods of low carbon intensity, reducing environmental footprint while maintaining content performance.

## Technology Stack

### Backend
- **FastAPI** (Python 3.11+) - High-performance async API framework
- **PostgreSQL 15** - Relational database for structured data
- **SQLAlchemy 2.0** - Modern Python ORM
- **XGBoost** - ML model for engagement prediction
- **APScheduler** - Background job scheduling

### Frontend
- **Next.js 14** - React framework with App Router
- **TypeScript** - Type-safe JavaScript
- **Tailwind CSS** - Utility-first styling
- **Recharts** - Data visualization

### Infrastructure
- **Docker & Docker Compose** - Containerized development environment
- **AWS** - Production deployment (EC2, RDS, S3)
- **ElectricityMap API** - Real-time carbon intensity data
- **OpenAI GPT-4** - AI content generation

## Quick Start

### Prerequisites
- Docker and Docker Compose
- Git
- Node.js 18+ (for local frontend development)
- Python 3.11+ (for local backend development)

### 1. Clone the Repository
```bash
git clone https://github.com/yourusername/EcoStudio.git
cd EcoStudio
```

### 2. Set Up Environment Variables
```bash
# Backend
cp backend/.env.example backend/.env
# Edit backend/.env with your API keys and configuration
```

### 3. Start with Docker Compose
```bash
# Start all services (database, backend, frontend)
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

### 4. Access the Application
- **Frontend**: http://localhost:3000
- **API Documentation**: http://localhost:8000/docs
- **API Health Check**: http://localhost:8000/health
- **pgAdmin** (optional): http://localhost:5050

## Project Structure

```
EcoStudio/
├── backend/                 # FastAPI backend
│   ├── app/
│   │   ├── api/            # API layer
│   │   │   ├── endpoints/  # REST API routes
│   │   │   ├── models/     # SQLAlchemy models
│   │   │   └── schemas/    # Pydantic schemas
│   │   ├── core/           # Core configuration
│   │   ├── services/       # Business logic services
│   │   └── ml/             # ML models and training
│   ├── tests/              # Backend tests
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/               # Next.js frontend
│   ├── src/
│   │   ├── app/           # Next.js pages (App Router)
│   │   ├── components/    # React components
│   │   ├── lib/           # Utilities and API client
│   │   └── types/         # TypeScript types
│   ├── public/            # Static assets
│   └── package.json
├── docker/                # Docker configuration
│   └── init-db.sql       # Database initialization
├── documentation/         # Project documentation
├── scripts/              # Utility scripts
├── docker-compose.yml
└── README.md
```

## Development

### Backend Development
```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run development server
uvicorn app.main:app --reload
```

### Frontend Development
```bash
cd frontend

# Install dependencies
npm install

# Run development server
npm run dev
```

### Database Management
```bash
# Access PostgreSQL
docker exec -it ecotrainer-db psql -U postgres -d ecotrainer

# Run migrations (Alembic)
cd backend
alembic upgrade head

# Create new migration
alembic revision --autogenerate -m "description"
```

## Phase 1 Implementation Status

### ✅ Completed
- [x] Project structure and configuration
- [x] Database schema design
- [x] Core models and schemas
- [x] Docker Compose setup
- [x] API endpoint scaffolding

### 🚧 In Progress
- [ ] Instagram OAuth integration
- [ ] Historical data sync
- [ ] ML prediction model
- [ ] Backend API implementation
- [ ] Frontend dashboard

### 📋 Upcoming
- [ ] Testing suite
- [ ] AWS deployment configuration
- [ ] Documentation

## API Endpoints

### Accounts
- `GET /api/v1/accounts` - List connected accounts
- `POST /api/v1/accounts/connect` - Connect new account (OAuth)
- `GET /api/v1/accounts/{id}` - Get account details
- `POST /api/v1/accounts/{id}/sync` - Sync historical data
- `GET /api/v1/accounts/{id}/stats` - Get engagement statistics
- `DELETE /api/v1/accounts/{id}` - Disconnect account

### Predictions
- `POST /api/v1/predictions/train` - Train ML model
- `POST /api/v1/predictions/schedule` - Get optimal posting times
- `GET /api/v1/predictions/{account_id}/latest` - Get latest predictions

### Scheduled Posts
- `GET /api/v1/content/scheduled` - List scheduled posts
- `POST /api/v1/content/schedule` - Schedule new post
- `GET /api/v1/content/{id}` - Get scheduled post
- `PATCH /api/v1/content/{id}` - Update scheduled post
- `DELETE /api/v1/content/{id}` - Cancel scheduled post

## Environment Variables

See [backend/.env.example](backend/.env.example) for all required environment variables.

Key variables:
- `DATABASE_URL` - PostgreSQL connection string
- `SECRET_KEY` - JWT secret (minimum 32 characters)
- `INSTAGRAM_CLIENT_ID` - Instagram App ID
- `INSTAGRAM_CLIENT_SECRET` - Instagram App Secret
- `OPENAI_API_KEY` - OpenAI API key (Phase 2)
- `ELECTRICITY_MAP_API_KEY` - ElectricityMap API key (Phase 2)

## Testing

```bash
# Backend tests
cd backend
pytest

# Frontend tests
cd frontend
npm test

# Coverage report
pytest --cov=app tests/
```

## Deployment

### AWS Architecture
- **Compute**: ECS Fargate for containerized backend
- **Database**: RDS PostgreSQL
- **Storage**: S3 for media files
- **CDN**: CloudFront for frontend
- **Cache**: ElastiCache Redis

See [documentation/deployment.md](documentation/deployment.md) for detailed deployment instructions.

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For issues, questions, or contributions, please open an issue on GitHub.

## Acknowledgments

- ElectricityMap for carbon intensity data
- Meta for Instagram Graph API
- OpenAI for content generation capabilities

"""
Main FastAPI application entry point.
Sets up the API with CORS, database initialization, and route registration.
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from app.core.config import settings
from app.core.database import init_db, AsyncSessionLocal
from app.api.endpoints import accounts, predictions, scheduled_posts, carbon, jobs, workflow
from app.services.eco_scheduler import EcoScheduler

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.
    Handles startup and shutdown events.
    """
    # Startup
    logger.info("Starting EcoTrainer Studio API...")
    logger.info(f"Environment: {settings.ENVIRONMENT}")
    logger.info(f"Database: {settings.DATABASE_URL}")

    # Initialize database tables
    try:
        init_db()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise

    # Start EcoScheduler for background jobs
    try:
        scheduler = EcoScheduler(AsyncSessionLocal)
        await scheduler.start()
        app.state.scheduler = scheduler
        logger.info("EcoScheduler initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize scheduler: {e}")
        # Continue without scheduler for development
        app.state.scheduler = None

    yield

    # Shutdown
    logger.info("Shutting down EcoTrainer Studio API...")
    if hasattr(app.state, 'scheduler') and app.state.scheduler:
        app.state.scheduler.shutdown()
        logger.info("EcoScheduler shut down successfully")


# Create FastAPI app
app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="AI-powered content scheduler with carbon-aware job execution",
    docs_url="/docs" if settings.is_development else None,
    redoc_url="/redoc" if settings.is_development else None,
    lifespan=lifespan,
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Health check endpoint
@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint with scheduler status."""
    checks = {
        "api": "healthy",
        "scheduler": "unknown"
    }

    if hasattr(app.state, 'scheduler') and app.state.scheduler:
        try:
            scheduler_running = app.state.scheduler.scheduler.running
            checks["scheduler"] = "healthy" if scheduler_running else "stopped"
        except:
            checks["scheduler"] = "unhealthy"
    else:
        checks["scheduler"] = "not_initialized"

    all_healthy = checks["api"] == "healthy" and checks["scheduler"] in ["healthy", "not_initialized"]

    return JSONResponse(
        content={
            "status": "healthy" if all_healthy else "degraded",
            "version": settings.VERSION,
            "environment": settings.ENVIRONMENT,
            "checks": checks
        }
    )


@app.get("/", tags=["Root"])
async def root():
    """
    Root endpoint with API information.
    """
    return {
        "name": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "docs": f"{settings.BACKEND_URL}/docs",
        "health": f"{settings.BACKEND_URL}/health",
    }


# Register API routers
app.include_router(
    accounts.router,
    prefix=f"{settings.API_V1_STR}/accounts",
    tags=["Accounts"],
)

app.include_router(
    predictions.router,
    prefix=f"{settings.API_V1_STR}/predictions",
    tags=["Predictions"],
)

app.include_router(
    scheduled_posts.router,
    prefix=f"{settings.API_V1_STR}/content",
    tags=["Scheduled Posts"],
)

app.include_router(
    carbon.router,
    prefix=f"{settings.API_V1_STR}/carbon",
    tags=["Carbon"],
)

app.include_router(
    jobs.router,
    prefix=f"{settings.API_V1_STR}/jobs",
    tags=["Jobs"],
)

app.include_router(
    workflow.router,
    prefix=f"{settings.API_V1_STR}/workflow",
    tags=["Workflow"],
)


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """
    Catch-all exception handler for unhandled errors.
    """
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error",
            "error": str(exc) if settings.is_development else "An error occurred",
        },
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.is_development,
        log_level=settings.LOG_LEVEL.lower(),
    )

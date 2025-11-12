"""
Application configuration management using Pydantic Settings.
Loads configuration from environment variables with validation.
"""
from typing import List, Optional
from pydantic import Field, PostgresDsn, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    Uses Pydantic for validation and type conversion.
    """

    # Application Settings
    PROJECT_NAME: str = "EcoTrainer Studio"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    SECRET_KEY: str = Field(..., min_length=32)
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    ENVIRONMENT: str = Field(default="development")

    # Database
    DATABASE_URL: PostgresDsn = Field(..., description="PostgreSQL connection string")
    DATABASE_POOL_SIZE: int = 20
    DATABASE_MAX_OVERFLOW: int = 0

    # CORS
    FRONTEND_URL: str = "http://localhost:3000"
    BACKEND_URL: str = "http://localhost:8000"
    ALLOWED_ORIGINS: str = "http://localhost:3000,http://localhost:8000"

    @field_validator("ALLOWED_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: str) -> List[str]:
        """Parse comma-separated CORS origins into a list."""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v

    # Instagram API
    INSTAGRAM_CLIENT_ID: str = Field(..., description="Instagram OAuth client ID")
    INSTAGRAM_CLIENT_SECRET: str = Field(..., description="Instagram OAuth secret")
    INSTAGRAM_REDIRECT_URI: str = Field(
        default="http://localhost:8000/api/auth/instagram/callback"
    )
    INSTAGRAM_API_VERSION: str = "v21.0"
    INSTAGRAM_GRAPH_API_BASE: str = "https://graph.instagram.com"

    # ElectricityMap API (Phase 2)
    ELECTRICITY_MAP_API_KEY: Optional[str] = None
    ELECTRICITY_MAP_REGION: str = "AU-VIC"
    ELECTRICITY_MAP_BASE_URL: str = "https://api.electricitymap.org/v3"

    # OpenAI API (Phase 2)
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_MODEL: str = "gpt-4-turbo-preview"
    OPENAI_MAX_TOKENS: int = 500

    # Redis (Optional)
    REDIS_URL: Optional[str] = None
    REDIS_CACHE_TTL: int = 3600  # 1 hour in seconds

    # AWS Configuration
    AWS_REGION: str = "us-east-1"
    AWS_ACCESS_KEY_ID: Optional[str] = None
    AWS_SECRET_ACCESS_KEY: Optional[str] = None
    AWS_S3_BUCKET: Optional[str] = None

    # Scheduler Settings
    SCHEDULER_TIMEZONE: str = "Australia/Melbourne"
    JOB_EXECUTION_INTERVAL_MINUTES: int = 30
    CARBON_FORECAST_UPDATE_HOURS: int = 6

    # ML Model Settings
    MODEL_TRAINING_MIN_POSTS: int = 50
    MODEL_TRAINING_DAYS_HISTORY: int = 90
    MODEL_CACHE_DIR: str = "models/cache"
    MODEL_VERSION: str = "1.0.0"

    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"

    # Rate Limiting
    INSTAGRAM_API_RATE_LIMIT: int = 200  # calls per hour
    OPENAI_API_RATE_LIMIT: int = 3500  # tokens per minute

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )

    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.ENVIRONMENT.lower() == "production"

    @property
    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.ENVIRONMENT.lower() == "development"


# Global settings instance
settings = Settings()

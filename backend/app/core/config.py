"""Application configuration using environment variables."""

from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Application
    APP_NAME: str = "CodeClash API"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = Field(default=False, description="Debug mode")

    # Database
    DATABASE_URL: str = Field(
        ...,
        description="PostgreSQL database URL",
        example="postgresql://user:password@localhost:5432/codeclash"
    )
    
    # Redis
    REDIS_URL: str = Field(
        default="redis://localhost:6379/0",
        description="Redis connection URL"
    )

    # JWT
    JWT_SECRET_KEY: str = Field(
        ...,
        description="Secret key for JWT token signing"
    )
    JWT_ALGORITHM: str = Field(
        default="HS256",
        description="JWT algorithm"
    )
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(
        default=30,
        description="Access token expiration time in minutes"
    )
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = Field(
        default=7,
        description="Refresh token expiration time in days"
    )

    # OpenAI (Placeholder)
    OPENAI_API_KEY: Optional[str] = Field(
        default=None,
        description="OpenAI API key for AI-driven question generation"
    )
    # Google Gemini (match question generation)
    GEMINI_API_KEY: Optional[str] = Field(
        default=None,
        description="Google Gemini API key for generating match questions"
    )
    # Groq (match question generation, free tier)
    GROQ_API_KEY: Optional[str] = Field(
        default=None,
        description="Groq API key for generating match questions"
    )
    GROQ_MODEL: Optional[str] = Field(
        default=None,
        description="Groq model ID (e.g. llama-3.3-70b-versatile, openai/gpt-oss-20b). Defaults to llama-3.3-70b-versatile if unset."
    )

    # Docker Judge
    DOCKER_SOCKET_URL: str = Field(
        default="unix://var/run/docker.sock",
        description="Docker socket URL for code execution"
    )
    DOCKER_TIMEOUT_SECONDS: int = Field(
        default=30,
        description="Default timeout for code execution"
    )

    # Celery (Task Queue)
    CELERY_BROKER_URL: str = Field(
        default="",
        description="Celery broker URL (defaults to REDIS_URL if not set)"
    )
    CELERY_RESULT_BACKEND: str = Field(
        default="",
        description="Celery result backend URL (defaults to REDIS_URL if not set)"
    )
    CELERY_TASK_SERIALIZER: str = Field(
        default="json",
        description="Task serialization format"
    )
    CELERY_RESULT_SERIALIZER: str = Field(
        default="json",
        description="Result serialization format"
    )
    CELERY_ACCEPT_CONTENT: list[str] = Field(
        default=["json"],
        description="Accepted content types"
    )
    CELERY_TASK_TIME_LIMIT: int = Field(
        default=600,
        description="Task time limit in seconds (10 minutes)"
    )
    CELERY_WORKER_CONCURRENCY: int = Field(
        default=4,
        description="Number of concurrent worker processes"
    )
    
    def get_celery_broker_url(self) -> str:
        """Get Celery broker URL, defaulting to REDIS_URL if not set."""
        return self.CELERY_BROKER_URL or self.REDIS_URL
    
    def get_celery_result_backend(self) -> str:
        """Get Celery result backend URL, defaulting to REDIS_URL if not set."""
        return self.CELERY_RESULT_BACKEND or self.REDIS_URL

    # Socket.io server (matchmaking)
    SOCKET_SERVER_URL: Optional[str] = Field(
        default="http://localhost:3001",
        description="Socket.io server URL for real-time matchmaking"
    )
    SOCKET_SERVER_SECRET: Optional[str] = Field(
        default=None,
        description="Shared secret for Socket server to call internal match-creation API"
    )

    # CORS - can be a JSON array string or comma-separated string
    CORS_ORIGINS: str | list[str] = Field(
        default=["http://localhost:3000", "http://localhost:5173"],
        description="Allowed CORS origins (JSON array or comma-separated)"
    )
    
    def get_cors_origins(self) -> list[str]:
        """Parse CORS_ORIGINS into a list."""
        if isinstance(self.CORS_ORIGINS, list):
            return self.CORS_ORIGINS
        if isinstance(self.CORS_ORIGINS, str):
            import json
            try:
                return json.loads(self.CORS_ORIGINS)
            except (json.JSONDecodeError, ValueError):
                # If not JSON, treat as comma-separated
                return [origin.strip() for origin in self.CORS_ORIGINS.split(',') if origin.strip()]
        return ["http://localhost:3000", "http://localhost:5173"]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


# Global settings instance
settings = Settings()

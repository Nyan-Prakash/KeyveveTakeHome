"""Application configuration and settings."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Database
    postgres_url: str = Field(
        default="postgresql://user:password@localhost:5432/keyveve_dev",
        description="PostgreSQL connection URL",
    )
    redis_url: str = Field(
        default="redis://localhost:6379/0",
        description="Redis connection URL",
    )

    # CORS
    ui_origin: str = Field(
        default="http://localhost:8501",
        description="Allowed CORS origin for UI",
    )

    # JWT Configuration
    jwt_private_key_pem: str = Field(
        default="dummy-private-key-for-tests",
        description="RSA private key for JWT signing (PEM format)",
    )
    jwt_public_key_pem: str = Field(
        default="dummy-public-key-for-tests",
        description="RSA public key for JWT verification (PEM format)",
    )

    # External APIs
    weather_api_key: str = Field(
        default="dummy-weather-api-key-for-tests", description="OpenWeatherMap API key"
    )

    # Performance Settings
    fanout_cap: int = Field(default=4, description="Max concurrent branches in planner")
    airport_buffer_min: int = Field(
        default=120, description="Airport connection buffer in minutes"
    )
    transit_buffer_min: int = Field(
        default=15, description="Transit connection buffer in minutes"
    )

    # Cache TTLs (hours)
    fx_ttl_hours: int = Field(default=24, description="FX rate cache TTL in hours")
    weather_ttl_hours: int = Field(
        default=24, description="Weather data cache TTL in hours"
    )

    # Evaluation
    eval_rng_seed: int = Field(default=42, description="Random seed for evaluation")

    # Timeouts (seconds)
    soft_timeout_s: float = Field(
        default=2.0, description="Soft timeout for tool calls"
    )
    hard_timeout_s: float = Field(
        default=4.0, description="Hard timeout for tool calls"
    )

    # Retry Configuration
    retry_jitter_min_ms: int = Field(
        default=200, description="Minimum retry jitter in milliseconds"
    )
    retry_jitter_max_ms: int = Field(
        default=500, description="Maximum retry jitter in milliseconds"
    )

    # Circuit Breaker
    breaker_failure_threshold: int = Field(
        default=5, description="Failures before circuit breaker opens"
    )
    breaker_timeout_s: int = Field(
        default=60, description="Circuit breaker timeout in seconds"
    )

    # Performance Budgets
    ttfe_budget_ms: int = Field(
        default=800, description="Time to first event budget in milliseconds"
    )
    e2e_p50_budget_s: int = Field(
        default=6, description="End-to-end p50 budget in seconds"
    )
    e2e_p95_budget_s: int = Field(
        default=10, description="End-to-end p95 budget in seconds"
    )


_settings: Settings | None = None


def get_settings() -> Settings:
    """Get application settings singleton."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings

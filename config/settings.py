"""Configuration settings for MatchKit.

All settings are loaded from environment variables (or a .env file).
White-label deployments override branding, scoring, and integration settings
via environment variables or the .env file.
"""
from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # ==================== Branding (white-label) ====================
    app_name: str = "MatchKit"
    app_tagline: str = "Cofounder & Interest Matching Platform"
    support_email: str = ""
    profile_base_url: str = ""  # e.g. "https://myplatform.com"
    profile_url_pattern: str = "/members/{slug}/"  # appended to profile_base_url

    # ==================== Embedding Provider ====================
    azure_openai_endpoint: str = ""
    azure_openai_api_key: str = ""
    azure_openai_embedding_deployment: str = "text-embedding-3-small"
    azure_openai_chat_deployment: str = "gpt-4o"
    embedding_dimension: int = 1536

    # ==================== Database ====================
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/matchkit"

    @property
    def async_database_url(self) -> str:
        """Ensure DATABASE_URL uses asyncpg driver."""
        url = self.database_url
        if url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        return url

    @property
    def sync_database_url(self) -> str:
        """Get synchronous database URL for Alembic migrations."""
        return self.database_url.replace("postgresql+asyncpg", "postgresql+psycopg2")

    # ==================== Email ====================
    mandrill_api_key: str = ""
    sendgrid_api_key: str = ""
    email_from_address: str = ""
    email_from_name: str = ""  # defaults to app_name if empty

    @property
    def resolved_email_from_name(self) -> str:
        return self.email_from_name or self.app_name

    # ==================== CRM Integration (optional) ====================
    crm_enabled: bool = False
    crm_instance_url: str = ""
    crm_client_id: str = ""
    crm_client_secret: str = ""
    crm_api_version: str = "v59.0"

    # ==================== API ====================
    api_key: str = "dev-api-key-change-in-production"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    debug: bool = False
    allowed_origins: str = "http://localhost:3000,http://localhost:8000"

    # ==================== Matching ====================
    min_match_score: float = 0.4
    max_matches_per_email: int = 5
    scoring_config_path: str = "config/scoring.yml"

    # ==================== AI Features ====================
    ai_explanations_enabled: bool = True
    ai_icebreakers_enabled: bool = True
    ai_onboarding_enabled: bool = True
    ai_nudges_enabled: bool = True
    ai_profile_enrichment_enabled: bool = True

    # ==================== Chat ====================
    chat_enabled: bool = True
    chat_max_message_length: int = 2000
    chat_history_limit: int = 100

    # ==================== Scheduler ====================
    weekly_email_day: str = "monday"
    weekly_email_hour: int = 9
    email_frequency: str = "weekly"  # "weekly" or "monthly"
    monthly_email_day: int = 1  # Day of month (1-28)
    match_refresh_frequency: str = "weekly"  # "weekly" or "monthly"
    nudge_frequency: str = "weekly"  # how often to send engagement nudges

    # ==================== Derived Properties ====================

    @property
    def allowed_origins_list(self) -> List[str]:
        """Parse comma-separated origins into a list."""
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]

    model_config = {
        "env_file": ".env",
        "case_sensitive": False,
        "extra": "ignore",
    }


settings = Settings()

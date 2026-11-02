from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "development"
    database_url: str = "postgresql+psycopg://hike:hike@localhost:5432/hike"
    redis_url: str = "redis://localhost:6379/0"

    # Auth
    jwt_secret: str = "dev-only-insecure-secret-change-me"
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 15
    refresh_token_days: int = 7
    cookie_secure: bool = False
    cookie_samesite: str = "lax"
    login_rate_limit: int = 5
    login_rate_window_seconds: int = 900

    # Comma-separated list of allowed origins
    cors_origins: str = "http://localhost:5173,http://localhost:8080"

    # Storage: "local" or "s3"
    storage_backend: str = "local"
    storage_dir: str = "./storage"
    s3_bucket: str = ""
    s3_endpoint_url: str = ""
    s3_region: str = "auto"
    s3_access_key_id: str = ""
    s3_secret_access_key: str = ""
    max_upload_mb: int = 5

    # ML: "onnx" (production) or "sentence-transformers" (reference implementation)
    embedding_backend: str = "onnx"
    model_dir: str = ""  # directory with model.onnx + tokenizer.json; empty = HF cache

    search_cache_ttl_seconds: int = 60
    seed_on_start: bool = False

    # Background jobs. With tasks_eager=true tasks run inline in the API process
    # (tests, and hosts without a worker such as Render's free plan).
    tasks_eager: bool = False
    task_max_retries: int = 3

    # Email: "log" writes messages to the hike.email logger; "smtp" sends them.
    email_backend: str = "log"
    email_from: str = "Hike <no-reply@hike.example>"
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_starttls: bool = True
    # Base URL of the web app, used for links in emails and calendar invites.
    public_app_url: str = "http://localhost:8080"

    # Observability
    log_format: str = "json"  # "json" or "text"
    log_level: str = "INFO"
    sentry_dsn: str = ""
    metrics_token: str = ""  # if set, /metrics requires "Authorization: Bearer <token>"

    # Resume privacy and security
    file_encryption_key: str = ""  # any secret string; empty = derived from jwt_secret
    signed_url_ttl_seconds: int = 300
    malware_scan: str = "heuristic"  # "heuristic" or "clamav" (heuristic checks + ClamAV)
    clamav_host: str = "clamav"
    clamav_port: int = 3310
    parser_isolation: str = "subprocess"  # "subprocess" or "inline"
    parser_timeout_seconds: int = 20
    parser_memory_mb: int = 512
    consent_version: str = "2026-11"
    # Retention: 0 disables a rule.
    retention_unconfirmed_days: int = 7
    retention_old_resume_days: int = 365
    retention_inactive_seeker_days: int = 0

    @field_validator("database_url")
    @classmethod
    def _normalise_db_url(cls, v: str) -> str:
        # Render and Heroku hand out postgres:// or postgresql:// URLs; SQLAlchemy needs the driver.
        if v.startswith("postgres://"):
            v = "postgresql://" + v[len("postgres://") :]
        if v.startswith("postgresql://"):
            v = "postgresql+psycopg://" + v[len("postgresql://") :]
        return v

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    if settings.is_production and settings.jwt_secret.startswith("dev-only"):
        raise RuntimeError("JWT_SECRET must be set in production")
    if settings.malware_scan not in ("heuristic", "clamav"):
        raise RuntimeError("MALWARE_SCAN must be 'heuristic' or 'clamav'")
    return settings


settings = get_settings()

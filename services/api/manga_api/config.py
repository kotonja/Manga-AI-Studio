from functools import lru_cache
import os

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", secrets_dir=os.getenv("SECRETS_DIR"))

    app_env: str = Field(default="development", validation_alias="APP_ENV")
    secrets_dir: str | None = Field(default=None, validation_alias="SECRETS_DIR")
    log_level: str = Field(default="INFO", validation_alias="LOG_LEVEL")
    log_format: str = Field(default="plain", validation_alias="LOG_FORMAT")
    public_base_url: str | None = Field(default=None, validation_alias="PUBLIC_BASE_URL")
    database_url: str = "postgresql+psycopg://manga:manga@localhost:5432/manga_ai"
    redis_url: str = "redis://localhost:6379/0"

    s3_endpoint_url: str = "http://localhost:9000"
    s3_public_url: str = "http://localhost:9000"
    s3_access_key_id: str = "minioadmin"
    s3_secret_access_key: str = "minioadmin"
    s3_bucket_name: str = "manga-ai-dev"
    s3_region: str = "us-east-1"

    api_cors_origins: str = Field(default="http://localhost:3000")
    model_provider: str = "mock"
    openai_api_key: str | None = None
    openai_model: str = "gpt-4.1-mini"
    openai_image_model: str = "gpt-image-1.5"
    comfyui_base_url: str | None = None
    qa_export_preset: str = "draft"
    qa_max_bubble_panel_coverage: float = 0.35
    qa_max_panel_overlap_ratio: float = 0.08
    enable_background_jobs: bool = False
    enable_dev_admin: bool = False
    alpha_auth_enabled: bool = Field(default=False, validation_alias="ALPHA_AUTH_ENABLED")
    alpha_shared_password: str | None = Field(default=None, validation_alias="ALPHA_SHARED_PASSWORD")
    alpha_admin_token: str | None = Field(default=None, validation_alias="ALPHA_ADMIN_TOKEN")
    auth_provider_mode: str = Field(default="local", validation_alias="AUTH_PROVIDER_MODE")
    auth_provider_name: str = Field(default="local", validation_alias="AUTH_PROVIDER_NAME")
    auth_forwarded_user_header: str = Field(default="X-Authenticated-User", validation_alias="AUTH_FORWARDED_USER_HEADER")
    auth_jwks_url: str | None = Field(default=None, validation_alias="AUTH_JWKS_URL")
    auth_issuer: str | None = Field(default=None, validation_alias="AUTH_ISSUER")
    auth_audience: str | None = Field(default=None, validation_alias="AUTH_AUDIENCE")
    default_project_allow_training: bool = Field(default=False, validation_alias="DEFAULT_PROJECT_ALLOW_TRAINING")
    default_project_allow_product_improvement: bool = Field(default=False, validation_alias="DEFAULT_PROJECT_ALLOW_PRODUCT_IMPROVEMENT")
    trusted_hosts: str = Field(default="*", validation_alias="TRUSTED_HOSTS")
    max_request_bytes: int = Field(default=25 * 1024 * 1024, validation_alias="MAX_REQUEST_BYTES")
    upload_max_bytes: int = Field(default=10 * 1024 * 1024, validation_alias="UPLOAD_MAX_BYTES")
    upload_allowed_content_types: str = Field(
        default="image/png,image/jpeg,image/webp",
        validation_alias="UPLOAD_ALLOWED_CONTENT_TYPES",
    )
    rate_limit_enabled: bool = Field(default=False, validation_alias="RATE_LIMIT_ENABLED")
    rate_limit_per_minute: int = Field(default=120, validation_alias="RATE_LIMIT_PER_MINUTE")
    expose_error_details: bool | None = Field(default=None, validation_alias="EXPOSE_ERROR_DETAILS")

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.api_cors_origins.split(",") if origin.strip()]

    @property
    def allowed_hosts(self) -> list[str]:
        return [host.strip() for host in self.trusted_hosts.split(",") if host.strip()]

    @property
    def allowed_upload_content_types(self) -> set[str]:
        return {item.strip().lower() for item in self.upload_allowed_content_types.split(",") if item.strip()}

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() == "production"

    @property
    def should_expose_error_details(self) -> bool:
        if self.expose_error_details is not None:
            return self.expose_error_details
        return not self.is_production


@lru_cache
def get_settings() -> Settings:
    return Settings()

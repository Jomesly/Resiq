from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: Literal["development", "test", "production"] = "development"
    database_url: str = "postgresql+psycopg://resiq:resiq-local-only@127.0.0.1:54329/resiq"
    signing_secret: SecretStr = SecretStr("resiq-development-only-change-before-deploying")
    cors_origins: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]
    public_api_url: str = ""
    storage_backend: Literal["local", "s3"] = "local"
    storage_root: Path = Path("data")
    s3_bucket: str = ""
    s3_endpoint_url: str | None = None
    s3_region: str = "auto"
    ocr_engine: Literal["paddle", "tesseract", "fake"] = "paddle"
    ocr_timeout_s: int = Field(default=90, ge=5, le=600)
    lease_s: int = Field(default=120, ge=15, le=900)
    worker_poll_s: float = Field(default=0.5, ge=0.1, le=10)
    max_attempts: int = Field(default=3, ge=1, le=10)
    max_upload_bytes: int = Field(default=10_485_760, ge=1, le=20_971_520)
    max_image_pixels: int = Field(default=30_000_000, ge=1)
    max_image_side: int = Field(default=2000, ge=500, le=4000)
    image_url_ttl_s: int = Field(default=900, ge=30, le=3600)
    rate_limit_enabled: bool = True
    max_receipts_per_workspace: int = Field(default=1000, ge=1)
    max_pending_per_workspace: int = Field(default=30, ge=1)
    cpu_threads: int = Field(default=2, ge=1, le=16)
    paddle_det_model: str = "PP-OCRv5_mobile_det"
    paddle_rec_model: str = "en_PP-OCRv5_mobile_rec"
    paddle_model_root: Path | None = None

    @model_validator(mode="after")
    def validate_runtime(self):
        if self.lease_s <= self.ocr_timeout_s + 10:
            raise ValueError("LEASE_S must exceed OCR_TIMEOUT_S by more than 10 seconds.")
        if self.ocr_engine == "fake" and self.environment != "test":
            raise ValueError("The fake OCR engine is only allowed in ENVIRONMENT=test.")
        if self.environment == "production":
            key = self.signing_secret.get_secret_value()
            if len(key) < 32 or key.startswith("resiq-development"):
                raise ValueError(
                    "Production needs a private SIGNING_SECRET of at least 32 characters."
                )
            if not self.public_api_url.startswith("https://"):
                raise ValueError("PUBLIC_API_URL must use HTTPS in production.")
        if self.storage_backend == "s3" and not self.s3_bucket:
            raise ValueError("S3_BUCKET is required for S3 storage.")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()

"""Application configuration loaded from environment variables / .env file."""

from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Central configuration for runtime and deployment defaults."""

    APP_HOST: str = "127.0.0.1"
    APP_PORT: int = 8000
    DEBUG: bool = False

    PHISHING_MAIL_API_KEY: str = "change-me-local-key"
    CLASSIFICATION_THRESHOLD: float = 0.5

    MODEL_DIR: str = str(
        Path(__file__).resolve().parent / "ml" / "models" / "secsuite_onnx_quantized"
    )
    PRELOAD_MODELS_ON_STARTUP: bool = False

    GCP_PROJECT_ID: str = "secsuite-phishing-mail-api"
    GCP_REGION: str = "europe-west1"
    SERVICE_NAME: str = "secsuite-phishing-mail-api"
    STAGING_SERVICE_NAME: str = "secsuite-phishing-mail-api-staging"
    AR_REPO: str = "secsuite-phishing-mail-api"
    IMAGE_NAME: str = "secsuite-phishing-mail-api"
    MODEL_BUCKET: str = "secsuite-phishing-mail-api-models-bucket"
    MODEL_ARTIFACTS_PREFIX: str = "secsuite-phishing-mail-api-models"
    GHA_SA_NAME: str = "gha-${GCP_PROJECT_ID}"
    REPO_SLUG: str = "secsuite/phishing-mail-api"

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
        "extra": "ignore",
    }


settings = Settings()

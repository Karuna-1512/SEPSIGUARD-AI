"""Environment-backed application configuration."""
from __future__ import annotations

import os
from pathlib import Path
from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")


def _database_url() -> str:
    value = os.getenv("DATABASE_URL", f"sqlite:///{(PROJECT_ROOT / 'sepsiguard.db').as_posix()}")
    if value.startswith("postgres://"):
        return "postgresql+psycopg://" + value.removeprefix("postgres://")
    if value.startswith("postgresql://"):
        return "postgresql+psycopg://" + value.removeprefix("postgresql://")
    return value


def _float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except ValueError:
        return default


class Settings:
    app_name = os.getenv("APP_NAME", "SepsiGuard AI")
    environment = os.getenv("ENVIRONMENT", "development")
    database_url = _database_url()
    secret_key = os.getenv("SECRET_KEY", "change-this-local-secret-before-deployment")
    session_cookie = "sepsiguard_session"
    session_hours = int(os.getenv("SESSION_HOURS", "12"))
    bootstrap_admin_email = os.getenv("BOOTSTRAP_ADMIN_EMAIL", "").strip().lower()
    bootstrap_admin_password = os.getenv("BOOTSTRAP_ADMIN_PASSWORD", "")
    bootstrap_admin_name = os.getenv("BOOTSTRAP_ADMIN_NAME", "SepsiGuard Administrator")
    model_path = Path(os.getenv("MODEL_PATH", str(PROJECT_ROOT / "models" / "sepsis_gru.keras")))
    scaler_path = Path(os.getenv("SCALER_PATH", str(PROJECT_ROOT / "models" / "scaler.pkl")))
    schema_path = Path(os.getenv("FEATURE_SCHEMA_PATH", str(PROJECT_ROOT / "models" / "feature_schema.json")))
    metrics_path = Path(os.getenv("METRICS_PATH", str(PROJECT_ROOT / "models" / "metrics.json")))
    low_threshold = _float("LOW_THRESHOLD", 0.30)
    high_threshold = _float("HIGH_THRESHOLD", 0.70)
    cors_origins = [x.strip() for x in os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",") if x.strip()]
    max_upload_bytes = int(os.getenv("MAX_UPLOAD_MB", "10")) * 1024 * 1024


settings = Settings()

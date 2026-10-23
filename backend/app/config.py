"""Central settings, read from environment variables (see .env.example)."""
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(REPO_ROOT / ".env")

APP_NAME = "RestockAI"


@dataclass(frozen=True)
class Settings:
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./restockiq.db")
    today: str | None = os.getenv("TODAY") or None
    llm_model: str = os.getenv("LLM_MODEL", "claude-haiku-5-5")
    job_token: str | None = os.getenv("JOB_TOKEN") or None
    data_dir: Path = REPO_ROOT / "data"
    frontend_dist: Path = REPO_ROOT / "frontend" / "dist"


settings = Settings()

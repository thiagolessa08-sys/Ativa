from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")


@dataclass(frozen=True)
class Settings:
    database_url: str = os.getenv("DATABASE_URL", "")
    bi_host: str = os.getenv("BI_HOST", "bi.ssw.inf.br")
    bi_port: int = int(os.getenv("BI_PORT", "5432"))
    bi_database: str = os.getenv("BI_DATABASE", "")
    bi_user: str = os.getenv("BI_USER", "")
    bi_password: str = os.getenv("BI_PASSWORD", "")
    bi2_host: str = os.getenv("BI2_HOST", "transfer.ssw.inf.br")
    bi2_port: int = int(os.getenv("BI2_PORT") or "22")
    bi2_user: str = os.getenv("BI2_USER", "")
    bi2_password: str = os.getenv("BI2_PASSWORD", "")
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-5.5")
    openai_base_url: str = os.getenv("OPENAI_BASE_URL", "")
    anthropic_api_key: str = os.getenv("ANTHROPIC_API_KEY", "")
    anthropic_model: str = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-5")
    query_timeout_ms: int = int(os.getenv("QUERY_TIMEOUT_MS", "20000"))


settings = Settings()

"""Настройки из окружения. Секреты не пишутся в базу и не имеют значений по умолчанию."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    host: str
    port: int
    public_base_url: str
    owner_id: str
    org_name: str
    today: str
    telegram_token: str
    telegram_chat_id: str
    llm_provider: str
    llm_api_key: str
    llm_base_url: str
    llm_model: str
    notion_mode: str
    notion_token: str
    notion_database_id: str
    search_engine: str

    @property
    def db_path(self) -> Path:
        return self.data_dir / "zlata.db"

    @property
    def upload_dir(self) -> Path:
        return self.data_dir / "uploads"

    @property
    def ics_path(self) -> Path:
        return self.data_dir / "calendar.ics"


def load_settings() -> Settings:
    load_dotenv()
    data_dir = Path(os.getenv("DATA_DIR", "./data")).resolve()
    data_dir.mkdir(parents=True, exist_ok=True)
    port = int(os.getenv("PORT", "8090"))
    base = os.getenv("PUBLIC_BASE_URL", f"http://127.0.0.1:{port}").rstrip("/")
    provider = os.getenv("LLM_PROVIDER", "demo").strip().lower() or "demo"
    return Settings(
        data_dir=data_dir,
        host=os.getenv("HOST", "0.0.0.0"),
        port=port,
        public_base_url=base,
        owner_id=os.getenv("OWNER_ID", "owner").strip() or "owner",
        org_name=os.getenv("ORG_NAME", "АНО «Злата»").strip() or "АНО «Злата»",
        today=os.getenv("ASSISTANT_TODAY", date.today().isoformat()),
        telegram_token=os.getenv("TELEGRAM_TOKEN", "").strip(),
        telegram_chat_id=os.getenv("TELEGRAM_CHAT_ID", "").strip(),
        llm_provider=provider,
        llm_api_key=os.getenv("LLM_API_KEY", "").strip(),
        llm_base_url=os.getenv("LLM_BASE_URL", "https://api.openai.com/v1").rstrip("/"),
        llm_model=os.getenv("LLM_MODEL", "gpt-4o-mini").strip(),
        notion_mode=os.getenv("NOTION_MODE", "mirror").strip().lower() or "mirror",
        notion_token=os.getenv("NOTION_TOKEN", "").strip(),
        notion_database_id=os.getenv("NOTION_DATABASE_ID", "").strip(),
        search_engine=os.getenv("SEARCH_ENGINE", "catalog").strip().lower() or "catalog",
    )

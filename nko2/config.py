"""Настройки второй версии. Секреты только из окружения."""

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
    leader_name: str
    today: str
    telegram_token: str
    telegram_chat_id: str
    telegram_channel_id: str
    llm_provider: str
    llm_api_key: str
    llm_base_url: str
    llm_model: str
    yonote_mode: str
    yonote_token: str
    yonote_base_url: str
    yonote_collection_id: str
    vk_token: str
    vk_group_id: str
    imap_host: str
    imap_user: str
    imap_password: str
    search_engine: str
    keywords: str

    @property
    def db_path(self) -> Path:
        return self.data_dir / "zlata2.db"

    @property
    def upload_dir(self) -> Path:
        return self.data_dir / "uploads2"


def load_settings() -> Settings:
    load_dotenv()
    # PORT_V2, чтобы общий .env первой версии не перехватывал порт.
    port = int(os.getenv("PORT_V2", "8091"))
    base = os.getenv("PUBLIC_BASE_URL_V2", f"http://127.0.0.1:{port}").rstrip("/")
    data_dir = Path(os.getenv("DATA_DIR", "./data")).resolve()
    data_dir.mkdir(parents=True, exist_ok=True)
    return Settings(
        data_dir=data_dir,
        host=os.getenv("HOST", "0.0.0.0"),
        port=port,
        public_base_url=base,
        owner_id=os.getenv("OWNER_ID", "owner").strip() or "owner",
        org_name=os.getenv("ORG_NAME", "АНО «Злата»").strip() or "АНО «Злата»",
        leader_name=os.getenv("LEADER_NAME", "Злата").strip() or "Злата",
        today=os.getenv("ASSISTANT_TODAY", date.today().isoformat()),
        telegram_token=os.getenv("TELEGRAM_TOKEN", "").strip(),
        telegram_chat_id=os.getenv("TELEGRAM_CHAT_ID", "").strip(),
        telegram_channel_id=os.getenv("TELEGRAM_CHANNEL_ID", "").strip(),
        llm_provider=os.getenv("LLM_PROVIDER", "demo").strip().lower() or "demo",
        llm_api_key=os.getenv("LLM_API_KEY", "").strip(),
        llm_base_url=os.getenv("LLM_BASE_URL", "https://gigachat.devices.sberbank.ru/api/v1").rstrip("/"),
        llm_model=os.getenv("LLM_MODEL", "GigaChat").strip(),
        yonote_mode=os.getenv("YONOTE_MODE", "mirror").strip().lower() or "mirror",
        yonote_token=os.getenv("YONOTE_TOKEN", "").strip(),
        yonote_base_url=os.getenv("YONOTE_BASE_URL", "https://app.yonote.ru/api").rstrip("/"),
        yonote_collection_id=os.getenv("YONOTE_COLLECTION_ID", "").strip(),
        vk_token=os.getenv("VK_TOKEN", "").strip(),
        vk_group_id=os.getenv("VK_GROUP_ID", "").strip(),
        imap_host=os.getenv("IMAP_HOST", "").strip(),
        imap_user=os.getenv("IMAP_USER", "").strip(),
        imap_password=os.getenv("IMAP_PASSWORD", "").strip(),
        search_engine=os.getenv("SEARCH_ENGINE", "catalog").strip().lower() or "catalog",
        keywords=os.getenv("KEYWORDS", "цифровизация, партнёрство, гранты НКО").strip(),
    )

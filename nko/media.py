"""Голос, фото и вложения. Без ключа файл сохраняется, а распознавание честно пропускается."""

from __future__ import annotations

import base64
from pathlib import Path

import httpx

from nko.config import Settings


def transcribe(path: Path, settings: Settings) -> str:
    if not settings.llm_api_key or settings.llm_provider in {"demo", "gigachat"}:
        return ""
    with path.open("rb") as handle:
        response = httpx.post(
            f"{settings.llm_base_url}/audio/transcriptions",
            headers={"Authorization": f"Bearer {settings.llm_api_key}"},
            data={"model": "whisper-1"},
            files={"file": (path.name, handle, "application/octet-stream")},
            timeout=60,
        )
    response.raise_for_status()
    return str(response.json().get("text") or "").strip()


def describe_image(path: Path, settings: Settings) -> str:
    sidecar = Path(str(path) + ".caption.txt")
    if sidecar.exists():
        return sidecar.read_text(encoding="utf-8").strip()
    if not settings.llm_api_key or settings.llm_provider != "openai":
        return ""
    payload = {
        "model": settings.llm_model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "Опиши афишу, письмо или страницу по-русски: даты, суммы, названия. Не выдумывай то, чего не видно.",
                    },
                    {"type": "image_url", "image_url": {"url": _data_url(path)}},
                ],
            }
        ],
    }
    response = httpx.post(
        f"{settings.llm_base_url}/chat/completions",
        headers={"Authorization": f"Bearer {settings.llm_api_key}"},
        json=payload,
        timeout=60,
    )
    response.raise_for_status()
    return str(response.json()["choices"][0]["message"]["content"]).strip()


def extract_document(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in {".txt", ".eml", ".md"}:
        return path.read_text(encoding="utf-8", errors="replace")
    if suffix == ".pdf":
        from pypdf import PdfReader

        reader = PdfReader(str(path))
        return "\n".join((page.extract_text() or "") for page in reader.pages).strip()
    raise ValueError(f"Формат {suffix or 'без расширения'} не читаю. Пришлите TXT, EML или PDF.")


def _data_url(path: Path) -> str:
    encoded = base64.standard_b64encode(path.read_bytes()).decode("ascii")
    suffix = path.suffix.lower().lstrip(".") or "jpeg"
    mime = "jpeg" if suffix in {"jpg", "jpeg"} else suffix
    return f"data:image/{mime};base64,{encoded}"

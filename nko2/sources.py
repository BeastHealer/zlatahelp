"""Живые источники, доступные из России. В режиме mirror сеть не вызывается."""

from __future__ import annotations

import imaplib

import httpx

from nko2.config import Settings


def yonote_search(settings: Settings, query: str) -> list[dict]:
    response = httpx.post(
        f"{settings.yonote_base_url}/documents.search",
        headers=_yonote_headers(settings),
        json={"query": query},
        timeout=20,
    )
    response.raise_for_status()
    payload = response.json()
    rows = payload.get("data") or payload.get("documents") or []
    items = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        document = row.get("document") if isinstance(row.get("document"), dict) else row
        items.append(
            {
                "source": "yonote",
                "title": str(document.get("title") or "Документ Yonote"),
                "body": str(document.get("text") or document.get("title") or ""),
                "ok": 1,
                "reason": "",
            }
        )
    return items


def yonote_create(settings: Settings, title: str, body: str) -> str:
    if not settings.yonote_collection_id:
        raise ValueError("пустой YONOTE_COLLECTION_ID")
    response = httpx.post(
        f"{settings.yonote_base_url}/documents.create",
        headers=_yonote_headers(settings),
        json={
            "title": title[:200],
            "text": body[:8000],
            "collectionId": settings.yonote_collection_id,
            "publish": True,
        },
        timeout=30,
    )
    response.raise_for_status()
    data = response.json().get("data") or {}
    return str(data.get("id") or data.get("urlId") or "")


def vk_wall(settings: Settings, message: str) -> str:
    response = httpx.post(
        "https://api.vk.com/method/wall.post",
        data={
            "owner_id": settings.vk_group_id,
            "from_group": 1,
            "message": message[:4000],
            "access_token": settings.vk_token,
            "v": "5.199",
        },
        timeout=20,
    )
    response.raise_for_status()
    payload = response.json()
    if payload.get("error"):
        raise ValueError(str(payload["error"].get("error_msg") or "vk"))
    return str((payload.get("response") or {}).get("post_id") or "")


def telegram_reachable(settings: Settings) -> None:
    response = httpx.get(_telegram_url(settings, "getMe"), timeout=8)
    response.raise_for_status()
    if not response.json().get("ok"):
        raise ValueError("telegram")


def telegram_channel(settings: Settings, message: str) -> str:
    response = httpx.post(
        _telegram_url(settings, "sendMessage"),
        json={"chat_id": settings.telegram_channel_id, "text": message[:4000]},
        timeout=20,
    )
    response.raise_for_status()
    payload = response.json()
    if not payload.get("ok"):
        raise ValueError(str(payload.get("description") or "telegram"))
    return str((payload.get("result") or {}).get("message_id") or "")


def read_imap(settings: Settings, limit: int = 10) -> list[dict]:
    mailbox = imaplib.IMAP4_SSL(settings.imap_host)
    try:
        mailbox.login(settings.imap_user, settings.imap_password)
        mailbox.select("INBOX")
        status, data = mailbox.search(None, "ALL")
        if status != "OK":
            raise RuntimeError(status)
        ids = (data[0] or b"").split()[-limit:]
        items = []
        for number in reversed(ids):
            fetched, payload = mailbox.fetch(number, "(BODY.PEEK[HEADER.FIELDS (SUBJECT FROM)])")
            if fetched != "OK" or not payload:
                continue
            raw = b""
            for part in payload:
                if isinstance(part, tuple):
                    raw += part[1]
            text = raw.decode("utf-8", errors="replace")
            items.append({"source": "mail", "title": "Письмо", "body": " ".join(text.split()), "ok": 1, "reason": ""})
        return items
    finally:
        try:
            mailbox.logout()
        except imaplib.IMAP4.error:
            pass


def _telegram_url(settings: Settings, method: str) -> str:
    return f"https://api.telegram.org/bot{settings.telegram_token}/{method}"


def _yonote_headers(settings: Settings) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {settings.yonote_token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

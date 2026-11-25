"""Открытие страниц каталога и, отдельно, живых адресов, если поиск по сети включён."""

from __future__ import annotations

import httpx

from nko.catalog import resolve
from nko.db import Database
from nko.models import PageResult
from nko.policy import html_to_text


class Browser:
    def __init__(self, db: Database, base_url: str):
        self.db = db
        self.base_url = base_url.rstrip("/")

    def open(self, path: str) -> PageResult:
        url = path if path.startswith("http") else f"{self.base_url}{path}"
        self.db.meta_set("last_url", url)
        if path.startswith("http"):
            return PageResult(ok=False, url=path, reason="Для произвольного адреса нужен SEARCH_ENGINE=web.")
        if path == "/sources/notion/workspace" and self.state()["needs_user"]:
            reason = self.state()["reason"] or "Сессия Notion закрыта."
            return PageResult(ok=False, url=url, title="Notion", needs_user=True, reason=reason)
        page = resolve(path)
        if page is None:
            return PageResult(ok=False, url=url, reason="Этого адреса нет в каталоге источников.")
        return PageResult(
            ok=bool(page.get("ok")),
            url=url,
            title=str(page.get("title") or ""),
            text=str(page.get("text") or ""),
            needs_user=bool(page.get("needs_user")),
            reason=str(page.get("reason") or ""),
            facts=list(page.get("facts") or []),
        )

    def fetch(self, url: str) -> PageResult:
        self.db.meta_set("last_url", url)
        try:
            response = httpx.get(
                url,
                timeout=12,
                follow_redirects=True,
                headers={"User-Agent": "Zlatahelp/1.0"},
            )
        except httpx.HTTPError as exc:
            return PageResult(ok=False, url=url, reason=f"Сеть не открыла страницу: {exc.__class__.__name__}.")
        if response.status_code >= 400:
            return PageResult(ok=False, url=url, reason=f"Сайт вернул HTTP {response.status_code}.")
        text = html_to_text(response.text)[:4000]
        title = url
        return PageResult(ok=True, url=url, title=title, text=text or "Страница открылась, видимого текста нет.")

    def lock(self, reason: str) -> None:
        self.db.meta_set("browser_needs_user", "1")
        self.db.meta_set("browser_reason", reason)

    def unlock(self) -> None:
        self.db.meta_set("browser_needs_user", "0")
        self.db.meta_set("browser_reason", "")

    def state(self) -> dict:
        return {
            "needs_user": self.db.meta_get("browser_needs_user") == "1",
            "reason": self.db.meta_get("browser_reason"),
            "last_url": self.db.meta_get("last_url"),
        }

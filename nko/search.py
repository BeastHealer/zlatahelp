"""Живой поиск без ключа. Каталог источников при этом не подменяется ответом поисковика."""

from __future__ import annotations

import httpx


def web_snippets(query: str) -> list[dict]:
    try:
        response = httpx.get(
            "https://api.duckduckgo.com/",
            params={"q": query, "format": "json", "no_html": "1", "skip_disambig": "1"},
            timeout=8,
            headers={"User-Agent": "Zlatahelp/1.0"},
        )
        response.raise_for_status()
        data = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        return [{"ok": False, "source_title": "DuckDuckGo", "reason": exc.__class__.__name__}]
    snippets = []
    abstract = str(data.get("AbstractText") or "").strip()
    if abstract:
        snippets.append(
            {
                "ok": True,
                "source_title": str(data.get("AbstractSource") or "DuckDuckGo"),
                "text": abstract,
                "url": str(data.get("AbstractURL") or ""),
            }
        )
    for topic in data.get("RelatedTopics") or []:
        if not isinstance(topic, dict) or not topic.get("Text"):
            continue
        snippets.append(
            {
                "ok": True,
                "source_title": "DuckDuckGo",
                "text": str(topic.get("Text")),
                "url": str(topic.get("FirstURL") or ""),
            }
        )
        if len(snippets) >= 4:
            break
    if not snippets:
        return [{"ok": False, "source_title": "DuckDuckGo", "reason": "по запросу нет короткого ответа"}]
    return snippets

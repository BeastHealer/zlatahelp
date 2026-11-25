"""Сжатие готового отчёта. Цифры источников остаются, даже если модель их выкинула."""

from __future__ import annotations

import uuid

import httpx

from nko.config import Settings


class LlmError(RuntimeError):
    pass


class LlmClient:
    def __init__(self, settings: Settings):
        self.settings = settings

    def rewrite(self, report: str, must_keep: list[str]) -> str:
        instruction = (
            "Сожми отчёт по-русски для руководителя НКО. "
            "Не добавляй фактов. Дословно сохрани фрагменты: " + "; ".join(must_keep)
        )
        if self.settings.llm_provider == "gigachat":
            return self._gigachat(instruction, report)
        return self._openai(instruction, report)

    def _openai(self, instruction: str, report: str) -> str:
        response = httpx.post(
            f"{self.settings.llm_base_url}/chat/completions",
            headers={"Authorization": f"Bearer {self.settings.llm_api_key}"},
            json={
                "model": self.settings.llm_model,
                "temperature": 0,
                "messages": [
                    {"role": "system", "content": instruction},
                    {"role": "user", "content": report},
                ],
            },
            timeout=60,
        )
        response.raise_for_status()
        return str(response.json()["choices"][0]["message"]["content"]).strip()

    def _gigachat(self, instruction: str, report: str) -> str:
        # У сертификата шлюза GigaChat своя цепочка, системное хранилище её часто не содержит.
        token_response = httpx.post(
            "https://ngw.devices.sberbank.ru:9443/api/v2/oauth",
            headers={
                "Authorization": f"Basic {self.settings.llm_api_key}",
                "RqUID": str(uuid.uuid4()),
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data={"scope": "GIGACHAT_API_PERS"},
            timeout=30,
            verify=False,
        )
        token_response.raise_for_status()
        token = token_response.json().get("access_token")
        if not token:
            raise LlmError("GigaChat не вернул access_token")
        response = httpx.post(
            "https://gigachat.devices.sberbank.ru/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "model": self.settings.llm_model or "GigaChat",
                "temperature": 0,
                "messages": [
                    {"role": "system", "content": instruction},
                    {"role": "user", "content": report},
                ],
            },
            timeout=60,
            verify=False,
        )
        response.raise_for_status()
        return str(response.json()["choices"][0]["message"]["content"]).strip()

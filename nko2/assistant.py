"""Поручения второй версии: сводка, отчёт, поиск, посты после «да»."""

from __future__ import annotations

from datetime import date

import httpx

from nko2.catalog import ACTIVITIES, INBOX, OPPORTUNITIES, POSTS
from nko2.config import Settings
from nko2.db import Database
from nko2.models import Incoming, Outbound
from nko2.policy import render_digest, render_opportunities, render_post, render_weekly
from nko2.sources import read_imap, telegram_channel, telegram_reachable, vk_wall, yonote_create, yonote_search
from nko2.textutil import (
    compose,
    detect_skill,
    find_urls,
    is_cancel,
    is_no,
    is_yes,
    normalize,
    now_iso,
    parse_keywords,
    parse_reminder,
    post_kind,
    ru_date,
)


class Assistant:
    def __init__(self, settings: Settings, db: Database, llm=None):
        self.settings = settings
        self.db = db
        self.llm = llm
        self.today = date.fromisoformat(settings.today)
        self._ensure_world()

    def handle(self, message: Incoming) -> list[Outbound]:
        message.user_id = self.settings.owner_id
        text = compose(message)
        if not text.strip():
            return self._emit(None, [Outbound("error", "Не вижу текста, расшифровки, описания фото или вложения.")])
        if is_cancel(text):
            return self.cancel()
        waiting = self.db.active_waiting(message.user_id)
        if waiting:
            self.db.add_event(waiting["id"], message.user_id, "user", text)
            return self._continue(waiting, text)
        return self._new(message, text)

    def cancel(self) -> list[Outbound]:
        user_id = self.settings.owner_id
        task = self.db.active_waiting(user_id)
        if task is None:
            running = [item for item in self.db.tasks_with_status("running") if item["user_id"] == user_id]
            task = running[-1] if running else None
        if task is None:
            return self._emit(None, [Outbound("result", "Активного поручения нет.")])
        for approval in self.db.approvals_for_task(task["id"]):
            if approval["status"] == "pending":
                self.db.mark_approval(approval["id"], "rejected", "")
        self.db.update_task(task["id"], status="cancelled", phase="cancelled", wait_reason="", result="Остановлено владельцем.")
        return self._emit(task["id"], [Outbound("result", f"Остановила «{task['title']}». Неопубликованное пометила как отменённое.")])

    def poll(self) -> list[Outbound]:
        user_id = self.settings.owner_id
        outs: list[Outbound] = []
        for reminder in self.db.due_reminders(user_id, now_iso()):
            self.db.mark_reminder_sent(reminder["id"])
            outs.append(Outbound("result", f"Напоминание: {reminder['text']}"))
        return self._emit(None, outs)

    def recover(self) -> list[Outbound]:
        outs: list[Outbound] = []
        for task in self.db.tasks_with_status("running"):
            approvals = self.db.approvals_for_task(task["id"])
            pending = [item for item in approvals if item["status"] == "pending"]
            sent = [item for item in approvals if item["status"] == "sent"]
            if pending:
                body = pending[0]["payload"].get("body") or pending[0]["payload"].get("telegram") or ""
                self.db.update_task(task["id"], status="waiting_user", phase="wait_approval", wait_reason="Нужно подтверждение.")
                outs.extend(self._emit(task["id"], [Outbound("waiting", f"Действие ещё не выполнялось. Жду «да» или «нет».\n\n{body}")]))
                continue
            if sent:
                self.db.update_task(task["id"], status="done", phase="done", wait_reason="", result=sent[0]["receipt"])
                outs.extend(self._emit(task["id"], [Outbound("result", f"После сбоя вижу квитанцию {sent[0]['receipt']}. Повторно не выполняю.")]))
                continue
            self.db.update_task(task["id"], status="failed", phase="failed", wait_reason="", result="Нет сохранённого черновика.")
            outs.extend(self._emit(task["id"], [Outbound("error", "После сбоя нет черновика. Поручение можно поставить заново.")]))
        return outs

    def snapshot(self) -> dict:
        user_id = self.settings.owner_id
        fresh = self.poll()
        return {
            "org": self.settings.org_name,
            "tasks": self.db.recent_tasks(user_id),
            "events": self.db.recent_events(user_id),
            "draft": self._pending_draft(user_id),
            "memory": self.db.memory_all(user_id),
            "reminders": self.db.pending_reminders(user_id),
            "yonote": self.db.yonote_pages(),
            "inbox": self.db.inbox(),
            "activities": self.db.activities("planned") + self.db.activities("done"),
            "fresh": [{"kind": item.kind, "text": item.text, "task_id": item.task_id} for item in fresh],
        }

    def _new(self, message: Incoming, text: str) -> list[Outbound]:
        skill = detect_skill(text)
        if skill == "weekly":
            return self._weekly(message, text)
        if skill == "post":
            return self._post(message, text)
        if skill == "reminder":
            return self._reminder(message, text)
        if skill == "opportunities":
            return self._opportunities(message, text)
        if skill == "page":
            return self._page(message, text)
        if skill == "digest":
            return self._digest(message, text)
        return self._general(message, text)

    def _continue(self, task: dict, text: str) -> list[Outbound]:
        if task["phase"] == "wait_when" and task["skill"] == "reminder":
            merged = (task["context"].get("query") or "") + "\n" + text
            parsed = parse_reminder(merged, self.today)
            if parsed is None:
                return self._emit(task["id"], [Outbound("waiting", "Всё ещё не вижу день. Например: «завтра в 10».")])
            due, note = parsed
            self.db.add_reminder(task["user_id"], note, due)
            report = f"Напомню {due}: {note}. Сработает один раз."
            self.db.update_task(task["id"], status="done", phase="done", wait_reason="", result=report)
            return self._emit(task["id"], [Outbound("result", report)])
        if task["phase"] != "wait_approval":
            return self._emit(task["id"], [Outbound("waiting", "Задача ждёт вас. Ответьте на вопрос или напишите «стоп».")])
        pending = [item for item in self.db.approvals_for_task(task["id"]) if item["status"] == "pending"]
        if not pending:
            sent = [item for item in self.db.approvals_for_task(task["id"]) if item["status"] == "sent"]
            if sent:
                return self._emit(task["id"], [Outbound("result", f"Уже выполнено, квитанция {sent[0]['receipt']}. Повторно не делаю.")])
            return self._emit(task["id"], [Outbound("waiting", "Не вижу черновика, который ещё можно подтвердить.")])
        if is_no(text):
            self.db.mark_approval(pending[0]["id"], "rejected", "")
            self.db.update_task(task["id"], status="done", phase="done", wait_reason="", result="Владелец отклонил.")
            return self._emit(task["id"], [Outbound("result", "Не записываю и не публикую.")])
        if not is_yes(text):
            if pending[0]["kind"] == "publish":
                return self._revise_post(task, pending[0], text)
            return self._emit(task["id"], [Outbound("waiting", "Нужно «да» или «нет».")])
        return self._emit(task["id"], [self._commit(task, pending[0])])

    def _digest(self, message: Incoming, text: str) -> list[Outbound]:
        task = self._begin(message, text, "Сводка входящих", "digest")
        items = self._live_inbox(text)
        report = render_digest(items)
        if "рутин" in normalize(text) or "входящ" in normalize(text):
            nearest = self._nearest_plan()
            if nearest:
                due = nearest["when_on"] if "T" in nearest["when_on"] else f"{nearest['when_on']}T09:00:00"
                self.db.add_reminder(message.user_id, nearest["title"], due)
                report += f"\n\nБлижайшее поставила в напоминания один раз: {nearest['title']} ({due})."
        if "запиши" in normalize(text):
            closing = report + "\n\nСтраница Yonote ещё не создана. Напишите «да», чтобы записать сводку один раз."
            return self._queue_yonote(task, "Сводка входящих", report, closing)
        self.db.update_task(task["id"], status="done", phase="done", result=report)
        return self._emit(task["id"], [Outbound("result", report)])

    def _weekly(self, message: Incoming, text: str) -> list[Outbound]:
        task = self._begin(message, text, "Еженедельный отчёт", "weekly")
        report = render_weekly(self.db.activities("done"), self.db.activities("planned"))
        title = f"Еженедельный отчёт {ru_date(self.settings.today)}"
        return self._queue_yonote(task, title, report, report + "\n\nСтраница Yonote ещё не создана. Напишите «да», чтобы записать отчёт один раз.")

    def _opportunities(self, message: Incoming, text: str) -> list[Outbound]:
        task = self._begin(message, text, "Поиск возможностей", "opportunities")
        keywords = parse_keywords(text, self.db.memory_get(message.user_id, "keywords", self.settings.keywords))
        self.db.memory_set(message.user_id, "keywords", ", ".join(keywords))
        chosen = [item for item in self.db.opportunities() if _hit(item, keywords)]
        evidence, tokens = render_opportunities(chosen, keywords)
        if self.settings.search_engine == "web" and not self.settings.llm_api_key:
            evidence += "\nЖивой поиск Яндекса не настроен: ключа нет, зарубежный поисковик не вызываю. Выше только открытые карточки."
        evidence = self._polish(evidence, tokens)
        title = "Возможности: " + ", ".join(keywords)
        return self._queue_yonote(
            task,
            title,
            evidence,
            evidence + "\n\nСтраница Yonote ещё не создана. Напишите «да», чтобы записать подборку один раз.",
        )

    def _post(self, message: Incoming, text: str) -> list[Outbound]:
        kind = post_kind(text)
        fact = POSTS[kind]
        task = self._begin(message, text, f"Пост: {kind}", "post")
        telegram, vk = render_post(kind, fact, self.settings.leader_name, self.settings.org_name)
        draft = f"Telegram:\n{telegram}\n\nVK:\n{vk}"
        closing = (
            "Публикация ещё не ушла. Можно прислать исправленный текст: в каналы уйдёт он. "
            "«Да» отправит текущий вариант один раз."
        )
        payload = {"telegram": telegram, "vk": vk, "body": draft, "subject": fact["title"], "kind": kind}
        approval = self.db.create_approval(message.user_id, task["id"], "publish", payload, f"publish|{kind}|{fact['title']}")
        if approval["status"] == "sent":
            report = draft + f"\n\nУже опубликовано, квитанция {approval['receipt']}. Повторно не публикую."
            self.db.update_task(task["id"], status="done", phase="done", result=report)
            return self._emit(task["id"], [Outbound("result", report)])
        full = draft + "\n\n" + closing
        self.db.update_task(task["id"], status="waiting_user", phase="wait_approval", wait_reason="Нужно одобрение публикации.", result="")
        return self._emit(task["id"], [Outbound("waiting", full)])

    def _reminder(self, message: Incoming, text: str) -> list[Outbound]:
        task = self._begin(message, text, "Напоминание", "reminder")
        parsed = parse_reminder(text, self.today)
        if parsed is None:
            self.db.update_task(task["id"], status="waiting_user", phase="wait_when", wait_reason="Нужен день.")
            return self._emit(task["id"], [Outbound("waiting", "Напишите день, например «напомни завтра в 10 о вебинаре».")])
        due, note = parsed
        self.db.add_reminder(message.user_id, note, due)
        report = f"Напомню {due}: {note}. Сработает один раз."
        self.db.update_task(task["id"], status="done", phase="done", result=report)
        return self._emit(task["id"], [Outbound("result", report)])

    def _page(self, message: Incoming, text: str) -> list[Outbound]:
        task = self._begin(message, text, "Страница", "page")
        lines = []
        for url in find_urls(text)[:3]:
            if self.settings.search_engine != "web":
                lines.append(f"{url} не открывала: SEARCH_ENGINE=catalog, произвольные сайты выключены.")
                continue
            try:
                response = httpx.get(url, timeout=12, follow_redirects=True, headers={"User-Agent": "Zlatahelp/2.0"})
                lines.append(f"{url}: HTTP {response.status_code}")
            except httpx.HTTPError as exc:
                lines.append(f"{url} не открылся: {exc.__class__.__name__}.")
        report = "\n".join(lines) or "В сообщении нет адреса."
        self.db.update_task(task["id"], status="done", phase="done", result=report)
        return self._emit(task["id"], [Outbound("result", report)])

    def _general(self, message: Incoming, text: str) -> list[Outbound]:
        task = self._begin(message, text, "Запрос", "general")
        report = (
            f"Я веду рутину {self.settings.org_name}: сводка Yonote, Telegram, VK и почты, "
            "еженедельный отчёт, поиск грантов и мероприятий, напоминания и посты. "
            "В Yonote, Telegram и VK ничего не уходит без отдельного «да»."
        )
        self.db.update_task(task["id"], status="done", phase="done", result=report)
        return self._emit(task["id"], [Outbound("result", report)])

    def _queue_yonote(self, task: dict, title: str, body: str, shown: str) -> list[Outbound]:
        existing = self.db.yonote_by_title(title)
        if existing:
            report = shown + f"\n\nВ Yonote такая страница уже есть, квитанция yonote-{existing['id']}. Вторую не создаю."
            self.db.update_task(task["id"], status="done", phase="done", wait_reason="", result=report)
            return self._emit(task["id"], [Outbound("result", report)])
        approval = self.db.create_approval(
            task["user_id"],
            task["id"],
            "yonote",
            {"title": title, "body": body, "subject": title},
            f"yonote|{title}",
        )
        if approval["status"] == "sent":
            report = shown + f"\n\nУже записано, квитанция {approval['receipt']}. Повторно не создаю."
            self.db.update_task(task["id"], status="done", phase="done", result=report)
            return self._emit(task["id"], [Outbound("result", report)])
        self.db.update_task(task["id"], status="waiting_user", phase="wait_approval", wait_reason="Нужно подтверждение записи в Yonote.", result="")
        return self._emit(task["id"], [Outbound("waiting", shown)])

    def _revise_post(self, task: dict, approval: dict, text: str) -> list[Outbound]:
        cleaned = text.strip()
        if not cleaned:
            return self._emit(task["id"], [Outbound("waiting", "Пустой текст не подставляю. Пришлите исправленное сообщение или «да».")])
        payload = dict(approval["payload"])
        payload["telegram"] = cleaned
        payload["vk"] = cleaned
        payload["body"] = cleaned
        self.db.update_approval_payload(approval["id"], payload)
        shown = (
            f"{cleaned}\n\nЧерновик заменила на ваш текст. Публикация ещё не ушла. "
            "Можно прислать ещё правку или написать «да»."
        )
        self.db.update_task(task["id"], status="waiting_user", phase="wait_approval", wait_reason="Нужно одобрение публикации.", result="")
        return self._emit(task["id"], [Outbound("waiting", shown)])

    def _pending_draft(self, user_id: str) -> dict | None:
        task = self.db.active_waiting(user_id)
        if task is None or task["phase"] != "wait_approval":
            return None
        pending = [item for item in self.db.approvals_for_task(task["id"]) if item["status"] == "pending" and item["kind"] == "publish"]
        if not pending:
            return None
        payload = pending[0]["payload"]
        return {"text": payload.get("telegram") or payload.get("body") or "", "kind": "publish"}

    def _commit(self, task: dict, approval: dict) -> Outbound:
        if approval["status"] == "sent":
            return Outbound("result", f"Уже выполнено, квитанция {approval['receipt']}. Повторно не делаю.")
        payload = approval["payload"]
        try:
            if approval["kind"] == "yonote":
                remote = ""
                if self.settings.yonote_mode == "api":
                    remote = yonote_create(self.settings, payload["title"], payload["body"])
                page = self.db.insert_yonote(payload["title"], payload["body"], remote)
                receipt = f"yonote-{page['id']}"
                message = f"Записала в Yonote один раз, квитанция {receipt}."
            elif approval["kind"] == "publish":
                receipt = f"post-{approval['id']}"
                message = self._publish(payload, receipt)
                if message is None:
                    return Outbound("error", "VK не принял публикацию. Квитанцию не ставлю, можно снова написать «да».")
            else:
                return Outbound("error", "Не знаю, как подтвердить это действие.")
        except (httpx.HTTPError, OSError, ValueError) as exc:
            return Outbound("error", f"Внешний сервис не принял действие ({exc.__class__.__name__}). Квитанцию не ставлю, можно снова написать «да».")
        self.db.mark_approval(approval["id"], "sent", receipt)
        self.db.update_task(task["id"], status="done", phase="done", wait_reason="", result=message)
        return Outbound("result", message)

    def _live_inbox(self, text: str) -> list[dict]:
        items = list(self.db.inbox())
        if self.settings.yonote_mode == "api" and self.settings.yonote_token:
            try:
                items = yonote_search(self.settings, text) + items
            except (httpx.HTTPError, OSError, ValueError) as exc:
                items.append({"source": "yonote", "title": "Yonote", "body": "", "ok": 0, "reason": exc.__class__.__name__})
        if self.settings.imap_host and self.settings.imap_user:
            try:
                items.extend(read_imap(self.settings))
            except (imaplib_error(), OSError) as exc:
                items.append({"source": "mail", "title": "Почта", "body": "", "ok": 0, "reason": exc.__class__.__name__})
        if self.settings.telegram_token:
            try:
                telegram_reachable(self.settings)
            except (httpx.HTTPError, OSError, ValueError):
                items.append(
                    {
                        "source": "telegram",
                        "title": "канал",
                        "body": "",
                        "ok": 0,
                        "reason": "Telegram недоступен, остальные источники разбираю дальше",
                    }
                )
        return items

    def _publish(self, payload: dict, receipt: str) -> str | None:
        vk_on = bool(self.settings.vk_token and self.settings.vk_group_id)
        telegram_on = bool(self.settings.telegram_token and self.settings.telegram_channel_id)
        vk_ok = False
        telegram_ok = False
        if vk_on:
            try:
                vk_wall(self.settings, payload["vk"])
                vk_ok = True
            except (httpx.HTTPError, OSError, ValueError):
                vk_ok = False
        if telegram_on:
            try:
                telegram_channel(self.settings, payload["telegram"])
                telegram_ok = True
            except (httpx.HTTPError, OSError, ValueError):
                telegram_ok = False
        if vk_on and not vk_ok and not telegram_ok:
            return None
        if not vk_on and not telegram_on:
            return f"Опубликовала в Telegram и VK один раз, квитанция {receipt}."
        if vk_on and not vk_ok and telegram_ok:
            return f"VK не принял публикацию. В Telegram опубликовала один раз, квитанция {receipt}."
        if telegram_on and not telegram_ok:
            where = "VK" if vk_ok else "исходящие"
            return f"Telegram недоступен, в канал не отправляла. В {where} опубликовала один раз, квитанция {receipt}."
        delivered = [name for name, ok in (("Telegram", telegram_ok), ("VK", vk_ok)) if ok]
        return f"Опубликовала в {' и '.join(delivered)} один раз, квитанция {receipt}."

    def _nearest_plan(self) -> dict | None:
        today = self.settings.today
        future = [item for item in self.db.activities("planned") if item["when_on"][:10] >= today]
        future.sort(key=lambda item: item["when_on"])
        return future[0] if future else None

    def _polish(self, report: str, tokens: list[str]) -> str:
        if self.settings.llm_provider == "demo" or self.llm is None or not self.settings.llm_api_key:
            return report
        try:
            text = self.llm.rewrite(report, tokens).strip()
        except (httpx.HTTPError, OSError, KeyError, ValueError, IndexError):
            return report
        if not text or any(token not in text for token in tokens):
            return report
        return text

    def _begin(self, message: Incoming, text: str, title: str, skill: str) -> dict:
        task = self.db.create_task(message.user_id, title, skill, "running", "work", {"query": text})
        self.db.add_event(task["id"], message.user_id, "user", text)
        return task

    def _ensure_world(self) -> None:
        if self.db.meta_get("world_ready") == "2":
            return
        for item in INBOX:
            self.db.insert_inbox(item["source"], item["title"], item["body"], item["ok"], item["reason"])
        for item in ACTIVITIES:
            self.db.insert_activity(item["status"], item["when_on"], item["title"], item["detail"])
        for item in OPPORTUNITIES:
            self.db.insert_opportunity(item)
        self.db.meta_set("world_ready", "2")

    def _emit(self, task_id: str | None, items: list[Outbound]) -> list[Outbound]:
        for item in items:
            self.db.add_event(task_id, self.settings.owner_id, item.kind, item.text)
            item.task_id = task_id or ""
        return items


def _hit(item: dict, keywords: list[str]) -> bool:
    haystack = normalize(f"{item['keywords']} {item['title']} {item['source']}")
    return any(word in haystack for word in keywords)


def imaplib_error() -> type[Exception]:
    import imaplib

    return imaplib.IMAP4.error

"""Поручения руководителя НКО: план, источники, подтверждение перед записью наружу."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta

import httpx

from nko.browser import Browser
from nko.calendar_io import render_ics
from nko.catalog import ARTICLES, CONTACTS, CONTRACT, FAILED_GRANT, LETTER_SAMPLE, grants_for
from nko.config import Settings
from nko.db import Database
from nko.llm import LlmClient
from nko.models import Incoming, Outbound
from nko.policy import overlapping, render_contacts, render_grants, render_letter, render_research
from nko.search import web_snippets
from nko.textutil import (
    clock_label,
    compose,
    detect_skill,
    find_contract_number,
    find_large_amounts,
    find_urls,
    is_cancel,
    is_no,
    is_resume,
    is_yes,
    iso_dt,
    next_weekday,
    normalize,
    now_iso,
    parse_ceiling,
    parse_city,
    parse_focus,
    parse_reminder,
    parse_when,
)


class Assistant:
    def __init__(self, settings: Settings, db: Database, browser: Browser, llm: LlmClient | None = None):
        self.settings = settings
        self.db = db
        self.browser = browser
        self.llm = llm
        self.today = date.fromisoformat(settings.today)
        self._ensure_world()

    def handle(self, message: Incoming) -> list[Outbound]:
        user_id = self.settings.owner_id
        message.user_id = user_id
        text = compose(message)
        if not text.strip():
            return self._emit(None, [Outbound("error", "Не вижу текста, расшифровки голоса, описания фото или вложения.")])
        if is_cancel(text):
            return self.cancel(user_id)
        waiting = self.db.active_waiting(user_id)
        if waiting:
            self.db.add_event(waiting["id"], user_id, "user", text)
            return self._continue(waiting, message, text)
        return self._policy_new(message, text)

    def cancel(self, user_id: str | None = None) -> list[Outbound]:
        user_id = user_id or self.settings.owner_id
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
        return self._emit(task["id"], [Outbound("result", f"Остановил задачу «{task['title']}». Незаписанное действие пометил как отменённое.")])

    def poll(self, user_id: str | None = None) -> list[Outbound]:
        user_id = user_id or self.settings.owner_id
        outs: list[Outbound] = []
        for reminder in self.db.due_reminders(user_id, now_iso()):
            self.db.mark_reminder_sent(reminder["id"])
            outs.append(Outbound("result", f"Напоминание: {reminder['text']}"))
        return self._emit(None, outs)

    def recover(self) -> list[Outbound]:
        outs: list[Outbound] = []
        for task in self.db.tasks_with_status("running"):
            self.db.add_event(task["id"], task["user_id"], "progress", "Процесс оборвался. Сверяю шаги и не повторяю уже выполненную запись.")
            approvals = self.db.approvals_for_task(task["id"])
            pending = [item for item in approvals if item["status"] == "pending"]
            sent = [item for item in approvals if item["status"] == "sent"]
            if pending:
                body = pending[0]["payload"].get("body") or ""
                self.db.update_task(task["id"], status="waiting_user", phase="wait_approval", wait_reason="Нужно подтверждение.")
                outs.extend(self._emit(task["id"], [Outbound("waiting", f"Запись ещё не выполнялась. Жду «да» или «нет».\n\n{body}")]))
                continue
            if sent:
                receipt = sent[0]["receipt"]
                self.db.update_task(task["id"], status="done", phase="done", wait_reason="", result=task.get("result") or receipt)
                outs.extend(self._emit(task["id"], [Outbound("result", f"После сбоя вижу квитанцию {receipt}. Повторно не выполняю.")]))
                continue
            self.db.update_task(task["id"], status="failed", phase="failed", wait_reason="", result="Не хватило сохранённого результата.")
            outs.extend(self._emit(task["id"], [Outbound("error", "После сбоя нет ни черновика, ни квитанции. Поручение можно поставить заново.")]))
        return outs

    def snapshot(self, user_id: str | None = None) -> dict:
        user_id = user_id or self.settings.owner_id
        fresh = self.poll(user_id)
        return {
            "org": self.settings.org_name,
            "tasks": self.db.recent_tasks(user_id),
            "events": self.db.recent_events(user_id),
            "memory": self.db.memory_all(user_id),
            "browser": self.browser.state(),
            "reminders": self.db.pending_reminders(user_id),
            "notion": self.db.notion_pages(),
            "calendar": self.db.calendar_events(),
            "contacts": self.db.contacts(),
            "fresh": [{"kind": item.kind, "text": item.text, "task_id": item.task_id} for item in fresh],
        }

    def _policy_new(self, message: Incoming, text: str) -> list[Outbound]:
        skill = detect_skill(text)
        if skill == "grant":
            return self._grant(message, text)
        if skill == "calendar":
            return self._calendar(message, text)
        if skill == "letter":
            return self._letter(message, text)
        if skill == "research":
            return self._research(message, text)
        if skill == "base":
            return self._base(message, text)
        if skill == "page":
            return self._page(message, text)
        if skill == "login":
            return self._login(message, text)
        if skill == "reminder":
            return self._reminder(message, text)
        return self._general(message, text)

    def _continue(self, task: dict, message: Incoming, text: str) -> list[Outbound]:
        phase = task["phase"]
        if phase == "wait_approval":
            return self._continue_approval(task, text)
        if phase == "wait_login":
            return self._continue_login(task, text)
        if phase == "wait_focus":
            merged = (task["context"].get("query") or "") + "\n" + text
            return self._grant(message, merged, task)
        if phase == "wait_when":
            merged = (task["context"].get("query") or "") + "\n" + text
            if task["skill"] == "reminder":
                return self._reminder(message, merged, task)
            return self._calendar(message, merged, task)
        return self._emit(task["id"], [Outbound("waiting", "Задача ещё ждёт вас. Ответьте на вопрос выше или напишите «стоп».")])

    def _grant(self, message: Incoming, text: str, task: dict | None = None) -> list[Outbound]:
        focus = parse_focus(text) or self.db.memory_get(message.user_id, "focus")
        city = parse_city(text) or self.db.memory_get(message.user_id, "city")
        if parse_city(text):
            self.db.memory_set(message.user_id, "city", parse_city(text))
        if parse_focus(text):
            self.db.memory_set(message.user_id, "focus", parse_focus(text))
        ceiling = parse_ceiling(text)
        remembered = self.db.memory_get(message.user_id, "ceiling_rub")
        if ceiling is None and remembered.isdigit():
            ceiling = int(remembered)
        if ceiling is not None:
            self.db.memory_set(message.user_id, "ceiling_rub", str(ceiling))
        context = {"query": text, "focus": focus, "city": city, "ceiling": ceiling, "image_note": message.image_note.strip()}
        if not focus:
            task = self._touch(message, text, task, "Какая тема гранта", "grant", "waiting_user", "wait_focus", context, "Нужна тема: цифровизация, дети, экология или образование.")
            return self._emit(task["id"], [Outbound("waiting", "Не вижу тему. Напишите, например, «цифровизация», «дети» или «экология».")])
        task = self._touch(message, text, task, f"Гранты: {focus}", "grant", "running", "browse", context, "")
        return self._grant_compute(task, focus, city, ceiling, message.image_note.strip())

    def _grant_compute(self, task: dict, focus: str, city: str, ceiling: int | None, image_note: str) -> list[Outbound]:
        progress = [Outbound("progress", f"Ищу гранты по теме «{focus}» и открываю источники по очереди.")]
        opened: list[dict] = []
        failed: list[dict] = []
        for item in grants_for(focus):
            page = self.browser.open(item["path"])
            if page.ok and page.facts:
                opened.append(page.facts[0])
                progress.append(Outbound("progress", f"Открыл {item['source_title']}: {item['title']}."))
            else:
                failed.append({"source_title": item["source_title"], "reason": page.reason or "пустая страница"})
        missed = self.browser.open(FAILED_GRANT["path"])
        failed.append({"source_title": FAILED_GRANT["source_title"], "reason": missed.reason or FAILED_GRANT["reason"]})
        progress.append(Outbound("progress", f"{FAILED_GRANT['source_title']} не открылся: {missed.reason}."))
        evidence, tokens = render_grants(opened, failed, city, ceiling)
        if image_note:
            evidence += f"\nС фото: {image_note}."
        evidence = self._maybe_polish(evidence, tokens)
        title = f"Подборка грантов: {focus}"
        existing = self.db.notion_by_title(title)
        if existing:
            report = evidence + f"\n\nВ Notion такая страница уже есть, квитанция notion-{existing['id']}. Вторую не создаю."
            self.db.update_task(task["id"], status="done", phase="done", wait_reason="", result=report, context={**task["context"], "report": report})
            return self._emit(task["id"], [*progress, Outbound("result", report)])
        closing = "Страница Notion ещё не создана. Напишите «да», чтобы записать подборку один раз."
        report = evidence + "\n\n" + closing
        payload = {"title": title, "body": evidence, "subject": title, "body_preview": evidence}
        payload["body"] = evidence
        approval = self.db.create_approval(task["user_id"], task["id"], "notion", {"title": title, "body": evidence, "subject": title}, f"notion|{title}")
        if approval["status"] == "sent":
            report = evidence + f"\n\nУже записано, квитанция {approval['receipt']}. Повторно не создаю страницу."
            self.db.update_task(task["id"], status="done", phase="done", wait_reason="", result=report)
            return self._emit(task["id"], [*progress, Outbound("result", report)])
        self.db.update_task(task["id"], status="waiting_user", phase="wait_approval", wait_reason="Нужно подтверждение записи в Notion.", result="", context={**task["context"], "report": report})
        return self._emit(task["id"], [*progress, Outbound("waiting", report)])

    def _calendar(self, message: Incoming, text: str, task: dict | None = None) -> list[Outbound]:
        title = "Встреча правления" if "правлен" in normalize(text) else "Встреча"
        slot = parse_when(text, self.today)
        context = {"query": text, "title": title}
        if slot is None:
            task = self._touch(message, text, task, title, "calendar", "waiting_user", "wait_when", context, "Нужен день встречи.")
            return self._emit(task["id"], [Outbound("waiting", "Не вижу день. Напишите, например, «в четверг в 11».")])
        task = self._touch(message, text, task, title, "calendar", "running", "schedule", context, "")
        start, end = slot
        hits = overlapping(self.db.calendar_events(), iso_dt(start), iso_dt(end))
        if hits:
            proposed_start, proposed_end = self._next_free(start)
            hit = hits[0]
            draft = (
                f"Запрошено: {clock_label(start)}.\n"
                f"Это время пересекается с «{hit['title']}» ({hit['start_at'][11:16]}–{hit['end_at'][11:16]}).\n"
                f"Ближайшее свободное: {clock_label(proposed_start)}.\n"
                "В календарь ещё не записал. Напишите «да», чтобы поставить встречу один раз."
            )
        else:
            proposed_start, proposed_end = start, end
            draft = (
                f"Слот свободен: {clock_label(start)}.\n"
                "В календарь ещё не записал. Напишите «да», чтобы поставить встречу один раз."
            )
        payload = {
            "title": title,
            "start": iso_dt(proposed_start),
            "end": iso_dt(proposed_end),
            "place": "уточним",
            "subject": title,
            "body": draft,
        }
        approval = self.db.create_approval(task["user_id"], task["id"], "calendar", payload, f"calendar|{payload['start']}|{title}")
        if approval["status"] == "sent":
            report = draft + f"\n\nУже стоит в календаре, квитанция {approval['receipt']}. Повторно не ставлю."
            self.db.update_task(task["id"], status="done", phase="done", wait_reason="", result=report)
            return self._emit(task["id"], [Outbound("result", report)])
        self.db.update_task(task["id"], status="waiting_user", phase="wait_approval", wait_reason="Нужно подтверждение записи в календарь.", context={**context, "report": draft})
        return self._emit(task["id"], [Outbound("progress", "Сверил календарь с уже поставленными встречами."), Outbound("waiting", draft)])

    def _letter(self, message: Incoming, text: str) -> list[Outbound]:
        raw = message.document_text.strip()
        sample = False
        if not raw:
            raw = LETTER_SAMPLE
            sample = True
        number = find_contract_number(raw) or find_contract_number(text) or "14"
        contract = self.db.contract(number)
        task = self._touch(message, text, None, f"Письмо по договору {number}", "letter", "running", "read", {"query": text}, "")
        if contract is None:
            report = f"Договора {number} нет в базе. Ответ не готовлю, чтобы не выдумать контрагента."
            self.db.update_task(task["id"], status="done", phase="done", result=report)
            return self._emit(task["id"], [Outbound("result", report)])
        amounts = find_large_amounts(raw)
        if not amounts:
            report = "В письме не вижу суммы. Не с чем сравнивать базу."
            self.db.update_task(task["id"], status="done", phase="done", result=report)
            return self._emit(task["id"], [Outbound("result", report)])
        report, draft, tokens = render_letter(amounts[0], contract, self.settings.org_name)
        report = self._maybe_polish(report, tokens)
        if sample:
            report = "Вложения не было, беру учебное письмо контура.\n" + report
        closing = "Письмо ещё не отправлено. Напишите «да», чтобы отправить его один раз."
        payload = {"to": contract["partner"], "subject": f"Договор {number}", "body": draft}
        approval = self.db.create_approval(
            task["user_id"],
            task["id"],
            "email",
            payload,
            f"email|{number}|{amounts[0]}|{contract['amount']}",
        )
        if approval["status"] == "sent":
            done = report + f"\n\nОтвет уже уходил, квитанция {approval['receipt']}. Повторно не отправляю."
            self.db.update_task(task["id"], status="done", phase="done", result=done)
            return self._emit(task["id"], [Outbound("result", done)])
        full = report + "\n\n" + draft + "\n\n" + closing
        self.db.update_task(task["id"], status="waiting_user", phase="wait_approval", wait_reason="Нужно подтверждение отправки письма.", context={"report": full})
        return self._emit(task["id"], [Outbound("progress", "Сверил сумму письма с базой договоров."), Outbound("waiting", full)])

    def _research(self, message: Incoming, text: str) -> list[Outbound]:
        task = self._touch(message, text, None, "Обзор источников", "research", "running", "browse", {"query": text}, "")
        progress = [Outbound("progress", "Открываю страницы по отчётности и не смешиваю их в одну дату.")]
        opened: list[dict] = []
        failed: list[dict] = []
        for article in ARTICLES:
            page = self.browser.open(article["path"])
            if page.ok:
                opened.append({"source_title": article["source_title"], "text": page.text})
                progress.append(Outbound("progress", f"Открыл {article['source_title']}."))
            else:
                failed.append({"source_title": article["source_title"], "reason": page.reason or article.get("reason") or "не открылась"})
        evidence, tokens = render_research(opened, failed)
        if self.settings.search_engine == "web":
            extra = []
            for snippet in web_snippets(text):
                if snippet.get("ok"):
                    extra.append(f"{snippet['source_title']}: {snippet['text']}")
                else:
                    extra.append(f"{snippet['source_title']} не ответил: {snippet.get('reason', 'нет ответа')}.")
            evidence += "\n\nЖивой поиск, отдельно от страниц выше:\n" + "\n".join(extra)
        evidence = self._maybe_polish(evidence, tokens)
        if "notion" in normalize(text) or "запиши" in normalize(text):
            title = "Обзор: отчётность НКО"
            payload = {"title": title, "body": evidence, "subject": title}
            approval = self.db.create_approval(task["user_id"], task["id"], "notion", payload, f"notion|{title}")
            if approval["status"] != "sent":
                report = evidence + "\n\nСтраница Notion ещё не создана. Напишите «да», чтобы записать обзор один раз."
                self.db.update_task(task["id"], status="waiting_user", phase="wait_approval", wait_reason="Нужно подтверждение записи в Notion.", result="")
                return self._emit(task["id"], [*progress, Outbound("waiting", report)])
            evidence += f"\n\nУже записано, квитанция {approval['receipt']}."
        self.db.update_task(task["id"], status="done", phase="done", result=evidence, wait_reason="")
        return self._emit(task["id"], [*progress, Outbound("result", evidence)])

    def _base(self, message: Incoming, text: str) -> list[Outbound]:
        task = self._touch(message, text, None, "Поиск в базе", "base", "running", "query", {"query": text}, "")
        city = parse_city(text)
        value = normalize(text)
        role = ""
        for needle in ("волонт", "бухгалтер", "грант"):
            if needle in value:
                role = needle
                break
        rows = []
        for contact in self.db.contacts():
            if city and city.lower() not in contact["city"].lower():
                continue
            if role and role not in contact["role"].lower():
                continue
            rows.append(contact)
        report = render_contacts(rows)
        self.db.update_task(task["id"], status="done", phase="done", result=report)
        return self._emit(task["id"], [Outbound("progress", "Смотрю базу контактов, это зеркало картотеки Notion."), Outbound("result", report)])

    def _page(self, message: Incoming, text: str) -> list[Outbound]:
        task = self._touch(message, text, None, "Страница из сети", "page", "running", "browse", {"query": text}, "")
        lines = []
        for url in find_urls(text)[:3]:
            if self.settings.search_engine != "web":
                lines.append(f"{url} не открывал: SEARCH_ENGINE=catalog, сеть для произвольных сайтов выключена.")
                continue
            page = self.browser.fetch(url)
            if not page.ok:
                lines.append(f"{url} не открылся: {page.reason}")
                continue
            lines.append(f"{url}\n{page.text[:700]}")
        report = "\n\n".join(lines) if lines else "В сообщении нет адреса."
        self.db.update_task(task["id"], status="done", phase="done", result=report)
        return self._emit(task["id"], [Outbound("result", report)])

    def _login(self, message: Incoming, text: str) -> list[Outbound]:
        self.browser.lock("Нужен вход в Notion. Откройте сессию на сервере и напишите «готово».")
        page = self.browser.open("/sources/notion/login")
        task = self._touch(message, text, None, "Вход в Notion", "login", "waiting_user", "wait_login", {"query": text}, page.reason)
        return self._emit(
            task["id"],
            [Outbound("waiting", "Сессия Notion закрыта. Я остановился на входе и не читаю рабочее пространство, пока вы не напишете «готово».")],
        )

    def _reminder(self, message: Incoming, text: str, task: dict | None = None) -> list[Outbound]:
        parsed = parse_reminder(text, self.today)
        task = self._touch(message, text, task, "Напоминание", "reminder", "running", "schedule", {"query": text}, "")
        if parsed is None:
            self.db.update_task(task["id"], status="waiting_user", phase="wait_when", wait_reason="Нужен день напоминания.")
            return self._emit(task["id"], [Outbound("waiting", "Напишите день, например «напомни завтра в 9 проверить дедлайн».")])
        due, note = parsed
        self.db.add_reminder(message.user_id, note, due)
        report = f"Напомню {due}: {note}. Сработает один раз."
        self.db.update_task(task["id"], status="done", phase="done", result=report)
        return self._emit(task["id"], [Outbound("result", report)])

    def _general(self, message: Incoming, text: str) -> list[Outbound]:
        task = self._touch(message, text, None, "Запрос", "general", "done", "done", {"query": text}, "")
        report = (
            f"Я веду поручения {self.settings.org_name}: гранты и источники, календарь, письма, "
            "контакты, обзор сети и запись в Notion. "
            "Запись и отправка ждут отдельного «да». Можно прислать голос, фото или файл."
        )
        self.db.update_task(task["id"], status="done", phase="done", result=report)
        return self._emit(task["id"], [Outbound("result", report)])

    def _continue_approval(self, task: dict, text: str) -> list[Outbound]:
        pending = [item for item in self.db.approvals_for_task(task["id"]) if item["status"] == "pending"]
        if not pending:
            sent = [item for item in self.db.approvals_for_task(task["id"]) if item["status"] == "sent"]
            if sent:
                return self._emit(task["id"], [Outbound("result", f"Уже выполнено, квитанция {sent[0]['receipt']}. Повторно не делаю.")])
            return self._emit(task["id"], [Outbound("waiting", "Не вижу черновика, который ещё можно подтвердить.")])
        if is_no(text):
            self.db.mark_approval(pending[0]["id"], "rejected", "")
            self.db.update_task(task["id"], status="done", phase="done", wait_reason="", result="Владелец отклонил запись.")
            return self._emit(task["id"], [Outbound("result", "Не записываю и не отправляю.")])
        if not is_yes(text):
            return self._emit(task["id"], [Outbound("waiting", "Нужно «да» или «нет».")])
        outcome = self._commit(task, pending[0])
        return self._emit(task["id"], [outcome])

    def _continue_login(self, task: dict, text: str) -> list[Outbound]:
        if not is_resume(text):
            return self._emit(task["id"], [Outbound("waiting", "Напишите «готово», когда вход в Notion завершён.")])
        self.browser.unlock()
        page = self.browser.open("/sources/notion/workspace")
        report = page.text if page.ok else page.reason
        self.db.update_task(task["id"], status="done", phase="done", wait_reason="", result=report)
        return self._emit(task["id"], [Outbound("result", report)])

    def _commit(self, task: dict, approval: dict) -> Outbound:
        if approval["status"] == "sent":
            return Outbound("result", f"Уже выполнено, квитанция {approval['receipt']}. Повторно не делаю.")
        payload = approval["payload"]
        kind = approval["kind"]
        if kind == "notion":
            remote = ""
            if self.settings.notion_mode == "api":
                try:
                    remote = self._notion_api(payload["title"], payload["body"])
                except (httpx.HTTPError, OSError, KeyError, ValueError) as exc:
                    return Outbound("error", f"Notion не принял страницу ({exc.__class__.__name__}). Квитанцию не ставлю, можно снова написать «да».")
            page = self.db.insert_notion(payload["title"], payload["body"], remote)
            receipt = f"notion-{page['id']}"
            message = f"Записал в Notion один раз, квитанция {receipt}."
        elif kind == "calendar":
            same = [
                event
                for event in self.db.calendar_events()
                if event["title"] == payload["title"] and event["start_at"] == payload["start"] and event["status"] != "cancelled"
            ]
            if same and same[0]["receipt"] not in {"", "pending"}:
                receipt = same[0]["receipt"]
                message = f"В календаре уже есть эта встреча, квитанция {receipt}. Повторно не ставлю."
            else:
                event = self.db.insert_calendar(payload["title"], payload["start"], payload["end"], payload.get("place") or "уточним", "")
                receipt = event["receipt"] or f"cal-{event['id']}"
                if not event["receipt"]:
                    self.db.set_calendar_receipt(event["id"], f"cal-{event['id']}")
                    receipt = f"cal-{event['id']}"
                message = f"Поставил в календарь один раз, квитанция {receipt}."
            self._write_ics()
        elif kind == "email":
            receipt = f"mail-{approval['id']}"
            message = f"Отправил один раз, квитанция {receipt}."
        else:
            return Outbound("error", "Не знаю, как подтвердить это действие.")
        self.db.mark_approval(approval["id"], "sent", receipt)
        self.db.update_task(task["id"], status="done", phase="done", wait_reason="", result=message)
        return Outbound("result", message)

    def _notion_api(self, title: str, body: str) -> str:
        if not self.settings.notion_token or not self.settings.notion_database_id:
            raise ValueError("пустые NOTION_TOKEN или NOTION_DATABASE_ID")
        chunk = body[:1900]
        response = httpx.post(
            "https://api.notion.com/v1/pages",
            headers={
                "Authorization": f"Bearer {self.settings.notion_token}",
                "Notion-Version": "2022-06-28",
                "Content-Type": "application/json",
            },
            json={
                "parent": {"database_id": self.settings.notion_database_id},
                "properties": {"Name": {"title": [{"text": {"content": title[:200]}}]}},
                "children": [
                    {
                        "object": "block",
                        "type": "paragraph",
                        "paragraph": {"rich_text": [{"type": "text", "text": {"content": chunk}}]},
                    }
                ],
            },
            timeout=30,
        )
        response.raise_for_status()
        return str(response.json().get("id") or "")

    def _next_free(self, start: datetime) -> tuple[datetime, datetime]:
        cursor = datetime.combine(start.date() + timedelta(days=1), time(11, 0))
        events = self.db.calendar_events()
        for _ in range(21):
            end = cursor + timedelta(hours=1)
            if not overlapping(events, iso_dt(cursor), iso_dt(end)):
                return cursor, end
            cursor += timedelta(days=1)
        end = cursor + timedelta(hours=1)
        return cursor, end

    def _maybe_polish(self, report: str, tokens: list[str]) -> str:
        if self.settings.llm_provider == "demo" or self.llm is None or not self.settings.llm_api_key:
            return report
        try:
            text = self.llm.rewrite(report, tokens).strip()
        except (httpx.HTTPError, OSError, KeyError, ValueError, IndexError):
            return report
        if not text or any(token not in text for token in tokens):
            return report
        return text

    def _touch(self, message: Incoming, text: str, task: dict | None, title: str, skill: str, status: str, phase: str, context: dict, wait_reason: str) -> dict:
        if task is None:
            created = self.db.create_task(message.user_id, title, skill, status, phase, context, wait_reason)
            self.db.add_event(created["id"], message.user_id, "user", text)
            return created
        return self.db.update_task(task["id"], title=title, skill=skill, status=status, phase=phase, context=context, wait_reason=wait_reason, result="")

    def _ensure_world(self) -> None:
        if self.db.meta_get("world_ready") == "1":
            return
        thursday = next_weekday(self.today, 3)
        friday = next_weekday(self.today, 4)
        self.db.insert_calendar(
            "Попечительский совет",
            iso_dt(datetime.combine(thursday, time(10, 0))),
            iso_dt(datetime.combine(thursday, time(12, 0))),
            "офис",
            "seed",
        )
        self.db.insert_calendar(
            "Сверка с бухгалтером",
            iso_dt(datetime.combine(friday, time(15, 0))),
            iso_dt(datetime.combine(friday, time(16, 0))),
            "онлайн",
            "seed",
        )
        for contact in CONTACTS:
            self.db.insert_contact(contact["name"], contact["city"], contact["role"], contact["phone"])
        self.db.upsert_contract(CONTRACT["number"], CONTRACT["partner"], CONTRACT["amount"], CONTRACT["title"])
        self.db.meta_set("world_ready", "1")
        self._write_ics()

    def _write_ics(self) -> None:
        self.settings.ics_path.write_text(render_ics(self.db.calendar_events(), self.settings.org_name), encoding="utf-8")

    def _emit(self, task_id: str | None, items: list[Outbound]) -> list[Outbound]:
        user_id = self.settings.owner_id
        for item in items:
            self.db.add_event(task_id, user_id, item.kind, item.text)
            item.task_id = task_id or ""
        return items

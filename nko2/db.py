"""Состояние второй версии: задачи, Yonote, входящие, подтверждения."""

from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from pathlib import Path

from nko2.textutil import now_iso


def new_id() -> str:
    return uuid.uuid4().hex[:12]


class Database:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init()

    def _init(self) -> None:
        with self._lock:
            self._conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS tasks (
                    id TEXT PRIMARY KEY, user_id TEXT NOT NULL, title TEXT NOT NULL, skill TEXT NOT NULL,
                    status TEXT NOT NULL, phase TEXT NOT NULL, wait_reason TEXT, result TEXT,
                    context_json TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT, user_id TEXT NOT NULL,
                    kind TEXT NOT NULL, text TEXT NOT NULL, created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS memory (
                    user_id TEXT NOT NULL, key TEXT NOT NULL, value TEXT NOT NULL, updated_at TEXT NOT NULL,
                    PRIMARY KEY (user_id, key)
                );
                CREATE TABLE IF NOT EXISTS approvals (
                    id TEXT PRIMARY KEY, task_id TEXT NOT NULL, user_id TEXT NOT NULL, kind TEXT NOT NULL,
                    payload_json TEXT NOT NULL, status TEXT NOT NULL, idempotency_key TEXT NOT NULL UNIQUE,
                    receipt TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS reminders (
                    id TEXT PRIMARY KEY, user_id TEXT NOT NULL, text TEXT NOT NULL, due_at TEXT NOT NULL,
                    status TEXT NOT NULL, created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS inbox (
                    id TEXT PRIMARY KEY, source TEXT NOT NULL, title TEXT NOT NULL, body TEXT NOT NULL,
                    ok INTEGER NOT NULL, reason TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS activities (
                    id TEXT PRIMARY KEY, status TEXT NOT NULL, when_on TEXT NOT NULL, title TEXT NOT NULL, detail TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS opportunities (
                    id TEXT PRIMARY KEY, source TEXT NOT NULL, title TEXT NOT NULL, amount INTEGER NOT NULL,
                    deadline TEXT NOT NULL, keywords TEXT NOT NULL, ok INTEGER NOT NULL, reason TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS yonote_pages (
                    id TEXT PRIMARY KEY, title TEXT NOT NULL, body TEXT NOT NULL, remote_id TEXT NOT NULL, created_at TEXT NOT NULL
                );
                """
            )
            self._conn.commit()

    def meta_get(self, key: str, default: str = "") -> str:
        with self._lock:
            row = self._conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
        return default if row is None else str(row["value"])

    def meta_set(self, key: str, value: str) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO meta(key, value) VALUES(?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, value),
            )
            self._conn.commit()

    def add_event(self, task_id: str | None, user_id: str, kind: str, text: str) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO events(task_id, user_id, kind, text, created_at) VALUES(?, ?, ?, ?, ?)",
                (task_id, user_id, kind, text, now_iso()),
            )
            self._conn.commit()

    def create_task(self, user_id: str, title: str, skill: str, status: str, phase: str, context: dict, wait_reason: str = "") -> dict:
        task_id = new_id()
        stamp = now_iso()
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO tasks(id, user_id, title, skill, status, phase, wait_reason, result, context_json, created_at, updated_at)
                VALUES(?, ?, ?, ?, ?, ?, ?, '', ?, ?, ?)
                """,
                (task_id, user_id, title[:120], skill, status, phase, wait_reason, json.dumps(context, ensure_ascii=False), stamp, stamp),
            )
            self._conn.commit()
        return self.get_task(task_id)

    def get_task(self, task_id: str) -> dict:
        with self._lock:
            row = self._conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        if row is None:
            raise KeyError(task_id)
        return self._task(row)

    def update_task(self, task_id: str, **fields) -> dict:
        current = self.get_task(task_id)
        if "context" in fields:
            current["context"] = fields.pop("context")
        current.update(fields)
        with self._lock:
            self._conn.execute(
                """
                UPDATE tasks SET title=?, skill=?, status=?, phase=?, wait_reason=?, result=?, context_json=?, updated_at=?
                WHERE id=?
                """,
                (
                    current["title"], current["skill"], current["status"], current["phase"],
                    current.get("wait_reason") or "", current.get("result") or "",
                    json.dumps(current["context"], ensure_ascii=False), now_iso(), task_id,
                ),
            )
            self._conn.commit()
        return self.get_task(task_id)

    def active_waiting(self, user_id: str) -> dict | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM tasks WHERE user_id=? AND status='waiting_user' ORDER BY updated_at DESC LIMIT 1",
                (user_id,),
            ).fetchone()
        return None if row is None else self._task(row)

    def tasks_with_status(self, status: str) -> list[dict]:
        with self._lock:
            rows = self._conn.execute("SELECT * FROM tasks WHERE status=? ORDER BY updated_at", (status,)).fetchall()
        return [self._task(row) for row in rows]

    def recent_tasks(self, user_id: str, limit: int = 20) -> list[dict]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM tasks WHERE user_id=? ORDER BY updated_at DESC LIMIT ?",
                (user_id, limit),
            ).fetchall()
        return [self._task(row) for row in rows]

    def recent_events(self, user_id: str, limit: int = 80) -> list[dict]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM events WHERE user_id=? ORDER BY id DESC LIMIT ?",
                (user_id, limit),
            ).fetchall()
        return [dict(row) for row in reversed(rows)]

    def memory_get(self, user_id: str, key: str, default: str = "") -> str:
        with self._lock:
            row = self._conn.execute("SELECT value FROM memory WHERE user_id=? AND key=?", (user_id, key)).fetchone()
        return default if row is None else str(row["value"])

    def memory_set(self, user_id: str, key: str, value: str) -> None:
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO memory(user_id, key, value, updated_at) VALUES(?, ?, ?, ?)
                ON CONFLICT(user_id, key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at
                """,
                (user_id, key, value, now_iso()),
            )
            self._conn.commit()

    def memory_all(self, user_id: str) -> list[dict]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT key, value, updated_at FROM memory WHERE user_id=? ORDER BY key",
                (user_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def create_approval(self, user_id: str, task_id: str, kind: str, payload: dict, idempotency_key: str) -> dict:
        with self._lock:
            row = self._conn.execute("SELECT * FROM approvals WHERE idempotency_key=?", (idempotency_key,)).fetchone()
            stamp = now_iso()
            if row is not None and row["status"] == "rejected":
                self._conn.execute(
                    """
                    UPDATE approvals SET task_id=?, user_id=?, kind=?, payload_json=?, status='pending', receipt='', updated_at=?
                    WHERE id=?
                    """,
                    (task_id, user_id, kind, json.dumps(payload, ensure_ascii=False), stamp, row["id"]),
                )
                self._conn.commit()
                fresh = self._conn.execute("SELECT * FROM approvals WHERE id=?", (row["id"],)).fetchone()
                return self._approval(fresh)
            if row is not None:
                return self._approval(row)
            approval_id = new_id()
            self._conn.execute(
                """
                INSERT INTO approvals(id, task_id, user_id, kind, payload_json, status, idempotency_key, receipt, created_at, updated_at)
                VALUES(?, ?, ?, ?, ?, 'pending', ?, '', ?, ?)
                """,
                (approval_id, task_id, user_id, kind, json.dumps(payload, ensure_ascii=False), idempotency_key, stamp, stamp),
            )
            self._conn.commit()
            fresh = self._conn.execute("SELECT * FROM approvals WHERE id=?", (approval_id,)).fetchone()
        return self._approval(fresh)

    def approvals_for_task(self, task_id: str) -> list[dict]:
        with self._lock:
            rows = self._conn.execute("SELECT * FROM approvals WHERE task_id=? ORDER BY created_at", (task_id,)).fetchall()
        return [self._approval(row) for row in rows]

    def count_approvals(self, status: str) -> int:
        with self._lock:
            row = self._conn.execute("SELECT COUNT(*) AS n FROM approvals WHERE status=?", (status,)).fetchone()
        return int(row["n"])

    def approvals_with_status(self, status: str) -> list[dict]:
        with self._lock:
            rows = self._conn.execute("SELECT * FROM approvals WHERE status=? ORDER BY created_at", (status,)).fetchall()
        return [self._approval(row) for row in rows]

    def get_approval(self, approval_id: str) -> dict:
        with self._lock:
            row = self._conn.execute("SELECT * FROM approvals WHERE id=?", (approval_id,)).fetchone()
        if row is None:
            raise KeyError(approval_id)
        return self._approval(row)

    def update_approval_payload(self, approval_id: str, payload: dict) -> dict:
        with self._lock:
            self._conn.execute(
                "UPDATE approvals SET payload_json=?, updated_at=? WHERE id=?",
                (json.dumps(payload, ensure_ascii=False), now_iso(), approval_id),
            )
            self._conn.commit()
        return self.get_approval(approval_id)

    def mark_approval(self, approval_id: str, status: str, receipt: str = "") -> dict:
        with self._lock:
            self._conn.execute(
                "UPDATE approvals SET status=?, receipt=?, updated_at=? WHERE id=?",
                (status, receipt, now_iso(), approval_id),
            )
            self._conn.commit()
        return self.get_approval(approval_id)

    def add_reminder(self, user_id: str, text: str, due_at: str) -> dict:
        reminder_id = new_id()
        with self._lock:
            self._conn.execute(
                "INSERT INTO reminders(id, user_id, text, due_at, status, created_at) VALUES(?, ?, ?, ?, 'pending', ?)",
                (reminder_id, user_id, text, due_at, now_iso()),
            )
            self._conn.commit()
            row = self._conn.execute("SELECT * FROM reminders WHERE id=?", (reminder_id,)).fetchone()
        return dict(row)

    def due_reminders(self, user_id: str, now: str) -> list[dict]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM reminders WHERE user_id=? AND status='pending' AND due_at<=? ORDER BY due_at",
                (user_id, now),
            ).fetchall()
        return [dict(row) for row in rows]

    def mark_reminder_sent(self, reminder_id: str) -> None:
        with self._lock:
            self._conn.execute("UPDATE reminders SET status='sent' WHERE id=?", (reminder_id,))
            self._conn.commit()

    def pending_reminders(self, user_id: str) -> list[dict]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM reminders WHERE user_id=? AND status='pending' ORDER BY due_at",
                (user_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def force_reminder_due(self, reminder_id: str, due_at: str) -> None:
        with self._lock:
            self._conn.execute("UPDATE reminders SET due_at=? WHERE id=?", (due_at, reminder_id))
            self._conn.commit()

    def insert_inbox(self, source: str, title: str, body: str, ok: int, reason: str) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO inbox(id, source, title, body, ok, reason) VALUES(?, ?, ?, ?, ?, ?)",
                (new_id(), source, title, body, ok, reason),
            )
            self._conn.commit()

    def inbox(self) -> list[dict]:
        with self._lock:
            rows = self._conn.execute("SELECT * FROM inbox ORDER BY source, title").fetchall()
        return [dict(row) for row in rows]

    def insert_activity(self, status: str, when_on: str, title: str, detail: str) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO activities(id, status, when_on, title, detail) VALUES(?, ?, ?, ?, ?)",
                (new_id(), status, when_on, title, detail),
            )
            self._conn.commit()

    def activities(self, status: str) -> list[dict]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM activities WHERE status=? ORDER BY when_on",
                (status,),
            ).fetchall()
        return [dict(row) for row in rows]

    def insert_opportunity(self, item: dict) -> None:
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO opportunities(id, source, title, amount, deadline, keywords, ok, reason)
                VALUES(?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (new_id(), item["source"], item["title"], item["amount"], item["deadline"], item["keywords"], item["ok"], item["reason"]),
            )
            self._conn.commit()

    def opportunities(self) -> list[dict]:
        with self._lock:
            rows = self._conn.execute("SELECT * FROM opportunities ORDER BY deadline").fetchall()
        return [dict(row) for row in rows]

    def insert_yonote(self, title: str, body: str, remote_id: str = "") -> dict:
        with self._lock:
            row = self._conn.execute("SELECT * FROM yonote_pages WHERE title=?", (title,)).fetchone()
            if row is not None:
                return dict(row)
            page_id = new_id()
            self._conn.execute(
                "INSERT INTO yonote_pages(id, title, body, remote_id, created_at) VALUES(?, ?, ?, ?, ?)",
                (page_id, title, body, remote_id, now_iso()),
            )
            self._conn.commit()
            fresh = self._conn.execute("SELECT * FROM yonote_pages WHERE id=?", (page_id,)).fetchone()
        return dict(fresh)

    def yonote_by_title(self, title: str) -> dict | None:
        with self._lock:
            row = self._conn.execute("SELECT * FROM yonote_pages WHERE title=?", (title,)).fetchone()
        return None if row is None else dict(row)

    def yonote_pages(self) -> list[dict]:
        with self._lock:
            rows = self._conn.execute("SELECT * FROM yonote_pages ORDER BY created_at").fetchall()
        return [dict(row) for row in rows]

    def yonote_page(self, page_id: str) -> dict | None:
        with self._lock:
            row = self._conn.execute("SELECT * FROM yonote_pages WHERE id=?", (page_id,)).fetchone()
        return None if row is None else dict(row)

    @staticmethod
    def _task(row: sqlite3.Row) -> dict:
        data = dict(row)
        data["context"] = json.loads(data.pop("context_json") or "{}")
        return data

    @staticmethod
    def _approval(row: sqlite3.Row) -> dict:
        data = dict(row)
        data["payload"] = json.loads(data.pop("payload_json") or "{}")
        return data

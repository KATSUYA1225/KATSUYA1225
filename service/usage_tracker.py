from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import aiosqlite

DB_PATH = Path("data/usage.db")

# トークン単価（JPY / 1K tokens）@ ¥150/$
# Opus 4.7:  $15/M input, $75/M output
# Sonnet 4.6: $3/M input, $15/M output
# Haiku 4.5:  $0.8/M input, $4/M output
RATES: dict[str, dict[str, float]] = {
    "claude-opus-4-7":           {"input": 2.25,  "output": 11.25},
    "claude-sonnet-4-6":         {"input": 0.45,  "output": 2.25},
    "claude-haiku-4-5-20251001": {"input": 0.12,  "output": 0.60},
}
DEFAULT_RATE = {"input": 0.45, "output": 2.25}


def calc_cost_jpy(model: str, tokens_input: int, tokens_output: int) -> float:
    rate = RATES.get(model, DEFAULT_RATE)
    return (tokens_input / 1000) * rate["input"] + (tokens_output / 1000) * rate["output"]


class UsageTracker:
    def __init__(self, db_path: Path = DB_PATH) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    async def init(self) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS companies (
                    company_id TEXT PRIMARY KEY,
                    config_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    task_id TEXT PRIMARY KEY,
                    company_id TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'queued',
                    task_text TEXT NOT NULL,
                    result_text TEXT,
                    tokens_input INTEGER DEFAULT 0,
                    tokens_output INTEGER DEFAULT 0,
                    cost_jpy REAL DEFAULT 0.0,
                    error_text TEXT,
                    created_at TEXT NOT NULL,
                    completed_at TEXT
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id TEXT PRIMARY KEY,
                    email TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    plan TEXT DEFAULT 'starter',
                    stripe_customer_id TEXT,
                    stripe_subscription_id TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT
                )
            """)
            await db.commit()

    # ── User CRUD ───────────────────────────────────────────────

    async def create_user(self, user_id: str, email: str, password_hash: str) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """INSERT INTO users (user_id, email, password_hash, plan, created_at)
                   VALUES (?, ?, ?, 'starter', ?)""",
                (user_id, email, password_hash, datetime.utcnow().isoformat()),
            )
            await db.commit()

    async def get_user_by_email(self, email: str) -> dict[str, Any] | None:
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT user_id, email, password_hash, plan, created_at FROM users WHERE email = ?",
                (email,),
            ) as cur:
                row = await cur.fetchone()
                if row is None:
                    return None
                return {"user_id": row[0], "email": row[1], "password_hash": row[2],
                        "plan": row[3], "created_at": row[4]}

    async def get_user_by_id(self, user_id: str) -> dict[str, Any] | None:
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT user_id, email, plan, created_at FROM users WHERE user_id = ?",
                (user_id,),
            ) as cur:
                row = await cur.fetchone()
                if row is None:
                    return None
                return {"user_id": row[0], "email": row[1], "plan": row[2], "created_at": row[3]}

    async def update_user_plan(self, user_id: str, plan: str) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE users SET plan = ?, updated_at = ? WHERE user_id = ?",
                (plan, datetime.utcnow().isoformat(), user_id),
            )
            await db.commit()

    async def email_exists(self, email: str) -> bool:
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT 1 FROM users WHERE email = ?", (email,)
            ) as cur:
                return await cur.fetchone() is not None

    async def register_company(self, company_id: str, config: dict[str, Any]) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT OR REPLACE INTO companies (company_id, config_json, created_at) VALUES (?, ?, ?)",
                (company_id, json.dumps(config, ensure_ascii=False), datetime.utcnow().isoformat()),
            )
            await db.commit()

    async def company_exists(self, company_id: str) -> bool:
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT 1 FROM companies WHERE company_id = ?", (company_id,)
            ) as cur:
                return await cur.fetchone() is not None

    async def get_company_config(self, company_id: str) -> dict[str, Any] | None:
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT config_json, created_at FROM companies WHERE company_id = ?", (company_id,)
            ) as cur:
                row = await cur.fetchone()
                if row is None:
                    return None
                data = json.loads(row[0])
                data["_created_at"] = row[1]
                return data

    async def create_task(self, task_id: str, company_id: str, task_text: str) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """INSERT INTO tasks (task_id, company_id, status, task_text, created_at)
                   VALUES (?, ?, 'queued', ?, ?)""",
                (task_id, company_id, task_text, datetime.utcnow().isoformat()),
            )
            await db.commit()

    async def update_task_status(self, task_id: str, status: str) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE tasks SET status = ? WHERE task_id = ?", (status, task_id)
            )
            await db.commit()

    async def complete_task(
        self,
        task_id: str,
        result_text: str,
        tokens_input: int = 0,
        tokens_output: int = 0,
        cost_jpy: float = 0.0,
    ) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """UPDATE tasks SET status='completed', result_text=?, tokens_input=?,
                   tokens_output=?, cost_jpy=?, completed_at=? WHERE task_id=?""",
                (result_text, tokens_input, tokens_output, cost_jpy,
                 datetime.utcnow().isoformat(), task_id),
            )
            await db.commit()

    async def fail_task(self, task_id: str, error: str) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """UPDATE tasks SET status='failed', error_text=?, completed_at=?
                   WHERE task_id=?""",
                (error, datetime.utcnow().isoformat(), task_id),
            )
            await db.commit()

    async def get_task(self, task_id: str) -> dict[str, Any] | None:
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                """SELECT task_id, company_id, status, task_text, result_text,
                          tokens_input, tokens_output, cost_jpy, error_text,
                          created_at, completed_at
                   FROM tasks WHERE task_id = ?""",
                (task_id,),
            ) as cur:
                row = await cur.fetchone()
                if row is None:
                    return None
                cols = ["task_id", "company_id", "status", "task_text", "result_text",
                        "tokens_input", "tokens_output", "cost_jpy", "error_text",
                        "created_at", "completed_at"]
                return dict(zip(cols, row))

    async def get_usage(self, company_id: str, month: str) -> dict[str, Any]:
        prefix = month + "%"  # e.g. "2026-05%"
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                """SELECT COUNT(*), SUM(tokens_input), SUM(tokens_output), SUM(cost_jpy)
                   FROM tasks
                   WHERE company_id=? AND status='completed' AND created_at LIKE ?""",
                (company_id, prefix),
            ) as cur:
                row = await cur.fetchone()
        total_tasks = row[0] or 0
        total_input = row[1] or 0
        total_output = row[2] or 0
        total_cost = row[3] or 0.0
        return {
            "company_id": company_id,
            "period": month,
            "total_tasks": total_tasks,
            "total_tokens_input": total_input,
            "total_tokens_output": total_output,
            "total_cost_jpy": round(total_cost, 4),
            "breakdown_by_skill": [],  # 将来の詳細実装用
        }

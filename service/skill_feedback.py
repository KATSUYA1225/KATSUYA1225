"""スキルフィードバック収集・集計サービス（SQLite）"""
from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

DB_PATH = Path(__file__).parent.parent / "data" / "feedback.db"


def _conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db() -> None:
    with _conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS skill_feedback (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                skill_id     TEXT    NOT NULL,
                rating       INTEGER NOT NULL CHECK(rating BETWEEN 1 AND 5),
                quality_tag  TEXT,
                notes        TEXT,
                task_snippet TEXT,
                created_at   TEXT    DEFAULT (datetime('now','localtime'))
            );
            CREATE INDEX IF NOT EXISTS idx_sf_skill ON skill_feedback(skill_id);

            CREATE TABLE IF NOT EXISTS skill_versions (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                skill_id     TEXT    NOT NULL,
                version      TEXT    NOT NULL,
                changelog    TEXT,
                upgraded_at  TEXT    DEFAULT (datetime('now','localtime'))
            );
        """)


def add_feedback(
    skill_id: str,
    rating: int,
    quality_tag: str | None = None,
    notes: str | None = None,
    task_snippet: str | None = None,
) -> int:
    init_db()
    with _conn() as conn:
        cur = conn.execute(
            """INSERT INTO skill_feedback (skill_id, rating, quality_tag, notes, task_snippet)
               VALUES (?,?,?,?,?)""",
            (skill_id, rating, quality_tag, notes, task_snippet),
        )
        return cur.lastrowid  # type: ignore[return-value]


def get_summary(skill_id: str) -> dict[str, Any]:
    init_db()
    with _conn() as conn:
        rows = conn.execute(
            """SELECT rating, quality_tag, notes, created_at
               FROM skill_feedback WHERE skill_id=? ORDER BY created_at DESC LIMIT 100""",
            (skill_id,),
        ).fetchall()

    if not rows:
        return {"count": 0, "avg_rating": None, "quality_breakdown": {}, "recent_notes": []}

    ratings = [r["rating"] for r in rows]
    quality_counts: dict[str, int] = {}
    for r in rows:
        qt = r["quality_tag"] or "unset"
        quality_counts[qt] = quality_counts.get(qt, 0) + 1

    return {
        "count": len(rows),
        "avg_rating": round(sum(ratings) / len(ratings), 1),
        "quality_breakdown": quality_counts,
        "recent_notes": [r["notes"] for r in rows if r["notes"]][:10],
        "last_feedback_at": rows[0]["created_at"] if rows else None,
    }


def get_all_summaries() -> dict[str, dict[str, Any]]:
    """全スキルのフィードバックサマリーを返す（admin用）"""
    init_db()
    with _conn() as conn:
        skill_ids = [
            r[0] for r in conn.execute(
                "SELECT DISTINCT skill_id FROM skill_feedback"
            ).fetchall()
        ]
    return {sid: get_summary(sid) for sid in skill_ids}


def add_version_log(skill_id: str, version: str, changelog: str) -> None:
    init_db()
    with _conn() as conn:
        conn.execute(
            "INSERT INTO skill_versions (skill_id, version, changelog) VALUES (?,?,?)",
            (skill_id, version, changelog),
        )


def get_version_history(skill_id: str) -> list[dict[str, Any]]:
    init_db()
    with _conn() as conn:
        rows = conn.execute(
            "SELECT version, changelog, upgraded_at FROM skill_versions WHERE skill_id=? ORDER BY upgraded_at DESC",
            (skill_id,),
        ).fetchall()
    return [dict(r) for r in rows]

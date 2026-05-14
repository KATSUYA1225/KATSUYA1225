"""企業DNA・タスクログ保存 — data/ 以下に JSON で管理"""
from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

DNA_DIR = Path("data/dna")
TASK_LOG = Path("data/task_log.json")


def _path(company_id: str) -> Path:
    DNA_DIR.mkdir(parents=True, exist_ok=True)
    return DNA_DIR / f"{company_id}.json"


def save_dna(company_id: str, data: dict[str, Any]) -> dict[str, Any]:
    existing = load_dna(company_id) or {}
    merged = {**existing, **data}
    merged["company_id"] = company_id
    merged["updated_at"] = datetime.now().isoformat()
    if "created_at" not in merged:
        merged["created_at"] = merged["updated_at"]
    _path(company_id).write_text(json.dumps(merged, ensure_ascii=False, indent=2))
    return merged


def load_dna(company_id: str) -> dict[str, Any] | None:
    p = _path(company_id)
    if not p.exists():
        return None
    return json.loads(p.read_text())


def list_companies() -> list[dict[str, Any]]:
    """DNAが登録済みの全企業をリストで返す"""
    if not DNA_DIR.exists():
        return []
    result = []
    for p in sorted(DNA_DIR.glob("*.json")):
        try:
            d = json.loads(p.read_text())
            result.append({
                "id":      p.stem,
                "name":    d.get("company_name", p.stem),
                "industry": d.get("industry", ""),
                "mission": d.get("goal_1y", ""),
                "plan":    d.get("plan", "starter"),
                "dna_only": True,
            })
        except Exception:
            pass
    return result


def dna_to_company_config(company_id: str, dna: dict[str, Any]) -> dict[str, Any]:
    """DNAから stream.py が必要とする会社設定辞書を生成する"""
    return {
        "config_version": "1.0",
        "company_id":     company_id,
        "company_name":   dna.get("company_name", company_id),
        "industry":       dna.get("industry", ""),
        "language":       "ja",
        "tone":           "professional",
        "company_mission": dna.get("goal_1y", ""),
        "company_context": "",
        "template_context": "",
        "active_addons":  dna.get("active_skills", []),
    }


def save_task_log(
    company_id: str,
    company_name: str,
    task: str,
    result: str,
    cost_ref: float,
) -> None:
    TASK_LOG.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "task_id":      str(uuid.uuid4()),
        "company_id":   company_id,
        "company_name": company_name,
        "task":         task,
        "result":       result,
        "cost_ref":     cost_ref,
        "created_at":   datetime.now().isoformat(),
    }
    existing: list[dict] = []
    if TASK_LOG.exists():
        try:
            existing = json.loads(TASK_LOG.read_text())
        except Exception:
            existing = []
    existing.insert(0, entry)
    TASK_LOG.write_text(json.dumps(existing[:200], ensure_ascii=False, indent=2))


def list_task_log(company_id: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
    if not TASK_LOG.exists():
        return []
    try:
        tasks = json.loads(TASK_LOG.read_text())
    except Exception:
        return []
    if company_id:
        tasks = [t for t in tasks if t.get("company_id") == company_id]
    return tasks[:limit]


def dna_to_context(dna: dict[str, Any]) -> str:
    """DNAをエージェントのシステムプロンプト用コンテキスト文字列に変換する"""
    lines: list[str] = ["【企業DNA情報】"]
    if dna.get("employee_count"):
        lines.append(f"従業員数: {dna['employee_count']}")
    if dna.get("revenue_range"):
        lines.append(f"売上規模: {dna['revenue_range']}")
    if dna.get("target_customers"):
        lines.append(f"ターゲット顧客: {dna['target_customers']}")
    if dna.get("competitors"):
        lines.append(f"主な競合: {dna['competitors']}")
    if dna.get("self_strengths"):
        lines.append(f"自社の強み（自己評価）: {dna['self_strengths']}")
    if dna.get("challenges"):
        lines.append(f"現在の課題: {dna['challenges']}")
    if dna.get("goal_3m"):
        lines.append(f"3ヶ月目標: {dna['goal_3m']}")
    if dna.get("goal_1y"):
        lines.append(f"1年目標: {dna['goal_1y']}")
    if dna.get("strength_report"):
        lines.append(f"\n【AI強みレポート（分析済）】\n{dna['strength_report']}")
    return "\n".join(lines) if len(lines) > 1 else ""

"""企業DNA保存・取得 — data/dna/ 以下に JSON で管理"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

DNA_DIR = Path("data/dna")


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

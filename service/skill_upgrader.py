"""
スキル自動アップグレードパイプライン

フィードバックデータ + 現在のプレイブック + スキルYAML を読み込み、
Claude を使って改善案を生成。承認後に YAML とプレイブックを更新する。
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import anthropic
import yaml

from service.skill_feedback import get_summary, add_version_log

SKILLS_DIR = Path(__file__).parent.parent / "skills"
KNOWLEDGE_DIR = Path(__file__).parent.parent / "knowledge"


def _load_skill_yaml(skill_id: str) -> tuple[Path, dict[str, Any]]:
    for p in SKILLS_DIR.rglob(f"{skill_id}.yaml"):
        return p, yaml.safe_load(p.read_text(encoding="utf-8"))
    raise FileNotFoundError(f"YAML not found for skill: {skill_id}")


def _load_playbook(skill_id: str) -> str:
    path = KNOWLEDGE_DIR / skill_id / "playbook.md"
    if path.exists():
        return path.read_text(encoding="utf-8")
    return "（プレイブックなし）"


def _bump_version(current: str) -> str:
    """'1.0' -> '1.1', '1.9' -> '2.0'"""
    parts = current.split(".")
    major, minor = int(parts[0]), int(parts[1]) if len(parts) > 1 else 0
    if minor >= 9:
        return f"{major + 1}.0"
    return f"{major}.{minor + 1}"


def generate_upgrade_proposal(skill_id: str, *, dry_run: bool = False) -> dict[str, Any]:
    """
    Claudeを使って改善案を生成する。

    Returns:
        {
            "skill_id": str,
            "current_version": str,
            "proposed_version": str,
            "feedback_summary": dict,
            "improved_playbook": str,
            "improved_system_prompt": str,
            "changelog": str,
        }
    """
    feedback = get_summary(skill_id)
    yaml_path, skill_data = _load_skill_yaml(skill_id)
    current_playbook = _load_playbook(skill_id)
    current_version = skill_data.get("skill_version", "1.0")
    proposed_version = _bump_version(current_version)

    if dry_run:
        return {
            "skill_id": skill_id,
            "current_version": current_version,
            "proposed_version": proposed_version,
            "feedback_summary": feedback,
            "improved_playbook": current_playbook,
            "improved_system_prompt": skill_data.get("system_prompt_template", ""),
            "changelog": "（dry-run: Claudeは呼ばれていません）",
        }

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key or api_key.startswith("mock"):
        return {
            "skill_id": skill_id,
            "current_version": current_version,
            "proposed_version": proposed_version,
            "feedback_summary": feedback,
            "improved_playbook": current_playbook,
            "improved_system_prompt": skill_data.get("system_prompt_template", ""),
            "changelog": "（MOCK_AI: Claudeは呼ばれていません）",
        }

    client = anthropic.Anthropic(api_key=api_key)

    prompt = f"""あなたは世界クラスの{skill_data['display_name']}の専門家であり、
AIエージェントのスキル品質を向上させるコンサルタントです。

## 現在のスキル情報
- スキルID: {skill_id}
- スキル名: {skill_data['display_name']}
- 説明: {skill_data['description']}
- 現在バージョン: {current_version}

## ユーザーフィードバック統計
{feedback}

## 現在のプレイブック
{current_playbook}

## 現在のシステムプロンプト
{skill_data.get('system_prompt_template', '')}

---

以下の3つを改善してください。業界のトップ専門家レベルのアウトプットが出るよう、
具体的なフレームワーク・手順・品質基準を盛り込んでください。

1. **improved_playbook**: プレイブック全体の改善版（Markdownで）
   - フィードバックで指摘された弱点を補強する
   - 最新の業界ベストプラクティスを追加する
   - 品質基準をより具体的にする

2. **improved_system_prompt**: システムプロンプトの改善版
   - プレイブックの知識を活用した、より専門的な指示に更新する
   - アウトプット形式の指定を追加する

3. **changelog**: 何をなぜ変更したか（1〜5行）

以下のJSON形式で回答してください:
```json
{{
  "improved_playbook": "...",
  "improved_system_prompt": "...",
  "changelog": "..."
}}
```
"""

    message = client.messages.create(
        model="claude-opus-4-7",
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = message.content[0].text
    import json
    match = re.search(r"```json\s*(.*?)\s*```", raw, re.DOTALL)
    if match:
        result = json.loads(match.group(1))
    else:
        result = json.loads(raw)

    return {
        "skill_id": skill_id,
        "current_version": current_version,
        "proposed_version": proposed_version,
        "feedback_summary": feedback,
        "improved_playbook": result.get("improved_playbook", current_playbook),
        "improved_system_prompt": result.get("improved_system_prompt", skill_data.get("system_prompt_template", "")),
        "changelog": result.get("changelog", ""),
    }


def apply_upgrade(proposal: dict[str, Any]) -> None:
    """承認された改善案をファイルに書き込み、バージョンを更新する"""
    skill_id = proposal["skill_id"]

    # プレイブック更新
    playbook_path = KNOWLEDGE_DIR / skill_id / "playbook.md"
    playbook_path.parent.mkdir(parents=True, exist_ok=True)
    # バージョンコメントを先頭に追加
    new_version = proposal["proposed_version"]
    content = re.sub(
        r"(# .+?— .+?)v[\d.]+",
        rf"\1v{new_version}",
        proposal["improved_playbook"],
        count=1,
    )
    playbook_path.write_text(content, encoding="utf-8")

    # YAML更新（system_prompt_template + skill_version）
    yaml_path, skill_data = _load_skill_yaml(skill_id)
    skill_data["skill_version"] = new_version
    skill_data["system_prompt_template"] = proposal["improved_system_prompt"]
    yaml_path.write_text(
        yaml.dump(skill_data, allow_unicode=True, default_flow_style=False, sort_keys=False),
        encoding="utf-8",
    )

    # バージョン履歴記録
    add_version_log(skill_id, new_version, proposal["changelog"])

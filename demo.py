"""
AI企業OS デモ（CLIモード / Proプラン）
APIキー不要 - claude -p コマンドをサブプロセスで呼び出す
"""
import asyncio
import json
import logging
import re
from pathlib import Path
from typing import Any

import yaml

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger(__name__)

SKILLS_DIR = Path("skills")
DEMO_TASK = "SNS戦略を立案し、売上向上につながる具体的な施策を3つ提案してください。"
DEMO_COMPANIES = [
    Path("companies/example_tech.yaml"),
    Path("companies/liverty_realm.yaml"),
]

# CLIモードは全エージェント sonnet 統一（Proプラン対応）
CLI_MODEL = "claude-sonnet-4-6"

# 参考API価格（Proプランでは実際の課金なし）
_REF_RATE = {"input": 0.45, "output": 2.25}   # JPY / 1K tokens
_EST = {"pres_in": 2000, "pres_out": 1500, "emp_in": 500, "emp_out": 800}


# ── ユーティリティ ────────────────────────────────────────────────────────────

def load_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def load_skill(role_id: str) -> dict[str, Any]:
    for p in SKILLS_DIR.rglob("*.yaml"):
        data = load_yaml(p)
        if data.get("role_id") == role_id:
            return data
    raise ValueError(f"Skill not found: {role_id}")


def render_prompt(skill: dict[str, Any], company: dict[str, Any]) -> str:
    return skill["system_prompt_template"].format_map({
        "company_name":    company.get("company_name", ""),
        "industry":        company.get("industry", ""),
        "language":        company.get("language", "ja"),
        "tone":            company.get("tone", "professional"),
        "company_mission": company.get("company_mission", ""),
        "company_context": company.get("company_context", ""),
        "template_context": company.get("template_context", ""),
    })


def extract_json(text: str) -> dict[str, Any]:
    for pat in [r"```(?:json)?\s*(\{.*?\})\s*```", r"(\{.*\})"]:
        m = re.search(pat, text, re.DOTALL)
        if m:
            return json.loads(m.group(1))
    raise ValueError("JSONが見つかりません")


def ref_cost(n_employees: int) -> float:
    pres = ((_EST["pres_in"] / 1000) * _REF_RATE["input"] + (_EST["pres_out"] / 1000) * _REF_RATE["output"]) * 2
    emp  = n_employees * ((_EST["emp_in"] / 1000) * _REF_RATE["input"] + (_EST["emp_out"] / 1000) * _REF_RATE["output"])
    return pres + emp


# ── claude CLI 呼び出し ───────────────────────────────────────────────────────

async def call_claude(prompt: str, system: str, model: str = CLI_MODEL) -> str:
    proc = await asyncio.create_subprocess_exec(
        "claude", "-p", prompt,
        "--system-prompt", system,
        "--model", model,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(f"claude CLI error: {stderr.decode()[:300]}")
    return stdout.decode().strip()


# ── 1社分の実行 ──────────────────────────────────────────────────────────────

async def run_company(company: dict[str, Any]) -> tuple[str, str, float]:
    name = company["company_name"]
    mandatory = ["president", "marketing", "sns_pr"]
    addons     = company.get("active_addons", [])
    all_ids    = list(dict.fromkeys(mandatory + addons))
    emp_ids    = [s for s in all_ids if s != "president"]

    skill_names = {}
    for sid in emp_ids:
        try:
            skill_names[sid] = load_skill(sid).get("display_name", sid)
        except ValueError:
            pass

    pres_system = render_prompt(load_skill("president"), company)

    # ── Phase 1: 社長が委譲計画を JSON で出力 ──────────────────
    dept_list = "\n".join(f"- {sid}: {n}" for sid, n in skill_names.items())
    phase1_prompt = f"""タスク: {DEMO_TASK}

利用可能な部門:
{dept_list}

このタスクを遂行するため、必要な部門を選んで各部門への指示を決定してください。
以下のJSON形式だけを出力してください（前後の説明文は不要）:
{{
  "delegations": [
    {{"department": "部門ID", "task": "具体的な指示内容"}},
    ...
  ]
}}"""

    logger.info(f"[{name}] 社長 → 委譲計画を策定...")
    phase1 = await call_claude(phase1_prompt, pres_system)

    try:
        plan = extract_json(phase1)
        delegations: list[dict[str, str]] = plan.get("delegations", [])
    except (ValueError, json.JSONDecodeError):
        logger.warning(f"[{name}] JSONパース失敗。全部門に委譲します。")
        delegations = [{"department": sid, "task": DEMO_TASK} for sid in emp_ids]

    called = [d["department"] for d in delegations]
    logger.info(f"[{name}] {len(called)}部門へ委譲: {called}")

    # ── Phase 2: 各部門が並列実行 ──────────────────────────────
    async def call_employee(dep: str, task: str) -> tuple[str, str]:
        try:
            skill = load_skill(dep)
        except ValueError:
            return dep, f"[{dep}] スキルが見つかりません"
        system  = render_prompt(skill, company)
        display = skill.get("display_name", dep)
        logger.info(f"  [{name}] {display}: 実行中...")
        result = await call_claude(task, system)
        logger.info(f"  [{name}] {display}: 完了")
        return display, result

    reports_raw = await asyncio.gather(
        *[call_employee(d["department"], d["task"]) for d in delegations],
        return_exceptions=True,
    )

    report_texts: list[str] = []
    for item in reports_raw:
        if isinstance(item, Exception):
            logger.warning(f"  エラー: {item}")
        else:
            dept_name, text = item
            report_texts.append(f"=== {dept_name} ===\n{text}")

    # ── Phase 3: 社長が統合・最終決裁 ─────────────────────────
    final_prompt = f"""元のタスク: {DEMO_TASK}

各部門からの報告書:
{chr(10).join(report_texts)}

上記の報告書を統合し、「【社長決裁】」で始まる最終的な経営判断を発表してください。"""

    logger.info(f"[{name}] 社長 → 最終決裁を作成中...")
    final = await call_claude(final_prompt, pres_system)

    return name, final, ref_cost(len(delegations))


# ── メイン ───────────────────────────────────────────────────────────────────

async def main() -> None:
    print("\n" + "=" * 70)
    print("  AI企業OS デモ  ／  CLIモード（Proプラン）")
    print(f"  モデル : {CLI_MODEL}")
    print(f"  タスク : {DEMO_TASK}")
    print("=" * 70)

    # コスト試算（参考）
    print("\n┌──────────────────────────────────────────────────────────────┐")
    print("│  コスト試算（参考値）  ※ Proプランのため実際の課金はありません │")
    print("├──────────────────────────────┬───────────────────────────────┤")

    total_ref = 0.0
    for p in DEMO_COMPANIES:
        cfg = load_yaml(p)
        n = len(cfg.get("active_addons", [])) + 3
        r = ref_cost(n)
        total_ref += r
        print(f"│ {cfg['company_name']:<28} │ 参考API価格: ¥{r:>8.1f}        │")

    print("├──────────────────────────────┴───────────────────────────────┤")
    print(f"│  合計参考API価格: ¥{total_ref:<6.1f}  （Proプラン利用のため ¥0）     │")
    print("└──────────────────────────────────────────────────────────────┘")

    print(f"\n  [Enter] で開始 / [Ctrl+C] でキャンセル: ", end="", flush=True)
    try:
        input()
    except KeyboardInterrupt:
        print("\n  キャンセルしました。")
        return

    print()

    results = await asyncio.gather(
        *[run_company(load_yaml(p)) for p in DEMO_COMPANIES],
        return_exceptions=True,
    )

    total_actual_ref = 0.0
    for item in results:
        if isinstance(item, Exception):
            print(f"\n[ERROR] {item}\n")
            continue
        company_name, result, cost_ref = item
        total_actual_ref += cost_ref
        print(f"\n{'#' * 70}")
        print(f"  {company_name}")
        print(f"{'#' * 70}")
        print(result)
        print(f"\n  ── 参考API価格: ¥{cost_ref:.1f}（Proプラン利用のため ¥0）")

    print("\n" + "=" * 70)
    print(f"  デモ完了 ／ 合計参考API価格: ¥{total_actual_ref:.1f}（実際の課金: ¥0）")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    asyncio.run(main())

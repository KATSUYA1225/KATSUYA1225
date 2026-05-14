"""
WebUI用 SSEストリーミングロジック
demo.py と同じ claude -p サブプロセスアプローチを使用（APIキー不要）
"""
from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path
from typing import Any, AsyncGenerator

import yaml

SKILLS_DIR = Path("skills")
COMPANIES_DIR = Path("companies")
CLI_MODEL = "claude-sonnet-4-6"

_REF_RATE = {"input": 0.45, "output": 2.25}  # JPY/1K tokens
_EST = {"pres_in": 2000, "pres_out": 1500, "emp_in": 500, "emp_out": 800}


def _load_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _load_skill(role_id: str) -> dict[str, Any]:
    for p in SKILLS_DIR.rglob("*.yaml"):
        data = _load_yaml(p)
        if data.get("role_id") == role_id:
            return data
    raise ValueError(f"Skill not found: {role_id}")


def _render_prompt(skill: dict[str, Any], company: dict[str, Any]) -> str:
    return skill["system_prompt_template"].format_map({
        "company_name":    company.get("company_name", ""),
        "industry":        company.get("industry", ""),
        "language":        company.get("language", "ja"),
        "tone":            company.get("tone", "professional"),
        "company_mission": company.get("company_mission", ""),
        "company_context": company.get("company_context", ""),
        "template_context": company.get("template_context", ""),
    })


async def _call_claude(prompt: str, system: str) -> str:
    proc = await asyncio.create_subprocess_exec(
        "claude", "-p", prompt,
        "--system-prompt", system,
        "--model", CLI_MODEL,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(f"claude error: {stderr.decode()[:300]}")
    return stdout.decode().strip()


def _extract_json(text: str) -> dict[str, Any]:
    for pat in [r"```(?:json)?\s*(\{.*?\})\s*```", r"(\{.*\})"]:
        m = re.search(pat, text, re.DOTALL)
        if m:
            return json.loads(m.group(1))
    raise ValueError("JSON not found")


def _ref_cost(n: int) -> float:
    pres = ((_EST["pres_in"] / 1000) * _REF_RATE["input"] + (_EST["pres_out"] / 1000) * _REF_RATE["output"]) * 2
    emp  = n * ((_EST["emp_in"] / 1000) * _REF_RATE["input"] + (_EST["emp_out"] / 1000) * _REF_RATE["output"])
    return pres + emp


def _sse(type_: str, **kwargs: Any) -> str:
    return f"data: {json.dumps({'type': type_, **kwargs}, ensure_ascii=False)}\n\n"


def list_presets() -> list[dict[str, str]]:
    presets = []
    for p in sorted(COMPANIES_DIR.glob("*.yaml")):
        cfg = _load_yaml(p)
        presets.append({
            "id":       p.stem,
            "name":     cfg.get("company_name", p.stem),
            "industry": cfg.get("industry", ""),
            "mission":  cfg.get("company_mission", ""),
        })
    return presets


async def run_stream(company_yaml: str, task: str) -> AsyncGenerator[str, None]:
    from service.company_store import load_dna, dna_to_context, dna_to_company_config, save_task_log

    path = COMPANIES_DIR / f"{company_yaml}.yaml"

    dna = load_dna(company_yaml)

    if path.exists():
        company = dict(_load_yaml(path))
    elif dna:
        # YAMLがなくてもDNAがあれば実行可能
        company = dna_to_company_config(company_yaml, dna)
    else:
        yield _sse("error", message=f"企業設定が見つかりません: {company_yaml}")
        return

    # DNAコンテキストをプロンプトに注入
    if dna:
        extra = dna_to_context(dna)
        if extra:
            company["company_context"] = company.get("company_context", "") + "\n\n" + extra

    mandatory = ["president", "marketing", "sns_pr"]
    emp_ids = list(dict.fromkeys(mandatory + company.get("active_addons", [])))
    emp_ids = [s for s in emp_ids if s != "president"]

    skill_meta: dict[str, dict] = {}
    for sid in emp_ids:
        try:
            skill_meta[sid] = _load_skill(sid)
        except ValueError:
            pass

    pres_system = _render_prompt(_load_skill("president"), company)

    # ── Phase 1: 社長が委譲計画を策定 ────────────────────────
    yield _sse("status", message="社長: 委譲計画を策定中...")

    dept_list = "\n".join(
        f"- {sid}: {m.get('display_name', sid)}" for sid, m in skill_meta.items()
    )
    phase1_prompt = f"""タスク: {task}

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

    try:
        phase1 = await _call_claude(phase1_prompt, pres_system)
        delegations: list[dict[str, str]] = _extract_json(phase1).get("delegations", [])
    except Exception:
        delegations = [{"department": sid, "task": task} for sid in emp_ids]

    yield _sse("delegations", departments=[d["department"] for d in delegations])

    # ── Phase 2: 各部門が並列実行 ─────────────────────────────
    queue: asyncio.Queue[tuple[str, str, str, str]] = asyncio.Queue()

    async def worker(dep: str, worker_task: str) -> None:
        try:
            sk = skill_meta.get(dep) or _load_skill(dep)
            result = await _call_claude(worker_task, _render_prompt(sk, company))
            await queue.put(("done", dep, sk.get("display_name", dep), result))
        except Exception as exc:
            await queue.put(("error", dep, dep, str(exc)))

    bg_tasks = [asyncio.create_task(worker(d["department"], d["task"])) for d in delegations]

    reports: dict[str, str] = {}
    for _ in range(len(delegations)):
        status, dep, display, content = await queue.get()
        if status == "done":
            reports[display] = content
        yield _sse("dept_done", department=dep, display=display, status=status)

    await asyncio.gather(*bg_tasks)

    # ── Phase 3: 社長が統合・最終決裁 ─────────────────────────
    yield _sse("status", message="社長: 最終決裁を作成中...")

    report_text = "\n\n".join(f"=== {n} ===\n{t}" for n, t in reports.items())
    final_prompt = f"""元のタスク: {task}

各部門からの報告書:
{report_text}

上記の報告書を統合し、「【社長決裁】」で始まる最終的な経営判断を発表してください。"""

    try:
        final = await _call_claude(final_prompt, pres_system)
    except Exception as exc:
        yield _sse("error", message=f"最終決裁生成エラー: {exc}")
        return

    cost_ref = round(_ref_cost(len(delegations)), 1)
    yield _sse("result", content=final, cost_ref=cost_ref)

    # タスクログに保存
    try:
        save_task_log(
            company_id=company_yaml,
            company_name=company.get("company_name", company_yaml),
            task=task,
            result=final,
            cost_ref=cost_ref,
        )
    except Exception:
        pass

    yield "data: [DONE]\n\n"

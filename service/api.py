from __future__ import annotations

import asyncio
import os
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Any

import anthropic
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse

from agents import CompanyConfig, PresidentAgent, SkillRegistry
from service.models import (
    CompanyDNARequest,
    CompanyDNAResponse,
    CompanyRegistrationRequest,
    CompanyResponse,
    SkillCatalogResponse,
    SkillInfo,
    StrengthAnalysisResponse,
    TaskRequest,
    TaskResponse,
    TaskStatusResponse,
    UsageResponse,
)
from service.usage_tracker import UsageTracker
from service import stream as stream_module
from service.company_store import load_dna, save_dna, dna_to_context, list_companies, list_task_log

load_dotenv()

# ── グローバル状態 ───────────────────────────────────────────
registry: SkillRegistry
tracker: UsageTracker
_tasks_store: dict[str, dict[str, Any]] = {}  # インメモリキャッシュ（MVP）


@asynccontextmanager
async def lifespan(app: FastAPI):
    global registry, tracker
    registry = SkillRegistry()
    tracker = UsageTracker()
    await tracker.init()
    yield


app = FastAPI(
    title="AI企業OS API",
    description="どんな企業でも選択課金制でAIエージェントチームを持てるサービス",
    version="1.0.0",
    lifespan=lifespan,
)


# ── ヘルパー ────────────────────────────────────────────────

def _get_client() -> anthropic.AsyncAnthropic:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="ANTHROPIC_API_KEY が設定されていません")
    return anthropic.AsyncAnthropic(api_key=api_key)


def _calc_monthly_cost(active_skill_ids: list[str]) -> int:
    total = 0
    for role_id in active_skill_ids:
        try:
            skill = registry.get_skill(role_id)
            total += skill.monthly_price_jpy
        except ValueError:
            pass
    return total


async def _run_task_bg(task_id: str, company_config: CompanyConfig, task_text: str) -> None:
    await tracker.update_task_status(task_id, "running")
    _tasks_store[task_id]["status"] = "running"
    try:
        async with _get_client() as client:
            president = PresidentAgent(client, company_config, registry)
            result = await president.run(task_text)
        await tracker.complete_task(task_id, result)
        _tasks_store[task_id].update({"status": "completed", "result": result,
                                      "completed_at": datetime.utcnow().isoformat()})
    except Exception as exc:
        err = str(exc)
        await tracker.fail_task(task_id, err)
        _tasks_store[task_id].update({"status": "failed", "error": err,
                                      "completed_at": datetime.utcnow().isoformat()})


# ── エンドポイント ───────────────────────────────────────────

@app.get("/v1/skills", response_model=SkillCatalogResponse, summary="スキルカタログ（公開）")
async def list_skills(tier: str | None = None, plan: str | None = None) -> SkillCatalogResponse:
    skills = registry.list_skills()
    if tier:
        skills = [s for s in skills if s.price_tier == tier]
    _plan_order = ["starter", "growth", "business", "enterprise"]
    if plan and plan in _plan_order:
        idx = _plan_order.index(plan)
        skills = [s for s in skills if _plan_order.index(s.plan_required) <= idx]
    items = [
        SkillInfo(
            role_id=s.role_id,
            display_name=s.display_name,
            display_name_en=s.display_name_en,
            description=s.description,
            price_tier=s.price_tier,
            monthly_price_jpy=s.monthly_price_jpy,
            tags=s.tags,
            capabilities=s.capabilities,
            is_mandatory=s.is_mandatory,
            plan_required=s.plan_required,
            preview_text=s.preview_text,
            example_tasks=s.example_tasks,
            category=s.category,
        )
        for s in skills
    ]
    return SkillCatalogResponse(skills=items, total_count=len(items))


@app.post("/v1/companies", response_model=CompanyResponse, status_code=201, summary="企業登録")
async def register_company(req: CompanyRegistrationRequest) -> CompanyResponse:
    if await tracker.company_exists(req.company_id):
        raise HTTPException(status_code=409, detail=f"company_id '{req.company_id}' は既に登録されています")

    try:
        company = CompanyConfig.from_dict(req.model_dump(), registry)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    await tracker.register_company(req.company_id, req.model_dump())

    monthly_cost = _calc_monthly_cost(company.active_skill_ids)
    return CompanyResponse(
        company_id=company.company_id,
        company_name=company.company_name,
        active_skills=company.active_skill_ids,
        monthly_cost_jpy=monthly_cost,
        created_at=datetime.utcnow(),
    )


@app.post("/v1/tasks", response_model=TaskResponse, status_code=202, summary="タスク投入")
async def submit_task(req: TaskRequest) -> TaskResponse:
    config_data = await tracker.get_company_config(req.company_id)
    if config_data is None:
        raise HTTPException(status_code=404, detail=f"company_id '{req.company_id}' が見つかりません")

    config_data.pop("_created_at", None)
    try:
        company = CompanyConfig.from_dict(config_data, registry)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    task_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()
    _tasks_store[task_id] = {
        "task_id": task_id,
        "company_id": req.company_id,
        "status": "queued",
        "task_text": req.task,
        "result": None,
        "error": None,
        "created_at": now,
        "completed_at": None,
    }
    await tracker.create_task(task_id, req.company_id, req.task)
    asyncio.create_task(_run_task_bg(task_id, company, req.task))

    return TaskResponse(
        task_id=task_id,
        company_id=req.company_id,
        status="queued",
        estimated_seconds=90,
    )


@app.get("/v1/tasks/recent", summary="タスク実行履歴（ログファイル）")
async def recent_tasks_log(company_id: str | None = None, limit: int = 50) -> dict:
    tasks = list_task_log(company_id=company_id, limit=limit)
    return {"tasks": tasks, "total": len(tasks)}


@app.get("/v1/tasks/{task_id}", response_model=TaskStatusResponse, summary="タスク結果取得")
async def get_task(task_id: str) -> TaskStatusResponse:
    data = _tasks_store.get(task_id) or await tracker.get_task(task_id)
    if data is None:
        raise HTTPException(status_code=404, detail=f"task_id '{task_id}' が見つかりません")

    return TaskStatusResponse(
        task_id=data["task_id"],
        company_id=data["company_id"],
        status=data["status"],
        task_text=data["task_text"],
        result=data.get("result") or data.get("result_text"),
        tokens_input=data.get("tokens_input", 0),
        tokens_output=data.get("tokens_output", 0),
        cost_jpy=data.get("cost_jpy", 0.0),
        created_at=datetime.fromisoformat(data["created_at"]),
        completed_at=datetime.fromisoformat(data["completed_at"]) if data.get("completed_at") else None,
        error=data.get("error") or data.get("error_text"),
    )


@app.get("/v1/companies/{company_id}/usage", response_model=UsageResponse, summary="使用量確認")
async def get_usage(company_id: str, month: str | None = None) -> UsageResponse:
    if not await tracker.company_exists(company_id):
        raise HTTPException(status_code=404, detail=f"company_id '{company_id}' が見つかりません")
    if month is None:
        month = datetime.utcnow().strftime("%Y-%m")
    usage = await tracker.get_usage(company_id, month)
    return UsageResponse(**usage)


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def index() -> HTMLResponse:
    html = (Path(__file__).parent.parent / "static" / "index.html").read_text(encoding="utf-8")
    return HTMLResponse(content=html)


@app.get("/v1/companies/presets", summary="企業一覧（YAML + DNA登録済み）")
async def list_presets() -> dict:
    yaml_presets = {p["id"]: p for p in stream_module.list_presets()}
    dna_companies = {c["id"]: c for c in list_companies()}
    # YAMLが優先、なければDNA企業を追加
    merged = {**dna_companies, **yaml_presets}
    return {"presets": list(merged.values())}




@app.get("/v1/stream", summary="タスク実行（SSEストリーミング）")
async def stream_task(company: str, task: str) -> StreamingResponse:
    return StreamingResponse(
        stream_module.run_stream(company, task),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"},
    )


@app.post("/v1/companies/{company_id}/dna", response_model=CompanyDNAResponse, summary="企業DNA保存")
async def save_company_dna(company_id: str, req: CompanyDNARequest) -> CompanyDNAResponse:
    data = req.model_dump()
    saved = save_dna(company_id, data)
    return CompanyDNAResponse(
        company_id=company_id,
        company_name=saved.get("company_name", ""),
        industry=saved.get("industry", ""),
        employee_count=saved.get("employee_count", ""),
        revenue_range=saved.get("revenue_range", ""),
        target_customers=saved.get("target_customers", ""),
        competitors=saved.get("competitors", ""),
        self_strengths=saved.get("self_strengths", ""),
        challenges=saved.get("challenges", ""),
        goal_3m=saved.get("goal_3m", ""),
        goal_1y=saved.get("goal_1y", ""),
        plan=saved.get("plan", "starter"),
        has_strength_report=bool(saved.get("strength_report")),
        updated_at=saved.get("updated_at"),
    )


@app.get("/v1/companies/{company_id}/dna", response_model=CompanyDNAResponse, summary="企業DNA取得")
async def get_company_dna(company_id: str) -> CompanyDNAResponse:
    dna = load_dna(company_id)
    if dna is None:
        raise HTTPException(status_code=404, detail=f"DNA not found for '{company_id}'")
    return CompanyDNAResponse(
        company_id=company_id,
        company_name=dna.get("company_name", ""),
        industry=dna.get("industry", ""),
        employee_count=dna.get("employee_count", ""),
        revenue_range=dna.get("revenue_range", ""),
        target_customers=dna.get("target_customers", ""),
        competitors=dna.get("competitors", ""),
        self_strengths=dna.get("self_strengths", ""),
        challenges=dna.get("challenges", ""),
        goal_3m=dna.get("goal_3m", ""),
        goal_1y=dna.get("goal_1y", ""),
        plan=dna.get("plan", "starter"),
        has_strength_report=bool(dna.get("strength_report")),
        updated_at=dna.get("updated_at"),
    )


@app.post("/v1/companies/{company_id}/analyze-strengths", response_model=StrengthAnalysisResponse,
          summary="強み分析（AI）")
async def analyze_strengths(company_id: str) -> StrengthAnalysisResponse:
    dna = load_dna(company_id)
    if not dna:
        raise HTTPException(status_code=404, detail=f"先に企業DNAを保存してください: '{company_id}'")

    company_name = dna.get("company_name") or company_id
    industry = dna.get("industry", "")
    context = dna_to_context(dna)

    prompt = f"""企業名: {company_name}
業界: {industry}

{context}

上記の企業情報をもとに、以下の観点で強みを徹底分析してください：

1. 自己評価された強みの客観的検証（本当に強みか？競合と比べてどうか？）
2. 業界・市場トレンドとの照合（時流に乗れているか）
3. 競合他社との差別化ポイントの特定
4. 潜在的に見落とされている優位性の発見
5. 強みを軸にした戦略方向性の提案（3つ）

【強みレポート】として以下の構成で出力してください：
## ✅ 強みの検証
## 🎯 競合優位性
## 💎 潜在的な強み（気づいていない優位性）
## 🚀 推奨戦略方向性（3つ）"""

    system = (
        f"あなたは{company_name}の強み発見を専門とする経営コンサルタントです。"
        f"業界: {industry}。"
        "客観的データと論理的思考をもとに、企業の真の強みを発見・言語化します。"
        "感情論ではなく、競合比較・市場ポジション・顧客価値の観点から分析します。"
    )

    proc = await asyncio.create_subprocess_exec(
        "claude", "-p", prompt,
        "--system-prompt", system,
        "--model", "claude-sonnet-4-6",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise HTTPException(status_code=500, detail=f"分析エラー: {stderr.decode()[:300]}")

    report = stdout.decode().strip()
    save_dna(company_id, {"strength_report": report})

    return StrengthAnalysisResponse(company_id=company_id, strength_report=report)


@app.get("/health")
async def health() -> JSONResponse:
    return JSONResponse({"status": "ok", "skills_loaded": len(registry.list_skills())})

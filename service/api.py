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
    CompanyRegistrationRequest,
    CompanyResponse,
    SkillCatalogResponse,
    SkillInfo,
    TaskRequest,
    TaskResponse,
    TaskStatusResponse,
    UsageResponse,
)
from service.usage_tracker import UsageTracker
from service import stream as stream_module

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
async def list_skills(tier: str | None = None) -> SkillCatalogResponse:
    skills = registry.list_skills()
    if tier:
        skills = [s for s in skills if s.price_tier == tier]
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


@app.get("/v1/companies/presets", summary="YAMLで定義済みの企業一覧")
async def list_presets() -> dict:
    return {"presets": stream_module.list_presets()}


@app.get("/v1/stream", summary="タスク実行（SSEストリーミング）")
async def stream_task(company: str, task: str) -> StreamingResponse:
    return StreamingResponse(
        stream_module.run_stream(company, task),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"},
    )


@app.get("/health")
async def health() -> JSONResponse:
    return JSONResponse({"status": "ok", "skills_loaded": len(registry.list_skills())})

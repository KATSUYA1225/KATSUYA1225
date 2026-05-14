from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


# ── リクエスト ──────────────────────────────────────────────

class CompanyRegistrationRequest(BaseModel):
    company_id: str = Field(..., description="グローバルユニークなID（英数字・ハイフン）")
    company_name: str
    industry: str = ""
    language: str = "ja"
    tone: Literal["casual", "professional", "formal"] = "professional"
    company_mission: str = ""
    company_context: str = ""
    active_addons: list[str] = Field(default_factory=list)
    model_overrides: dict[str, str] = Field(default_factory=dict)
    token_overrides: dict[str, int] = Field(default_factory=dict)


class TaskRequest(BaseModel):
    company_id: str
    task: str = Field(..., min_length=1, max_length=2000)
    priority: Literal["normal", "high"] = "normal"


# ── レスポンス ─────────────────────────────────────────────

class SkillInfo(BaseModel):
    role_id: str
    display_name: str
    display_name_en: str
    description: str
    price_tier: str
    monthly_price_jpy: int
    tags: list[str]
    capabilities: list[str]
    is_mandatory: bool


class CompanyResponse(BaseModel):
    company_id: str
    company_name: str
    active_skills: list[str]
    monthly_cost_jpy: int
    created_at: datetime


class TaskResponse(BaseModel):
    task_id: str
    company_id: str
    status: Literal["queued", "running", "completed", "failed"]
    estimated_seconds: int = 60


class TaskStatusResponse(BaseModel):
    task_id: str
    company_id: str
    status: Literal["queued", "running", "completed", "failed"]
    task_text: str
    result: str | None = None
    tokens_input: int = 0
    tokens_output: int = 0
    cost_jpy: float = 0.0
    created_at: datetime
    completed_at: datetime | None = None
    error: str | None = None


class UsageBreakdown(BaseModel):
    role_id: str
    display_name: str
    task_count: int
    tokens_input: int
    tokens_output: int
    cost_jpy: float


class UsageResponse(BaseModel):
    company_id: str
    period: str  # "2026-05"
    total_tasks: int
    total_tokens_input: int
    total_tokens_output: int
    total_cost_jpy: float
    breakdown_by_skill: list[UsageBreakdown]


class SkillCatalogResponse(BaseModel):
    skills: list[SkillInfo]
    total_count: int

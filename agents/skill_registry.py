from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml

if TYPE_CHECKING:
    from .company_config import CompanyConfig

SKILLS_DIR = Path(__file__).parent.parent / "skills"


@dataclass
class SkillConfig:
    role_id: str
    display_name: str
    display_name_en: str
    description: str
    is_mandatory: bool
    price_tier: str  # included | standard | premium | professional
    monthly_price_jpy: int
    model: str
    max_tokens: int
    system_prompt_template: str
    delegation_description: str | None
    delegation_task_description: str | None
    tags: list[str] = field(default_factory=list)
    capabilities: list[str] = field(default_factory=list)
    included_in_templates: list[str] = field(default_factory=list)
    max_delegation_loops: int = 5  # presidentのみ使用
    plan_required: str = "starter"  # starter | growth | business | enterprise
    preview_text: str = ""
    example_tasks: list[str] = field(default_factory=list)
    category: str = "general"

    def render_system_prompt(self, company: CompanyConfig) -> str:
        vars: dict[str, str] = defaultdict(str, {
            "company_name": company.company_name,
            "industry": company.industry,
            "language": company.language,
            "tone": company.tone,
            "company_mission": company.company_mission,
            "company_context": company.company_context,
            "template_context": company.template_context,
        })
        return self.system_prompt_template.format_map(vars)


class SkillRegistry:
    def __init__(self, skills_dir: Path = SKILLS_DIR) -> None:
        self._skills: dict[str, SkillConfig] = {}
        self._load_all(skills_dir)

    def _load_all(self, skills_dir: Path) -> None:
        for yaml_path in sorted(skills_dir.rglob("*.yaml")):
            skill = self._load_one(yaml_path)
            self._skills[skill.role_id] = skill

    def _load_one(self, path: Path) -> SkillConfig:
        data: dict[str, Any] = yaml.safe_load(path.read_text(encoding="utf-8"))
        return SkillConfig(
            role_id=data["role_id"],
            display_name=data["display_name"],
            display_name_en=data.get("display_name_en", data["display_name"]),
            description=data["description"],
            is_mandatory=data.get("is_mandatory", False),
            price_tier=data.get("price_tier", "standard"),
            monthly_price_jpy=data.get("monthly_price_jpy", 0),
            model=data["model"],
            max_tokens=data.get("max_tokens", 2048),
            system_prompt_template=data["system_prompt_template"],
            delegation_description=data.get("delegation_description"),
            delegation_task_description=data.get("delegation_task_description"),
            tags=data.get("tags", []),
            capabilities=data.get("capabilities", []),
            included_in_templates=data.get("included_in_templates", []),
            max_delegation_loops=data.get("max_delegation_loops", 5),
            plan_required=data.get("plan_required", "starter"),
            preview_text=data.get("preview_text", ""),
            example_tasks=data.get("example_tasks", []),
            category=data.get("category", "general"),
        )

    def get_skill(self, role_id: str) -> SkillConfig:
        if role_id not in self._skills:
            raise ValueError(f"Unknown skill: '{role_id}'. Available: {list(self._skills)}")
        return self._skills[role_id]

    def list_skills(self) -> list[SkillConfig]:
        return list(self._skills.values())

    def list_addon_skills(self) -> list[SkillConfig]:
        return [s for s in self._skills.values() if not s.is_mandatory]

    def get_mandatory_role_ids(self) -> list[str]:
        return [s.role_id for s in self._skills.values() if s.is_mandatory]

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .skill_registry import SkillRegistry

MANDATORY_SKILLS = ["president", "marketing", "sns_pr"]


@dataclass
class CompanyConfig:
    company_id: str
    company_name: str
    industry: str
    language: str
    tone: str
    company_mission: str
    active_addons: list[str]
    company_context: str = ""
    template_context: str = ""
    model_overrides: dict[str, str] = field(default_factory=dict)
    token_overrides: dict[str, int] = field(default_factory=dict)
    log_dir_template: str = "logs/{company_id}"

    @property
    def active_skill_ids(self) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []
        for role_id in MANDATORY_SKILLS + self.active_addons:
            if role_id not in seen:
                seen.add(role_id)
                result.append(role_id)
        return result

    @property
    def log_dir(self) -> Path:
        return Path(self.log_dir_template.replace("{company_id}", self.company_id))

    @classmethod
    def from_yaml(cls, path: Path, registry: SkillRegistry) -> CompanyConfig:
        data: dict[str, Any] = yaml.safe_load(path.read_text(encoding="utf-8"))
        active_addons: list[str] = data.get("active_addons", [])

        unknown = [r for r in active_addons if r not in {s.role_id for s in registry.list_skills()}]
        if unknown:
            raise ValueError(f"Unknown skill(s) in active_addons: {unknown}")

        return cls(
            company_id=data["company_id"],
            company_name=data["company_name"],
            industry=data.get("industry", ""),
            language=data.get("language", "ja"),
            tone=data.get("tone", "professional"),
            company_mission=data.get("company_mission", ""),
            active_addons=active_addons,
            company_context=data.get("company_context", ""),
            template_context=data.get("template_context", ""),
            model_overrides=data.get("model_overrides", {}),
            token_overrides=data.get("token_overrides", {}),
            log_dir_template=data.get("log_dir", "logs/{company_id}"),
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any], registry: SkillRegistry) -> CompanyConfig:
        active_addons: list[str] = data.get("active_addons", [])
        unknown = [r for r in active_addons if r not in {s.role_id for s in registry.list_skills()}]
        if unknown:
            raise ValueError(f"Unknown skill(s) in active_addons: {unknown}")
        return cls(
            company_id=data["company_id"],
            company_name=data["company_name"],
            industry=data.get("industry", ""),
            language=data.get("language", "ja"),
            tone=data.get("tone", "professional"),
            company_mission=data.get("company_mission", ""),
            active_addons=active_addons,
            company_context=data.get("company_context", ""),
            template_context=data.get("template_context", ""),
            model_overrides=data.get("model_overrides", {}),
            token_overrides=data.get("token_overrides", {}),
        )

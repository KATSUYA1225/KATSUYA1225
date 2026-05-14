from __future__ import annotations

import anthropic

from .base_agent import AgentConfig, BaseAgent
from .company_config import CompanyConfig
from .skill_registry import SkillRegistry


def create_employee_from_skill(
    role_id: str,
    company: CompanyConfig,
    registry: SkillRegistry,
    client: anthropic.AsyncAnthropic,
) -> BaseAgent:
    skill = registry.get_skill(role_id)
    config = AgentConfig(
        name=skill.display_name,
        role=role_id,
        model=company.model_overrides.get(role_id, skill.model),
        system_prompt=skill.render_system_prompt(company),
        max_tokens=company.token_overrides.get(role_id, skill.max_tokens),
        language=company.language,
    )
    return BaseAgent(config, client)

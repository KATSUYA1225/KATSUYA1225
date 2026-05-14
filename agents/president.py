from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any

import anthropic

from .company_config import CompanyConfig
from .employee_agents import create_employee_from_skill
from .skill_registry import SkillRegistry

_MOCK_AI    = os.environ.get("MOCK_AI",    "").lower() in ("1", "true", "yes")
_HAIKU_MODE = os.environ.get("HAIKU_MODE", "").lower() in ("1", "true", "yes")
_HAIKU_MODEL = "claude-haiku-4-5-20251001"

# JPY/1K tokens（usage_tracker.RATES と同期）
_RATES: dict[str, dict[str, float]] = {
    "claude-opus-4-7":           {"input": 2.25,  "output": 11.25},
    "claude-sonnet-4-6":         {"input": 0.45,  "output": 2.25},
    "claude-haiku-4-5-20251001": {"input": 0.12,  "output": 0.60},
}

def _cost_jpy(model: str, inp: int, out: int) -> float:
    r = _RATES.get(model, {"input": 0.45, "output": 2.25})
    return (inp / 1000) * r["input"] + (out / 1000) * r["output"]


class PresidentAgent:
    def __init__(
        self,
        client: anthropic.AsyncAnthropic,
        company_config: CompanyConfig,
        registry: SkillRegistry,
        log_dir: Path | None = None,
    ) -> None:
        self.client = client
        self.company = company_config
        self.registry = registry
        self.log_dir = (log_dir or company_config.log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self._logger = logging.getLogger(f"president.{company_config.company_id}")

        pres = registry.get_skill("president")
        base_model = company_config.model_overrides.get("president", pres.model)
        self._model = _HAIKU_MODEL if _HAIKU_MODE else base_model
        self._max_tokens = company_config.token_overrides.get("president", pres.max_tokens)
        self._max_loops = pres.max_delegation_loops
        self._system_prompt = pres.render_system_prompt(company_config)
        self._delegate_tools, self._tool_to_role = self._build_delegate_tools()
        self.session_input_tokens: int = 0
        self.session_output_tokens: int = 0
        self.session_cost_jpy: float = 0.0

    def _build_delegate_tools(self) -> tuple[list[dict[str, Any]], dict[str, str]]:
        tools: list[dict[str, Any]] = []
        tool_to_role: dict[str, str] = {}
        for role_id in self.company.active_skill_ids:
            if role_id == "president":
                continue
            skill = self.registry.get_skill(role_id)
            tool_name = f"delegate_to_{role_id}"
            tools.append({
                "name": tool_name,
                "description": skill.delegation_description or f"{skill.display_name}に指示を出す",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "task": {
                            "type": "string",
                            "description": skill.delegation_task_description or "具体的な指示内容",
                        }
                    },
                    "required": ["task"],
                },
            })
            tool_to_role[tool_name] = role_id
        return tools, tool_to_role

    async def _call_employee(self, role_id: str, task: str) -> str:
        employee = create_employee_from_skill(role_id, self.company, self.registry, self.client)
        self._logger.info(f"  [{employee.config.name}] 指示受信: {task[:60]}...")
        result = await employee.run(task)
        cost = _cost_jpy(employee.config.model, employee.last_input_tokens, employee.last_output_tokens)
        self.session_input_tokens += employee.last_input_tokens
        self.session_output_tokens += employee.last_output_tokens
        self.session_cost_jpy += cost
        self._logger.info(f"  [{employee.config.name}] 報告書完成 (¥{cost:.1f})")
        return result

    async def _process_tool_calls(
        self, tool_uses: list[anthropic.types.ToolUseBlock]
    ) -> list[dict[str, Any]]:
        async def run_one(tool: anthropic.types.ToolUseBlock) -> dict[str, Any]:
            role_id = self._tool_to_role[tool.name]
            task = tool.input["task"]  # type: ignore[index]
            result = await self._call_employee(role_id, task)
            return {"type": "tool_result", "tool_use_id": tool.id, "content": result}

        return list(await asyncio.gather(*[run_one(t) for t in tool_uses]))

    def _save_log(self, task: str, conversation: list[dict[str, Any]], result: str) -> None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_path = self.log_dir / f"session_{timestamp}.json"
        log_path.write_text(
            json.dumps(
                {
                    "timestamp": timestamp,
                    "company_id": self.company.company_id,
                    "task": task,
                    "conversation": conversation,
                    "final_decision": result,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        self._logger.info(f"ログ保存: {log_path}")

    def _mock_run(self, task: str) -> str:
        short = task[:80] + ("..." if len(task) > 80 else "")
        dept_names = [
            self.registry.get_skill(rid).display_name
            for rid in self.company.active_skill_ids
            if rid != "president"
        ]
        delegations = "\n".join(f"- **{d}** に分析・実行を指示" for d in dept_names[:4])
        return (
            f"## 社長決裁レポート（モック）\n\n"
            f"**タスク:** {short}\n\n"
            f"### 各部門への指示\n{delegations}\n\n"
            "### 統合判断\n"
            "各部門の報告を統合した結果、以下の戦略方針を決定します。\n\n"
            "1. **最優先**: 収益に直結する施策を30日以内に実行\n"
            "2. **体制整備**: 人材・プロセスの見直しを並行して推進\n"
            "3. **中長期**: ブランド・顧客基盤の拡充で持続的成長を実現\n\n"
            "### 経営指標目標\n"
            "| 指標 | 現状 | 3ヶ月後目標 |\n"
            "|------|------|------------|\n"
            "| 売上成長率 | ベースライン | +20% |\n"
            "| 顧客獲得コスト | ベースライン | -15% |\n"
            "| NPS | ベースライン | +10pt |\n\n"
            "> ⚠️ これはMOCK_AI=trueによるモックレスポンスです。実際のAI分析ではありません。"
        )

    async def run(self, task: str) -> str:
        self._logger.info(f"[{self.company.company_name} 社長] タスク受信: {task}")

        if _MOCK_AI:
            result = self._mock_run(task)
            self._save_log(task, [], result)
            return result

        messages: list[dict[str, Any]] = [{"role": "user", "content": task}]
        final_text = ""

        for _ in range(self._max_loops):
            response = await self.client.messages.create(
                model=self._model,
                max_tokens=self._max_tokens,
                system=[
                    {
                        "type": "text",
                        "text": self._system_prompt,
                        "cache_control": {"type": "ephemeral"},
                    }
                ],
                tools=self._delegate_tools,  # type: ignore[arg-type]
                messages=messages,
            )

            self.session_input_tokens += response.usage.input_tokens
            self.session_output_tokens += response.usage.output_tokens
            self.session_cost_jpy += _cost_jpy(self._model, response.usage.input_tokens, response.usage.output_tokens)

            assistant_content = [block.model_dump() for block in response.content]
            messages.append({"role": "assistant", "content": assistant_content})

            for block in response.content:
                if block.type == "text":
                    final_text = block.text

            if response.stop_reason == "end_turn":
                break

            if response.stop_reason == "tool_use":
                tool_uses = [b for b in response.content if b.type == "tool_use"]
                self._logger.info(f"[社長] {len(tool_uses)}部門に指示を委譲")
                tool_results = await self._process_tool_calls(tool_uses)  # type: ignore[arg-type]
                messages.append({"role": "user", "content": tool_results})
            else:
                break

        self._save_log(task, messages, final_text)
        return final_text

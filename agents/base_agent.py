import os
from dataclasses import dataclass
import anthropic

# MOCK_AI=true  → Claude API 呼び出しをスキップ（検証用・完全無料）
# HAIKU_MODE=true → 全エージェントを claude-haiku-4-5-20251001 に切り替え（最安値）
_MOCK_AI   = os.environ.get("MOCK_AI",    "").lower() in ("1", "true", "yes")
_HAIKU_MODE = os.environ.get("HAIKU_MODE", "").lower() in ("1", "true", "yes")
_HAIKU_MODEL = "claude-haiku-4-5-20251001"


@dataclass
class AgentConfig:
    name: str
    role: str
    model: str
    system_prompt: str
    max_tokens: int = 2048
    language: str = "ja"


class BaseAgent:
    def __init__(self, config: AgentConfig, client: anthropic.AsyncAnthropic) -> None:
        self.config = config
        self.client = client
        self.last_input_tokens: int = 0
        self.last_output_tokens: int = 0

    async def run(self, instruction: str) -> str:
        if _MOCK_AI:
            return self._mock_response(instruction)

        model = _HAIKU_MODEL if _HAIKU_MODE else self.config.model
        response = await self.client.messages.create(
            model=model,
            max_tokens=self.config.max_tokens,
            system=[
                {
                    "type": "text",
                    "text": self.config.system_prompt,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[{"role": "user", "content": instruction}],
        )
        self.last_input_tokens = response.usage.input_tokens
        self.last_output_tokens = response.usage.output_tokens
        content = response.content[0]
        if content.type != "text":
            raise ValueError(f"Unexpected response type: {content.type}")
        return content.text

    def _mock_response(self, instruction: str) -> str:
        self.last_input_tokens = 100
        self.last_output_tokens = 200
        role = self.config.role
        name = self.config.name
        short_task = instruction[:60] + ("..." if len(instruction) > 60 else "")
        return (
            f"## {name}（{role}）— モック報告書\n\n"
            f"**受領タスク:** {short_task}\n\n"
            "### 分析結果\n"
            "- 現状の市場環境を分析し、3つの重点施策を特定しました\n"
            "- リソース配分の最適化により20%のコスト削減が見込めます\n"
            "- 優先度の高い施策から順次実行することを推奨します\n\n"
            "### 推奨アクション\n"
            "1. **即時対応**: KPIの見直しと目標再設定（1週間以内）\n"
            "2. **短期施策**: チーム体制の強化と役割明確化（1ヶ月以内）\n"
            "3. **中期戦略**: 新規チャネル開拓とブランド強化（3ヶ月以内）\n\n"
            "> ⚠️ これはMOCK_AI=trueによるモックレスポンスです。実際のAI分析ではありません。"
        )

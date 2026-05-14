from dataclasses import dataclass, field
import anthropic


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
        response = await self.client.messages.create(
            model=self.config.model,
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

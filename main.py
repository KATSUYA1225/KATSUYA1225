import argparse
import asyncio
import logging
import os
from pathlib import Path

import anthropic
from dotenv import load_dotenv

from agents import CompanyConfig, PresidentAgent, SkillRegistry

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(message)s",
    datefmt="%H:%M:%S",
)

DEFAULT_CONFIG = Path("companies/example_tech.yaml")


async def main(config_path: Path, task: str) -> None:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise EnvironmentError("ANTHROPIC_API_KEY が設定されていません。.env ファイルを確認してください。")

    registry = SkillRegistry()
    company = CompanyConfig.from_yaml(config_path, registry)

    print("\n" + "=" * 60)
    print(f"  企業: {company.company_name}")
    print(f"  スキル: {', '.join(company.active_skill_ids)}")
    print(f"  タスク: {task}")
    print("=" * 60 + "\n")

    async with anthropic.AsyncAnthropic(api_key=api_key) as client:
        president = PresidentAgent(client, company, registry)
        result = await president.run(task)

    print("\n" + "=" * 60)
    print("  社長決裁")
    print("=" * 60)
    print(result)
    print("=" * 60 + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AI企業OS")
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG,
        help="企業設定YAMLファイルのパス（デフォルト: companies/example_tech.yaml）",
    )
    parser.add_argument(
        "--task",
        type=str,
        default="新規顧客獲得コストを下げるための施策を立案してください。",
        help="社長に依頼するタスク",
    )
    args = parser.parse_args()
    asyncio.run(main(args.config, args.task))

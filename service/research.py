"""業界リサーチ — DuckDuckGo Instant Answer API + Claude 構造化分析"""
from __future__ import annotations

import asyncio
import json
import urllib.parse
from typing import Any, AsyncGenerator

import aiohttp

DDG_API = "https://api.duckduckgo.com/"
CLI_MODEL = "claude-sonnet-4-6"


def _sse(type_: str, **kw: Any) -> str:
    return f"data: {json.dumps({'type': type_, **kw}, ensure_ascii=False)}\n\n"


async def _ddg_search(query: str, timeout: int = 8) -> str:
    """DuckDuckGo Instant Answer APIで検索し、テキストを返す"""
    params = {
        "q": query, "format": "json",
        "no_html": "1", "no_redirect": "1", "kl": "jp-jp",
    }
    url = DDG_API + "?" + urllib.parse.urlencode(params)
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=timeout)) as resp:
                if resp.status != 200:
                    return ""
                data = await resp.json(content_type=None)
        parts: list[str] = []
        if data.get("AbstractText"):
            parts.append(data["AbstractText"])
        for topic in data.get("RelatedTopics", [])[:4]:
            if isinstance(topic, dict) and topic.get("Text"):
                parts.append(topic["Text"])
        return "\n".join(parts)
    except Exception:
        return ""


async def _call_claude(prompt: str, system: str) -> str:
    proc = await asyncio.create_subprocess_exec(
        "claude", "-p", prompt,
        "--system-prompt", system,
        "--model", CLI_MODEL,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, _ = await proc.communicate()
    return stdout.decode().strip()


async def run_research_stream(
    company_id: str,
    dna: dict[str, Any],
) -> AsyncGenerator[str, None]:
    """
    業界リサーチ → 競合分析 → AI強み分析 をSSEストリームで返す
    """
    from service.company_store import save_dna

    company_name = dna.get("company_name", company_id)
    industry     = dna.get("industry", "")
    competitors  = dna.get("competitors", "")
    strengths    = dna.get("self_strengths", "")
    challenges   = dna.get("challenges", "")
    target       = dna.get("target_customers", "")
    goal_3m      = dna.get("goal_3m", "")
    goal_1y      = dna.get("goal_1y", "")

    # ── Step 1: 業界情報収集 ──────────────────────────────────
    yield _sse("status", step=1, total=4, message=f"🌐 業界情報を収集中...（{industry}）")

    async def _empty() -> str:
        return ""

    industry_info, competitor_info = await asyncio.gather(
        _ddg_search(f"{industry} 業界トレンド 市場規模 2025"),
        _ddg_search(f"{competitors or industry} 競合 強み 差別化") if competitors else _empty(),
    )

    if industry_info:
        yield _sse("research", label="業界情報", content=industry_info[:400])
    else:
        yield _sse("research", label="業界情報", content="Claudeの学習データをもとに分析します")

    # ── Step 2: 競合分析 ─────────────────────────────────────
    yield _sse("status", step=2, total=4, message="📊 競合・市場ポジションを分析中...")

    if competitor_info:
        yield _sse("research", label="競合情報", content=competitor_info[:300])

    # ── Step 3: AI強み分析 ───────────────────────────────────
    yield _sse("status", step=3, total=4, message="🤖 AIが強みレポートを生成中（30秒ほど）...")

    research_context = ""
    if industry_info:
        research_context += f"\n【業界リサーチ結果】\n{industry_info[:600]}"
    if competitor_info:
        research_context += f"\n\n【競合リサーチ結果】\n{competitor_info[:400]}"

    prompt = f"""企業名: {company_name}
業界: {industry}
ターゲット顧客: {target}
主な競合: {competitors}
自社の強み（自己評価）: {strengths}
現在の課題: {challenges}
3ヶ月目標: {goal_3m}
1年目標: {goal_1y}
{research_context}

上記の情報・リサーチ結果をもとに、以下の観点で徹底分析してください：

1. 自己評価された強みの客観的検証（競合・市場データと照合）
2. 業界トレンドとの照合（時流に乗れているか、ズレはないか）
3. 競合との差別化ポイントの特定（勝てる領域はどこか）
4. 潜在的に見落とされている優位性（気づいていない強み）
5. 強みを軸にした具体的な戦略方向性（3案）

【強みレポート】として以下の構成で出力してください：

## ✅ 強みの検証（自己評価 vs 客観評価）
## 🎯 競合優位性（勝てる差別化ポイント）
## 💎 潜在的な強み（見落とされていた優位性）
## 🚀 推奨戦略方向性（具体的な3案）
## 📊 優先アクション（最初の30日でやること）"""

    system = (
        f"あなたは{company_name}の強み発見を専門とする経営コンサルタントです。"
        f"業界: {industry}。"
        "Webリサーチと企業DNAデータを組み合わせ、"
        "客観的事実と論理的思考をもとに企業の真の強みを発見・言語化します。"
        "感情論ではなく、競合比較・市場ポジション・顧客価値の観点から分析し、"
        "実行可能な戦略方向性を提案します。"
    )

    try:
        report = await _call_claude(prompt, system)
    except Exception as exc:
        yield _sse("error", message=f"分析エラー: {exc}")
        return

    # ── Step 4: 保存 ─────────────────────────────────────────
    yield _sse("status", step=4, total=4, message="💾 レポートを保存中...")
    save_dna(company_id, {"strength_report": report})

    yield _sse("result", content=report)
    yield "data: [DONE]\n\n"

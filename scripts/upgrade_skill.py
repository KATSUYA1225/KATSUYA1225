#!/usr/bin/env python3
"""
スキルアップグレードCLI

使い方:
  python scripts/upgrade_skill.py --skill marketing
  python scripts/upgrade_skill.py --skill marketing --apply
  python scripts/upgrade_skill.py --list-feedback
  python scripts/upgrade_skill.py --all --dry-run
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# プロジェクトルートをパスに追加
sys.path.insert(0, str(Path(__file__).parent.parent))

from service.skill_feedback import get_all_summaries, get_version_history
from service.skill_upgrader import generate_upgrade_proposal, apply_upgrade


def cmd_list_feedback(args: argparse.Namespace) -> None:
    summaries = get_all_summaries()
    if not summaries:
        print("フィードバックデータがまだありません。")
        return

    print(f"\n{'スキルID':<25} {'件数':>4} {'平均':>5}  {'最新メモ'}")
    print("-" * 70)
    for sid, s in sorted(summaries.items(), key=lambda x: -(x[1]["avg_rating"] or 0)):
        avg = f"{s['avg_rating']:.1f}" if s["avg_rating"] else "  -"
        note = (s["recent_notes"][0][:30] + "…") if s["recent_notes"] else ""
        print(f"{sid:<25} {s['count']:>4} {avg:>5}  {note}")


def cmd_upgrade(args: argparse.Namespace) -> None:
    skill_ids = args.skill if isinstance(args.skill, list) else [args.skill]

    for skill_id in skill_ids:
        print(f"\n{'='*60}")
        print(f"  スキル: {skill_id}")
        print(f"{'='*60}")

        print("→ 改善案を生成中...")
        proposal = generate_upgrade_proposal(skill_id, dry_run=args.dry_run)

        print(f"\n現在バージョン : {proposal['current_version']}")
        print(f"提案バージョン : {proposal['proposed_version']}")
        print(f"\nフィードバック統計:")
        fb = proposal["feedback_summary"]
        print(f"  件数: {fb['count']}, 平均評価: {fb.get('avg_rating', 'N/A')}")

        print(f"\n--- 変更ログ ---")
        print(proposal["changelog"])

        print(f"\n--- プレイブック改善箇所（先頭500文字）---")
        print(proposal["improved_playbook"][:500] + "...")

        if args.apply:
            confirm = input(f"\nこの改善案を適用しますか？ (y/N): ").strip().lower()
            if confirm == "y":
                apply_upgrade(proposal)
                print(f"✅  {skill_id} を v{proposal['proposed_version']} にアップグレードしました。")
            else:
                print("スキップしました。")
        elif not args.dry_run:
            print("\n（--apply フラグなし：変更は保存されていません）")


def cmd_history(args: argparse.Namespace) -> None:
    history = get_version_history(args.skill)
    if not history:
        print(f"'{args.skill}' のバージョン履歴がありません。")
        return
    print(f"\n{args.skill} のアップグレード履歴:")
    for h in history:
        print(f"  v{h['version']} ({h['upgraded_at']}): {h['changelog'][:60]}")


def main() -> None:
    parser = argparse.ArgumentParser(description="スキルアップグレードCLI")
    sub = parser.add_subparsers(dest="cmd")

    # feedback list
    p_fb = sub.add_parser("feedback", help="フィードバック統計を表示")
    p_fb.set_defaults(func=cmd_list_feedback)

    # upgrade
    p_up = sub.add_parser("upgrade", help="スキルの改善案を生成")
    p_up.add_argument("--skill", required=True, help="スキルID (例: marketing)")
    p_up.add_argument("--apply", action="store_true", help="改善案を適用する")
    p_up.add_argument("--dry-run", action="store_true", help="Claudeを呼ばずに動作確認")
    p_up.set_defaults(func=cmd_upgrade)

    # history
    p_hist = sub.add_parser("history", help="スキルのバージョン履歴を表示")
    p_hist.add_argument("--skill", required=True)
    p_hist.set_defaults(func=cmd_history)

    args = parser.parse_args()
    if not args.cmd:
        parser.print_help()
        return

    args.func(args)


if __name__ == "__main__":
    main()

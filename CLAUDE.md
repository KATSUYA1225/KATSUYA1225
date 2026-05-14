# AI企業運営プロジェクト

## プロジェクト概要

AI社長（President Agent）が複数の従業員AI（Employee Agents）を組織化し、実際の企業運営をシミュレートするマルチエージェントシステム。

## 組織構造

```
AI社長（President Agent）
├── 経営企画部長（Strategy Agent）
├── 開発部長（Engineering Agent）
├── 営業部長（Sales Agent）
├── マーケティング部長（Marketing Agent）
├── 財務部長（Finance Agent）
└── HR部長（HR Agent）
```

## エージェント定義

### AI社長（President Agent）
- 役割: 全体戦略の策定・意思決定・部門間調整
- 権限: 全エージェントへの指示・評価・リソース配分
- 使用モデル: `claude-opus-4-7`（最高性能）

### 従業員エージェント共通仕様
- 使用モデル: `claude-sonnet-4-6`（コスト効率重視）
- 各部門の専門知識に特化したシステムプロンプト
- 社長からの指示を受け取り、報告書を返す

## 技術スタック

- **言語**: Python 3.11+
- **AI SDK**: `anthropic` (Claude API)
- **エージェント間通信**: 非同期メッセージキュー
- **状態管理**: ファイルベース or データベース（TBD）

## ディレクトリ構成（予定）

```
/
├── CLAUDE.md               # このファイル
├── agents/
│   ├── president.py        # AI社長エージェント
│   ├── strategy.py         # 経営企画エージェント
│   ├── engineering.py      # 開発エージェント
│   ├── sales.py            # 営業エージェント
│   ├── marketing.py        # マーケティングエージェント
│   ├── finance.py          # 財務エージェント
│   └── hr.py               # HRエージェント
├── core/
│   ├── message_bus.py      # エージェント間メッセージング
│   ├── task_manager.py     # タスク管理
│   └── report_generator.py # 報告書生成
├── prompts/
│   └── *.md                # 各エージェントのシステムプロンプト
├── logs/                   # 会議録・意思決定ログ
└── main.py                 # エントリポイント
```

## 開発ガイドライン

### エージェント実装ルール
- 全エージェントは `BaseAgent` クラスを継承する
- エージェント間通信は直接呼び出しではなくメッセージバス経由
- 全ての意思決定はログに記録する
- プロンプトキャッシュ（`cache_control`）を積極活用してコスト削減

### コーディング規約
- 型ヒントを必ず付ける
- 非同期処理は `asyncio` を使用
- エラーは握りつぶさず適切に伝播させる

### Claude API 使用方針
- 社長エージェント: `claude-opus-4-7`
- 従業員エージェント: `claude-sonnet-4-6`
- バッチ処理が可能なタスクは Batch API を使用
- システムプロンプトには必ず `cache_control: {"type": "ephemeral"}` を設定

## 実行方法

```bash
# 環境変数設定
export ANTHROPIC_API_KEY=your_api_key

# 全エージェント起動
python main.py

# 特定タスクを社長に依頼
python main.py --task "新規事業計画を立案してください"
```

## 注意事項

- API コストに注意。開発中はモデルを `claude-haiku-4-5-20251001` に切り替えてテスト可能
- 無限ループによるAPI過剰消費に注意。各エージェントの呼び出し回数に上限を設ける
- 機密情報（APIキー等）は `.env` ファイルで管理し、絶対にコミットしない

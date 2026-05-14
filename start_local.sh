#!/usr/bin/env bash
# ローカル検証用起動スクリプト
# 使い方:
#   ./start_local.sh          # モックモード（APIコスト¥0）
#   ./start_local.sh haiku    # Haikuモード（最安値・本物AI）
#   ./start_local.sh real     # 本番モード（通常コスト）

set -e
cd "$(dirname "$0")"

MODE=${1:-mock}

# 依存パッケージ確認
pip install -q -r requirements.txt

mkdir -p data/dna logs

case "$MODE" in
  mock)
    echo "🟡 モックモード起動（APIコスト: ¥0）"
    export MOCK_AI=true
    export ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY:-"mock-key-not-used"}
    ;;
  haiku)
    echo "🟢 Haikuモード起動（最安値モデル使用）"
    export HAIKU_MODE=true
    if [ -z "$ANTHROPIC_API_KEY" ]; then
      echo "❌ ANTHROPIC_API_KEY が未設定です。.envファイルを確認してください。"
      exit 1
    fi
    ;;
  real)
    echo "🔴 本番モード起動"
    if [ -z "$ANTHROPIC_API_KEY" ]; then
      echo "❌ ANTHROPIC_API_KEY が未設定です。.envファイルを確認してください。"
      exit 1
    fi
    ;;
  *)
    echo "使い方: $0 [mock|haiku|real]"
    exit 1
    ;;
esac

# .envがあれば読み込む
if [ -f .env ]; then
  export $(grep -v '^#' .env | grep -v '^$' | xargs) 2>/dev/null || true
fi

echo ""
echo "🚀 サーバー起動: http://localhost:8000"
echo "   API docs:     http://localhost:8000/docs"
echo ""
echo "Codespaceの場合: ポート8000を「公開」に設定するとURLが発行されます"
echo "  (ポートタブ → 8000 → 右クリック → ポートの可視性 → Public)"
echo ""

uvicorn service.api:app --host 0.0.0.0 --port 8000 --reload

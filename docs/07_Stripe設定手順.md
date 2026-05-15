# Stripe設定手順

所要時間：約30分

---

## 前提

- Renderデプロイが完了していること
- 銀行口座情報（売上の受け取り先として必要）

---

## Step 1. Stripeアカウント作成

https://stripe.com/jp → 「今すぐ始める」

メールアドレス・パスワードで登録。

---

## Step 2. テストモードで動作確認

最初は「テストモード」で進める（実際に課金されない）。

ダッシュボード右上のトグルで「**テストモード**」になっていることを確認。

---

## Step 3. 商品・価格を作成

「**製品カタログ**」→「**製品を追加**」

### Starter プラン
| 項目 | 値 |
|------|-----|
| 製品名 | AI企業OS Starter |
| 価格 | ¥9,800 |
| 請求期間 | 月次 |
| 通貨 | JPY |

→ 「**保存**」後に表示される `price_xxxxx` をメモ

### Growth プラン
| 項目 | 値 |
|------|-----|
| 製品名 | AI企業OS Growth |
| 価格 | ¥29,800 |
| 請求期間 | 月次 |
| 通貨 | JPY |

### Business プラン
| 項目 | 値 |
|------|-----|
| 製品名 | AI企業OS Business |
| 価格 | ¥59,800 |
| 請求期間 | 月次 |
| 通貨 | JPY |

---

## Step 4. APIキーを取得

「**開発者**」→「**APIキー**」

- 公開可能キー（`pk_test_xxx`）: フロントエンド用（今は未使用）
- シークレットキー（`sk_test_xxx`）: バックエンド用 → **Renderに設定**

---

## Step 5. Renderに環境変数を追加

Renderダッシュボード → ai-kigyo-os → **Environment**

| 変数名 | 値 |
|--------|-----|
| `STRIPE_SECRET_KEY` | `sk_test_xxx`（テスト中）→ 本番は `sk_live_xxx` |
| `STRIPE_PRICE_GROWTH` | `price_xxxxx`（Growthの価格ID） |
| `STRIPE_PRICE_BUSINESS` | `price_xxxxx`（Businessの価格ID） |

---

## Step 6. Webhook設定

「**開発者**」→「**Webhook**」→「**エンドポイントを追加**」

| 項目 | 値 |
|------|-----|
| エンドポイントURL | `https://ai-kigyo-os.onrender.com/billing/webhook` |
| リッスンするイベント | `checkout.session.completed` |

→ Webhook シークレット（`whsec_xxx`）を Renderの `STRIPE_WEBHOOK_SECRET` に設定

---

## Step 7. テスト決済

テストカード番号: `4242 4242 4242 4242`
有効期限: 任意の未来の日付
CVC: 任意3桁

---

## Step 8. 本番モードへ切替

本番で使う場合：
1. Stripe ダッシュボードで本番用APIキーを取得
2. Renderの `STRIPE_SECRET_KEY` を `sk_live_xxx` に変更
3. 銀行口座を登録（売上受け取り先）

---

## Claude Code への報告内容

設定完了後、以下を教えてもらえれば即対応：
- Starter の Price ID: `price_xxxxx`
- Growth の Price ID: `price_xxxxx`
- Business の Price ID: `price_xxxxx`

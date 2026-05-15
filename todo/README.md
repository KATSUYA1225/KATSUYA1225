# あとでやることリスト

作成日：2026-05-15

---

## 🔴 最優先（Renderデプロイ前に必要）

### 1. Renderデプロイ
- render.com にログイン
- `New` → `Web Service` → GitHub `KATSUYA1225/KATSUYA1225` を連携
- `render.yaml` が自動検出される → Deploy
- 完了後のURL例：`https://ai-kigyo-os.onrender.com`

### 2. Formspree確認
- [formspree.io](https://formspree.io) にログイン
- フォームID `xeoqkqzn` が自分のアカウントに紐づいているか確認
- 未登録なら `New Form` を作成してIDを `static/register.html` の665行目に反映

---

## 🟡 X投稿（デプロイ後すぐ）

### 3. X毎日投稿スタート
- 投稿文：`sales/sns_posts_x.md` に10本分完成済み
- スケジュール：月〜金 毎日1本
- 月：POST 01（数字系）、火：POST 04（教育系）、水：POST 02（デモ系）、木：POST 05（思想系）、金：POST 03（CTA強め）

### 4. Xプロフィール更新
- プロフィール文にAI企業OSへの言及を追加
- URLを `https://ai-kigyo-os.onrender.com/register` に設定

---

## 🟢 今月中

### 5. Google Analytics（GA4）設定
- [analytics.google.com](https://analytics.google.com) でプロパティ作成
- 測定IDを取得（`G-XXXXXXXXXX` 形式）
- `static/register.html` の20行目付近のコメントアウトを解除して測定IDを設定
- `static/landing2.html` にも同じタグを追加

### 6. Stripe設定（正式ローンチ前）
- [stripe.com](https://stripe.com) でアカウント作成
- 3プランの月額サブスク商品を作成
  - Starter：¥9,800/月
  - Growth：¥29,800/月
  - Business：¥59,800/月
- Price IDを取得 → Renderの環境変数に設定

---

## 🔵 正式ローンチ時（6月1日）

### 7. 先行登録者への一斉案内メール
- Formspreeで収集したメールに一斉送信
- 内容：正式ローンチお知らせ + 初月50%オフクーポン + 支払いリンク

### 8. Liverty Realmでの自社実運用開始
- AI企業OSを使って実際の業務をこなす
- 使用ログ・事例をX発信に活用（「AI社長に任せてみた」シリーズ）

---

## 📋 いつかやる

- OGP画像の品質向上（デザイナーに依頼 or Canvaで作成）
- 導入事例ページ作成（2〜3社分）
- Slack/LINE連携
- 無料トライアル14日間の実装

"""Stripe課金統合 — サブスクリプション管理"""
from __future__ import annotations

import os
from typing import Any

import stripe

# Stripe初期化（テストキー / 本番キーは環境変数で切り替え）
stripe.api_key = os.environ.get("STRIPE_SECRET_KEY", "")
WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")

# プランごとのStripe Price ID（Stripe ダッシュボードで作成後に.envに設定）
PLAN_PRICES: dict[str, str] = {
    "growth":     os.environ.get("STRIPE_PRICE_GROWTH",     "price_growth_test"),
    "business":   os.environ.get("STRIPE_PRICE_BUSINESS",   "price_business_test"),
    "enterprise": os.environ.get("STRIPE_PRICE_ENTERPRISE", "price_enterprise_test"),
}

PLAN_INFO: dict[str, dict[str, Any]] = {
    "starter": {
        "name": "Starter",
        "price_jpy": 9800,
        "description": "必須スキル3種 + アドオン最大2種",
        "features": ["AI社長", "マーケティング", "SNS広報", "+ 選択アドオン×2"],
    },
    "growth": {
        "name": "Growth",
        "price_jpy": 29800,
        "description": "必須スキル + 業種汎用スキル最大5種",
        "features": ["全Starterスキル", "営業・財務・HR・分析・プロダクト", "コピーライター・動画・EC"],
    },
    "business": {
        "name": "Business",
        "price_jpy": 59800,
        "description": "全スキル + プロフェッショナルスキル",
        "features": ["全Growthスキル", "ブランドデザイン・建築・UI/UX", "医療・不動産・製造業など専門スキル"],
    },
    "enterprise": {
        "name": "Enterprise",
        "price_jpy": 0,
        "description": "専用AIチーム構築 + カスタム対応",
        "features": ["全スキル使い放題", "カスタムスキル開発", "専任サポート", "API直接利用"],
    },
}


def is_configured() -> bool:
    return bool(stripe.api_key and not stripe.api_key.startswith("sk_test_dummy"))


async def create_checkout_session(
    user_id: str,
    email: str,
    plan: str,
    success_url: str,
    cancel_url: str,
) -> str:
    """Stripe Checkout セッションを作成してURLを返す"""
    if not is_configured():
        raise ValueError("Stripe APIキーが設定されていません（.envにSTRIPE_SECRET_KEYを追加してください）")

    price_id = PLAN_PRICES.get(plan)
    if not price_id:
        raise ValueError(f"無効なプラン: {plan}")

    session = stripe.checkout.Session.create(
        customer_email=email,
        mode="subscription",
        line_items=[{"price": price_id, "quantity": 1}],
        success_url=success_url + "?session_id={CHECKOUT_SESSION_ID}",
        cancel_url=cancel_url,
        metadata={"user_id": user_id, "plan": plan},
        subscription_data={"metadata": {"user_id": user_id, "plan": plan}},
    )
    return session.url  # type: ignore[return-value]


def verify_webhook(payload: bytes, sig_header: str) -> dict[str, Any]:
    """Stripe Webhookの署名を検証してイベントを返す"""
    if not WEBHOOK_SECRET:
        raise ValueError("STRIPE_WEBHOOK_SECRETが設定されていません")
    event = stripe.Webhook.construct_event(payload, sig_header, WEBHOOK_SECRET)
    return event  # type: ignore[return-value]


def extract_plan_from_event(event: dict[str, Any]) -> tuple[str, str] | None:
    """webhookイベントから (user_id, plan) を抽出する"""
    etype = event.get("type", "")
    sub = event.get("data", {}).get("object", {})
    user_id = sub.get("metadata", {}).get("user_id", "")
    plan = sub.get("metadata", {}).get("plan", "starter")

    if etype in ("customer.subscription.created", "customer.subscription.updated"):
        status = sub.get("status", "")
        if status in ("active", "trialing"):
            return user_id, plan
    if etype == "customer.subscription.deleted":
        return user_id, "starter"
    return None

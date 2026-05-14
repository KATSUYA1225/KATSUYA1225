"""SMTP メール通知（任意設定 — 未設定でも動作に影響なし）"""
from __future__ import annotations

import os
import smtplib
import threading
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

SMTP_HOST    = os.environ.get("SMTP_HOST", "")
SMTP_PORT    = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER    = os.environ.get("SMTP_USER", "")
SMTP_PASS    = os.environ.get("SMTP_PASS", "")
NOTIFY_EMAIL = os.environ.get("NOTIFY_EMAIL", "")


def is_configured() -> bool:
    return bool(SMTP_HOST and SMTP_USER and SMTP_PASS and NOTIFY_EMAIL)


def _send(company_name: str, task: str, result: str, cost_ref: float) -> None:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"【AI企業OS】{company_name}のタスクが完了しました"
    msg["From"]    = SMTP_USER
    msg["To"]      = NOTIFY_EMAIL

    snippet = result[:1500] + ("..." if len(result) > 1500 else "")
    text = f"企業: {company_name}\nタスク: {task}\n参考料金: ¥{cost_ref}\n\n{result}"
    html = f"""<html><body style="font-family:sans-serif;color:#333;max-width:600px;margin:0 auto;padding:20px">
<h2 style="color:#7c3aed">AI企業OS — タスク完了</h2>
<table style="width:100%;border-collapse:collapse;margin:16px 0;font-size:14px">
  <tr><td style="padding:8px 12px;background:#f3f4f6;font-weight:600;width:110px">企業</td>
      <td style="padding:8px 12px">{company_name}</td></tr>
  <tr><td style="padding:8px 12px;background:#f3f4f6;font-weight:600">タスク</td>
      <td style="padding:8px 12px">{task}</td></tr>
  <tr><td style="padding:8px 12px;background:#f3f4f6;font-weight:600">参考料金</td>
      <td style="padding:8px 12px">¥{cost_ref}</td></tr>
</table>
<h3 style="color:#374151">社長決裁</h3>
<div style="background:#f9fafb;padding:16px;border-radius:8px;font-size:13px;white-space:pre-wrap;line-height:1.7">{snippet}</div>
<p style="color:#9ca3af;font-size:11px;margin-top:24px">AI企業OS by Future Share Collective</p>
</body></html>"""

    msg.attach(MIMEText(text, "plain", "utf-8"))
    msg.attach(MIMEText(html,  "html",  "utf-8"))

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15) as srv:
            srv.starttls()
            srv.login(SMTP_USER, SMTP_PASS)
            srv.send_message(msg)
    except Exception:
        pass  # メール失敗は本体処理に影響させない


def send_async(company_name: str, task: str, result: str, cost_ref: float) -> None:
    if not is_configured():
        return
    threading.Thread(
        target=_send,
        args=(company_name, task, result, cost_ref),
        daemon=True,
    ).start()

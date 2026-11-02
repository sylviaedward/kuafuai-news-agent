from __future__ import annotations

import os
import smtplib
from email.message import EmailMessage


def render_plain_text(briefing: dict) -> str:
    lines = [briefing["headline"], ""]
    for index, item in enumerate(briefing["items"], 1):
        lines.extend([f"{index}. {item['title']}", item["summary"],
                      f"与你的订阅相关：{item['why']}",
                      f"来源：{item['source']} | {item['published_at']}", item["url"], ""])
    lines.append(briefing["closing"])
    return "\n".join(lines)


def deliver(user: dict, briefing: dict) -> str:
    """The saved run is always available in the in-app inbox; SMTP is optional."""
    host = os.getenv("SMTP_HOST", "")
    sender = os.getenv("SMTP_FROM", "")
    if not host or not sender:
        return "已投递到站内收件箱（未配置 SMTP）"
    message = EmailMessage()
    message["Subject"] = briefing["headline"]
    message["From"] = sender
    message["To"] = user["email"]
    message.set_content(render_plain_text(briefing))
    try:
        port = int(os.getenv("SMTP_PORT", "587"))
        if port == 465:
            server = smtplib.SMTP_SSL(host, port, timeout=15)
        else:
            server = smtplib.SMTP(host, port, timeout=15)
        with server:
            if port != 465 and os.getenv("SMTP_USE_TLS", "true").lower() == "true":
                server.starttls()
            username = os.getenv("SMTP_USER", "")
            if username:
                server.login(username, os.getenv("SMTP_PASSWORD", ""))
            server.send_message(message)
        return "已投递到站内收件箱及邮箱"
    except (OSError, smtplib.SMTPException, ValueError) as exc:
        return f"已投递到站内收件箱；邮件发送失败：{type(exc).__name__}"


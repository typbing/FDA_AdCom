from __future__ import annotations

import requests


def format_notification(payload: dict) -> str:
    doc = payload["document"]
    signal = payload["signal"]
    analysis = payload["analysis"]
    lines = [
        "FDA AdCom document detected",
        f"Title: {doc.get('title')}",
        f"Signal: {signal.get('label')} ({signal.get('action')})",
        f"Approval estimate: {signal.get('probability')}%",
        f"Confidence: {signal.get('confidence')}%",
        f"Provider: {analysis.get('provider')}",
        f"URL: {doc.get('url')}",
    ]
    return "\n".join(lines)


def notify_console(payload: dict) -> None:
    print(format_notification(payload))


def notify_telegram(payload: dict, bot_token: str, chat_id: str) -> None:
    if not bot_token or not chat_id:
        return
    response = requests.post(
        f"https://api.telegram.org/bot{bot_token}/sendMessage",
        json={"chat_id": chat_id, "text": format_notification(payload)},
        timeout=20,
    )
    response.raise_for_status()

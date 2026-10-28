"""Telegram 通知。沒設定 TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID 時只印出訊息內容。"""
from __future__ import annotations

import html
import logging

import requests

from . import config

log = logging.getLogger(__name__)


def _short(text: str, limit: int = 90) -> str:
    text = text or ""
    return text if len(text) <= limit else text[:limit].rstrip() + "…"


def build_message(report: dict) -> str:
    url = f"{config.PAGES_URL}{report['kind']}/{report['id']}.html"
    period = "本週" if report["kind"] == "weekly" else "今日"
    icon = "🗓" if report["kind"] == "weekly" else "📈"
    new_count = sum(1 for r in report["repos"] if r.get("first_time"))

    lines = [f"{icon} <b>{html.escape(report['title'])}</b>"]
    if report["kind"] == "daily":
        lines.append(f"共 {len(report['repos'])} 個 repo，🆕 首次上榜 {new_count} 個")
    lines.append("")
    for r in report["repos"][: config.NOTIFY_TOP]:
        tag = " 🆕" if r.get("first_time") else (f" 🔥{r['streak']}天" if r.get("streak", 0) > 1 else "")
        stars = f"+{r['stars_period']:,} {period}" if r.get("stars_period") else f"⭐ {r['stars']:,}"
        cats = "、".join(r.get("categories", [])[:2])
        lines.append(f"{r['rank']}. <a href=\"{html.escape(r['url'])}\">{html.escape(r['full_name'])}</a>{tag}")
        lines.append(f"   {stars}{'｜' + r['language'] if r.get('language') else ''}{'｜' + html.escape(cats) if cats else ''}")
        if r.get("description"):
            lines.append(f"   {html.escape(_short(r['description']), quote=False)}")
    lines += ["", f"👉 <a href=\"{html.escape(url)}\">完整報告</a>"]
    return "\n".join(lines)


def send(report: dict) -> bool:
    message = build_message(report)
    if not (config.TELEGRAM_BOT_TOKEN and config.TELEGRAM_CHAT_ID):
        log.warning("TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID not set, printing message instead")
        print(message)
        return False
    resp = requests.post(
        f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage",
        json={"chat_id": config.TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML",
              "disable_web_page_preview": True},
        timeout=30,
    )
    if not resp.ok:
        log.error("telegram send failed: %s %s", resp.status_code, resp.text[:300])
        resp.raise_for_status()
    return True

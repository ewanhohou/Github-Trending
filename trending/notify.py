"""Telegram 通知。沒設定 TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID 時只印出訊息內容。"""
from __future__ import annotations

import html
import logging

import requests

from . import config
from .pick import load_post

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
        desc = r.get("description_zh") or r.get("description")
        if desc:
            lines.append(f"   {html.escape(_short(desc, 60), quote=False)}")
    lines += ["", f"👉 <a href=\"{html.escape(url)}\">完整報告</a>"]
    return "\n".join(lines)


CAPTION_LIMIT = 1024


def build_pick_message(pick: dict) -> str:
    """精選通知：貼文放在 <pre> 裡，Telegram 會顯示「複製」按鈕，可以直接貼到 Threads。"""
    r = pick["repo"]
    lines = [f"⭐ <b>今日精選 {html.escape(pick['date'])}</b>：<a href=\"{html.escape(r['url'])}\">{html.escape(r['full_name'])}</a>"]
    if pick.get("reason"):
        lines.append(html.escape(pick["reason"], quote=False))
    lines.append("")
    post = load_post(pick["date"])
    if post:
        lines += ["📝 Threads 貼文（按複製）：", f"<pre>{html.escape(post, quote=False)}</pre>", ""]
    else:
        lines += ["（這次沒有貼文：沒設定 Cloudflare Workers AI，或是精選不是在這次執行產生的）", ""]
    lines.append(f"🔗 留言區連結：{html.escape(r['url'])}")
    return "\n".join(lines)


def _telegram(method: str, *, files=None, **data) -> None:
    resp = requests.post(f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/{method}",
                         data=data if files else None, json=None if files else data, files=files, timeout=60)
    if not resp.ok:
        log.error("telegram %s failed: %s %s", method, resp.status_code, resp.text[:300])
        resp.raise_for_status()


def _configured(message: str) -> bool:
    if config.TELEGRAM_BOT_TOKEN and config.TELEGRAM_CHAT_ID:
        return True
    log.warning("TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID not set, printing message instead")
    print(message)
    return False


def send(report: dict) -> bool:
    message = build_message(report)
    if not _configured(message):
        return False
    _telegram("sendMessage", chat_id=config.TELEGRAM_CHAT_ID, text=message, parse_mode="HTML",
              disable_web_page_preview=True)
    return True


def send_pick(pick: dict) -> bool:
    """送出說明圖與貼文；圖說超過 Telegram 的長度上限時，圖和文字分開送。"""
    message = build_pick_message(pick)
    if not _configured(message):
        return False
    image = config.DOCS_DIR / pick["image"] if pick.get("image") else None
    if not (image and image.exists()):
        _telegram("sendMessage", chat_id=config.TELEGRAM_CHAT_ID, text=message, parse_mode="HTML",
                  disable_web_page_preview=True)
        return True
    fits = len(message) <= CAPTION_LIMIT
    with image.open("rb") as f:
        _telegram("sendPhoto", files={"photo": (image.name, f, "image/jpeg")}, chat_id=config.TELEGRAM_CHAT_ID,
                  caption=message if fits else f"⭐ 今日精選 {pick['date']}：{pick['full_name']}", parse_mode="HTML")
    if not fits:
        _telegram("sendMessage", chat_id=config.TELEGRAM_CHAT_ID, text=message, parse_mode="HTML",
                  disable_web_page_preview=True)
    return True

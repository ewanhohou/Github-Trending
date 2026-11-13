"""Telegram 通知。沒設定 TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID 時只印出訊息內容。"""
from __future__ import annotations

import html
import json
import logging

import requests

from . import config
from .pick import full_post, pick_file

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
    pick = _pick_for(report)
    if pick:
        lines += ["", *build_pick_summary(pick)]
    lines += ["", f"👉 <a href=\"{html.escape(url)}\">完整報告</a>"]
    return "\n".join(lines)


def _pick_for(report: dict) -> dict | None:
    if report["kind"] != "daily" or not pick_file(report["id"]).exists():
        return None
    return json.loads(pick_file(report["id"]).read_text())


CAPTION_LIMIT = 1024


def build_pick_summary(pick: dict) -> list[str]:
    """精選的說明放在日報訊息裡，精選那則只留發文會用到的東西。"""
    r = pick["repo"]
    lines = [f"⭐ <b>今日精選</b>：<a href=\"{html.escape(r['url'])}\">{html.escape(r['full_name'])}</a>"]
    if pick.get("reason"):
        lines.append(html.escape(pick["reason"], quote=False))
    return lines


def build_pick_message(pick: dict) -> str:
    """精選那則的圖說：完整貼文（含標籤）放 <pre>，按「複製」就能直接貼到 Threads。"""
    post = full_post(pick)
    if post:
        return f"<pre>{html.escape(post, quote=False)}</pre>"
    return "（這次沒有貼文：沒設定 Cloudflare Workers AI，或是精選不是在這次執行產生的）"


def build_comment_message(pick: dict) -> str:
    """留言區要貼的那句，另外一則訊息，一樣按「複製」就好。"""
    return f"<pre>🔗 留言區連結：{html.escape(pick['repo']['url'], quote=False)}</pre>"


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


def _send_text(text: str) -> None:
    _telegram("sendMessage", chat_id=config.TELEGRAM_CHAT_ID, text=text, parse_mode="HTML",
              disable_web_page_preview=True)


def send(report: dict) -> bool:
    message = build_message(report)
    if not _configured(message):
        return False
    _send_text(message)
    return True


def send_pick(pick: dict, *, summary: bool = False) -> bool:
    """送出說明圖與貼文，再送一則留言區要貼的連結。summary=True 時先送精選說明，給沒有同時發日報的時候用。
    貼文超過 Telegram 圖說的長度上限時，圖和貼文分開送。"""
    head = "\n".join(build_pick_summary(pick)) if summary else ""
    message = build_pick_message(pick)
    comment = build_comment_message(pick)
    if not _configured("\n\n".join(filter(None, (head, message, comment)))):
        return False
    if head:
        _send_text(head)
    image = config.DOCS_DIR / pick["image"] if pick.get("image") else None
    if not (image and image.exists()):
        _send_text(message)
    else:
        fits = len(message) <= CAPTION_LIMIT
        caption = {"caption": message, "parse_mode": "HTML"} if fits else {}
        with image.open("rb") as f:
            _telegram("sendPhoto", files={"photo": (image.name, f, "image/jpeg")},
                      chat_id=config.TELEGRAM_CHAT_ID, **caption)
        if not fits:
            _send_text(message)
    _send_text(comment)
    return True

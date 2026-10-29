"""每日精選：從今天的日報挑一個最值得推薦的 repo（PICK_DEDUPE_DAYS 天內不重複），
再產生說明圖文案、AI 背景圖、說明圖（docs/picks/<日期>.jpg），以及可以直接貼到 Threads 的貼文。

沒設定 Cloudflare 時只用規則挑選，說明圖用摘要內容與預設背景，也不產生貼文。"""
from __future__ import annotations

import base64
import json
import logging
import math
import re
from datetime import date, timedelta

import requests

from . import config, translate
from .report import latest_report, save_json

log = logging.getLogger(__name__)

PICKS_DOCS = config.DOCS_DIR / "picks"
AI_CATEGORIES = {"AI Agent", "大型語言模型 / LLM", "機器學習 / 深度學習"}
LOW_NOVELTY_KINDS = {"資源清單", "教學 / 課程"}
SHORTLIST = 5
CARD_SIZE = (1080, 1350)  # Threads / IG 直式 4:5

CHOOSE_PROMPT = (
    "你是科技社群的編輯，每天從 GitHub Trending 挑一個最值得推薦的開源專案。"
    "挑選時依序考慮：1) 跟 AI 有關；2) 新奇：少見的點子、做法或用途，看了會想試試；3) 今天的熱度。"
    "避免資源清單、教學合集，以及大家早就知道的老牌大專案。"
    "使用者會給你以 [編號] 開頭的候選清單。只輸出 JSON，格式為 "
    '{"pick": 編號, "reason": "一句話推薦理由，30 字以內，台灣繁體中文"}，不要輸出其他文字。'
)

CARD_PROMPT = (
    "你是科技社群小編，要把一個開源專案濃縮成一張 Threads 說明圖的文案，讓人一眼看懂。"
    "用台灣繁體中文與台灣用語，專案名稱與技術名詞保留英文，文字要短、具體、口語，不要行銷用語。"
    "只輸出 JSON，不要輸出其他文字，格式為："
    '{"hook": "抓住注意力的一句話，16 字以內", '
    '"tagline": "白話說明它是什麼，40 字以內", '
    '"points": [{"icon": "一個 emoji", "title": "重點標題，10 字以內", "text": "說明，22 字以內"}]（剛好 3 個）, '
    '"audience": "適合誰用，20 字以內", '
    '"image_subject": "In English: ONE concrete physical object or visual metaphor for the idea of the project, '
    'for example \'a glowing crystal brain wired to tiny robots\'. Never screens, monitors, documents, paper, books, '
    'signs, labels, charts or user interfaces, because they make the image model draw fake text."}'
    "。英文字母與數字算半個字。"
)

# 背景圖的固定畫風；AI 只決定主體。FLUX 沒有 negative prompt，畫到螢幕或文件時常出現亂碼文字，所以主體只用實體物件
IMAGE_STYLE = (
    "{subject}. Isometric 3D render of a single centered subject floating in empty space, dark navy background, "
    "glowing neon green and cyan rim light, cinematic lighting, soft depth of field, minimalist. "
    "Pure illustration: no text, no letters, no numbers, no words, no logos, no signs, no screens, no user interface."
)

# 說明圖每個欄位在版面上放得下的寬度（全形字數，英數算半個）。提示詞要求得更短，留點餘裕
CARD_LIMITS = {"hook": 20, "tagline": 56, "title": 14, "text": 27, "audience": 26}
CARD_ATTEMPTS = 3

DEFAULT_ICONS = ("✨", "⚡", "🧩")


def _clip(text: str, limit: int) -> str:
    text = re.sub(r"\s+", " ", text or "").strip()
    return text if len(text) <= limit else text[: limit - 1].rstrip("，,、。.；; ") + "…"


def _width(text: str) -> float:
    return sum(0.55 if ord(c) < 128 else 1 for c in text)


def _fit(text: str, limit: float) -> str:
    """放不下時優先在逗號、頓號等斷句處截斷，不留半句；找不到合適的斷點才加「…」。"""
    text = re.sub(r"\s+", " ", text or "").strip()
    if _width(text) <= limit:
        return text
    width, cut, best = 0.0, 0, ""
    for i, c in enumerate(text):
        width += _width(c)
        if width > limit - 1:
            break
        cut = i + 1
        if c in "，,、；;。：:！!？?" and _width(text[:i]) >= limit / 2:
            best = text[:i]
    return best.rstrip() or text[:cut].rstrip("，,、。.；; ") + "…"


def _parse_json(text: str | None) -> dict | None:
    if not text:
        return None
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        data = json.loads(text[start : end + 1])
    except ValueError:
        return None
    return data if isinstance(data, dict) else None


# ---------- 挑選 ----------

def recent_picks(day: date) -> dict[str, str]:
    """day 之前 PICK_DEDUPE_DAYS 天內選過的 repo → 日期。"""
    since = (day - timedelta(days=config.PICK_DEDUPE_DAYS)).isoformat()
    picks = {}
    for path in config.PICKS_DIR.glob("*.json"):
        if since <= path.stem < day.isoformat():
            picks[json.loads(path.read_text())["full_name"]] = path.stem
    return picks


def score(repo: dict, day: date) -> float:
    """規則分數：熱度為主，AI 與新奇度加分，清單類與老牌大專案扣分。"""
    s = math.log1p(repo.get("stars_period") or 0) * 10
    if AI_CATEGORIES & set(repo.get("categories", [])):
        s += 15
    if repo.get("first_time"):
        s += 12
    if repo.get("is_new_repo"):
        s += 12
    if repo.get("features"):
        s += 4
    if repo.get("image") and not repo.get("image_is_og"):
        s += 2
    if repo.get("kind") in LOW_NOVELTY_KINDS or "學習資源 / 清單" in repo.get("categories", []):
        s -= 25
    created = (repo.get("created_at") or "")[:10]
    if created and (day - date.fromisoformat(created)).days > 3 * 365 and repo.get("stars", 0) > 30000:
        s -= 12
    if (repo.get("streak") or 0) > 3:  # 已經紅了好幾天，新鮮感較低
        s -= 4
    return s


def _candidate_line(n: int, r: dict) -> str:
    desc = r.get("description_zh") or r.get("description") or ""
    intro = r.get("intro_zh") or r.get("intro") or ""
    tags = [f"今日 +{r.get('stars_period') or 0} 星", f"總星數 {r.get('stars', 0)}"]
    if r.get("first_time"):
        tags.append("首次上榜")
    if r.get("is_new_repo"):
        tags.append("30 天內建立的新專案")
    cats = "、".join(r.get("categories", [])) or "未分類"
    return f"[{n}] {r['full_name']}｜{'，'.join(tags)}｜分類：{cats}｜{_clip(desc, 120)}｜{_clip(intro, 200)}"


def choose(report: dict, exclude: dict[str, str]) -> tuple[dict, str]:
    """回傳 (repo, 推薦理由)。先用規則分數取前幾名，再讓 AI 從中挑一個。"""
    day = date.fromisoformat(report["date"])
    pool = [r for r in report["repos"] if r["full_name"] not in exclude] or report["repos"]
    shortlist = sorted(pool, key=lambda r: score(r, day), reverse=True)[:SHORTLIST]
    if translate.enabled():
        lines = "\n".join(_candidate_line(n, r) for n, r in enumerate(shortlist, start=1))
        data = _parse_json(translate.chat(CHOOSE_PROMPT, lines, temperature=0.3, max_tokens=300))
        try:
            n = int((data or {}).get("pick"))
        except (TypeError, ValueError):
            n = 0
        if 1 <= n <= len(shortlist):
            return shortlist[n - 1], _clip(str(data.get("reason") or ""), 40)
        log.warning("AI pick not usable (%r), falling back to the top score", data)
    return shortlist[0], ""


# ---------- 文案、貼文、背景圖 ----------

def _repo_brief(r: dict, reason: str) -> str:
    features = r.get("features_zh") or r.get("features") or []
    lines = [
        f"專案：{r['full_name']}",
        f"描述：{r.get('description_zh') or r.get('description') or ''}",
        f"介紹：{_clip(r.get('intro_zh') or r.get('intro') or '', 600)}",
        f"功能：{'；'.join(_clip(f, 120) for f in features[:8])}",
        f"分類：{'、'.join(r.get('categories', []))}　語言：{r.get('language') or '未知'}",
        f"星數：{r.get('stars', 0)}，今天新增 {r.get('stars_period') or 0}",
    ]
    if r.get("first_time"):
        lines.append("今天第一次上 GitHub Trending")
    if r.get("is_new_repo"):
        lines.append("建立不到 30 天的新專案")
    if reason:
        lines.append(f"推薦理由：{reason}")
    return "\n".join(lines)


def _fallback_card(r: dict) -> dict:
    features = r.get("features_zh") or r.get("features") or []
    points = []
    for icon, f in zip(DEFAULT_ICONS, features[:3]):
        m = re.match(r"\s*(.+?)[。.:：—]\s*(.*)", f)
        title, text = (m.group(1), m.group(2)) if m else (f, "")
        points.append({"icon": icon, "title": _fit(title, CARD_LIMITS["title"]), "text": _fit(text, CARD_LIMITS["text"])})
    return {
        "hook": "",
        "tagline": _fit(re.sub(r"https?://\S+", "", r.get("description_zh") or r.get("description") or "").strip(" ."),
                        CARD_LIMITS["tagline"]),
        "points": points,
        "audience": "",
        "image_prompt": "",
    }


def _normalize_card(data: dict) -> dict | None:
    points = [p for p in data.get("points") or [] if isinstance(p, dict) and p.get("title")][:3]
    if not (data.get("tagline") and points):
        return None
    text = lambda v: re.sub(r"\s+", " ", str(v or "")).strip()
    return {
        "hook": text(data.get("hook")),
        "tagline": text(data.get("tagline")),
        "points": [{"icon": _clip(text(p.get("icon")) or DEFAULT_ICONS[i], 4), "title": text(p["title"]),
                    "text": text(p.get("text"))} for i, p in enumerate(points)],
        "audience": text(data.get("audience")),
        "image_subject": _clip(text(data.get("image_subject")), 300),
    }


def _overlong(card: dict) -> list[str]:
    """列出放不進版面的欄位，例如「tagline（61 字，最多 56 字）」。"""
    fields = [(k, card[k], CARD_LIMITS[k]) for k in ("hook", "tagline", "audience")]
    for i, p in enumerate(card["points"], start=1):
        fields += [(f"points 第 {i} 個的 title", p["title"], CARD_LIMITS["title"]),
                   (f"points 第 {i} 個的 text", p["text"], CARD_LIMITS["text"])]
    return [f"{name}（{math.ceil(_width(v))} 字，最多 {limit} 字）" for name, v, limit in fields if _width(v) > limit]


def card_content(r: dict, reason: str) -> dict:
    """請 AI 寫說明圖文案；有欄位太長就附上哪裡太長請它重寫，最後仍太長的在斷句處截短。"""
    best, best_issues = None, None
    if translate.enabled():
        brief = _repo_brief(r, reason)
        user = brief
        for _ in range(CARD_ATTEMPTS):
            data = _parse_json(translate.chat(CARD_PROMPT, user, temperature=0.5, max_tokens=800))
            card = _normalize_card(data) if data else None
            if not card:
                log.warning("card content not usable: %r", data)
                continue
            issues = _overlong(card)
            if best is None or len(issues) < len(best_issues):
                best, best_issues = card, issues
            if not issues:
                break
            log.info("card text too long, asking for a shorter one: %s", "、".join(issues))
            user = (f"{brief}\n\n上一版文案：{json.dumps(card, ensure_ascii=False)}\n"
                    f"這些欄位太長，放不進說明圖：{'、'.join(issues)}。請改寫得更精簡，不要只是截斷，"
                    "其他欄位維持原樣，重新輸出完整 JSON。")
    if not best:
        return _fallback_card(r)
    best["hook"] = _fit(best["hook"], CARD_LIMITS["hook"])
    best["tagline"] = _fit(best["tagline"], CARD_LIMITS["tagline"])
    best["audience"] = _fit(best["audience"], CARD_LIMITS["audience"])
    for p in best["points"]:
        p["title"], p["text"] = _fit(p["title"], CARD_LIMITS["title"]), _fit(p["text"], CARD_LIMITS["text"])
    best["image_prompt"] = IMAGE_STYLE.format(subject=best.pop("image_subject").rstrip(".")) if best.get("image_subject") else ""
    return best


def voice_prompt() -> str:
    return config.VOICE_PROMPT or (config.TEMPLATES_DIR / "voice.md").read_text()


def write_post(r: dict, reason: str, card: dict) -> str:
    if not translate.enabled():
        return ""
    brief = _repo_brief(r, reason)
    if card.get("points"):
        brief += "\n說明圖上的重點：" + "；".join(f"{p['title']} {p['text']}" for p in card["points"])
    post = translate.chat(voice_prompt(), brief, temperature=0.8, max_tokens=900) or ""
    post = re.sub(r"https?://\S+", "", post)
    post = re.sub(r"[ \t]{2,}", " ", post).strip().strip("「」\"")
    return post[:480]


def generate_background(prompt: str) -> bytes | None:
    if not (translate.enabled() and prompt):
        return None
    result = translate.run_model(config.CLOUDFLARE_IMAGE_MODEL, {"prompt": prompt, "steps": 8})
    image = (result or {}).get("image")
    if not image:
        log.warning("background image not generated: %r", str(result)[:200])
        return None
    return base64.b64decode(image)


# ---------- 說明圖 ----------

def _data_uri(data: bytes, mime: str) -> str:
    return f"data:{mime};base64,{base64.b64encode(data).decode()}"


def _fetch_image(url: str, max_bytes: int = 5_000_000) -> str | None:
    try:
        resp = requests.get(url, timeout=20, headers={"User-Agent": config.USER_AGENT})
    except requests.RequestException:
        return None
    mime = resp.headers.get("content-type", "").split(";")[0]
    if not resp.ok or mime not in ("image/png", "image/jpeg", "image/webp", "image/gif") or len(resp.content) > max_bytes:
        return None
    return _data_uri(resp.content, mime)


def render_card(pick: dict, out_path) -> bool:
    """把精選資料排成 1080×1350 的說明圖。沒裝 Playwright 或找不到瀏覽器時回傳 False。"""
    try:
        from playwright.sync_api import Error, sync_playwright
    except ImportError:
        log.warning("playwright not installed, skipping the card image")
        return False
    from .render import _env

    bg_path = PICKS_DOCS / f"{pick['date']}-bg.jpg"
    r = pick["repo"]
    html = _env().get_template("card.html").render(
        pick=pick, r=r, card=pick["card"], width=CARD_SIZE[0], height=CARD_SIZE[1],
        background=_data_uri(bg_path.read_bytes(), "image/jpeg") if bg_path.exists() else None,
        avatar=_fetch_image(r["owner_avatar"] + "&s=160") if r.get("owner_avatar") else None,
        site=config.PAGES_URL.split("://", 1)[-1].rstrip("/"),
    )
    with sync_playwright() as p:
        browser = None
        for kwargs in ({"channel": "chrome"}, {}):  # 優先用系統的 Chrome，省得另外下載瀏覽器
            try:
                browser = p.chromium.launch(**kwargs)
                break
            except Error as e:
                log.info("cannot launch chromium %s: %s", kwargs, str(e).splitlines()[0])
        if not browser:
            log.warning("no browser available, skipping the card image")
            return False
        page = browser.new_page(viewport={"width": CARD_SIZE[0], "height": CARD_SIZE[1]})
        page.set_content(html, wait_until="load")
        page.evaluate("document.fonts.ready")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(out_path), type="jpeg", quality=90)
        browser.close()
    return True


# ---------- 對外 ----------

def pick_file(day_id: str):
    return config.PICKS_DIR / f"{day_id}.json"


def latest_pick() -> dict | None:
    files = sorted(config.PICKS_DIR.glob("*.json"))
    return json.loads(files[-1].read_text()) if files else None


def list_picks() -> dict[str, dict]:
    return {f.stem: json.loads(f.read_text()) for f in config.PICKS_DIR.glob("*.json")}


REPO_KEYS = ("full_name", "url", "description", "description_zh", "language", "stars", "stars_period", "forks",
             "license", "categories", "first_time", "is_new_repo", "owner_avatar", "homepage", "image", "rank")


def build(*, redo: bool = False, render_only: bool = False) -> dict | None:
    """替最新一份日報產生每日精選。同一天已經選過就沿用，redo=True 重新挑選與產生。"""
    report = latest_report("daily")
    if not report:
        log.error("no daily report found")
        return None
    day = date.fromisoformat(report["date"])
    path = pick_file(report["id"])
    pick = json.loads(path.read_text()) if path.exists() and not redo else None

    if pick is None:
        if render_only:
            log.error("no pick for %s yet", report["id"])
            return None
        repo, reason = choose(report, recent_picks(day))
        log.info("picked %s (%s)", repo["full_name"], reason or "by score")
        card = card_content(repo, reason)
        pick = {
            "date": report["id"],
            "full_name": repo["full_name"],
            "reason": reason,
            "repo": {k: repo.get(k) for k in REPO_KEYS},
            "card": card,
            "post": write_post(repo, reason, card),
        }
        background = generate_background(card.get("image_prompt"))
        bg_path = PICKS_DOCS / f"{report['id']}-bg.jpg"
        if background:
            bg_path.parent.mkdir(parents=True, exist_ok=True)
            bg_path.write_bytes(background)
        elif bg_path.exists():
            bg_path.unlink()
        (PICKS_DOCS / f"{report['id']}.jpg").unlink(missing_ok=True)

    image_path = PICKS_DOCS / f"{report['id']}.jpg"
    pick["image"] = f"picks/{image_path.name}" if render_card(pick, image_path) or image_path.exists() else ""
    save_json(path, pick)
    return pick

"""把 data/ 裡的報告 JSON 輸出成 docs/ 下的 GitHub Pages 網頁。每次都全部重建，模板改了舊報告也會跟著更新。"""
from __future__ import annotations

import hashlib
import json
import shutil
from collections import Counter

from jinja2 import Environment, FileSystemLoader, select_autoescape

from . import config, i18n
from .pick import list_picks
from .report import list_reports

LANG_COLORS = {
    "Python": "#3572A5", "TypeScript": "#3178c6", "JavaScript": "#f1e05a", "Go": "#00ADD8", "Rust": "#dea584",
    "Java": "#b07219", "C++": "#f34b7d", "C": "#555555", "C#": "#178600", "Swift": "#F05138", "Kotlin": "#A97BFF",
    "Ruby": "#701516", "PHP": "#4F5D95", "Shell": "#89e051", "Jupyter Notebook": "#DA5B0B", "HTML": "#e34c26",
    "CSS": "#663399", "Vue": "#41b883", "Dart": "#00B4AB", "Zig": "#ec915c", "Lua": "#000080", "Scala": "#c22d40",
    "Elixir": "#6e4a7e", "Haskell": "#5e5086", "MDX": "#fcb32c", "Svelte": "#ff3e00", "Nix": "#7e7eff",
}


def _env() -> Environment:
    env = Environment(loader=FileSystemLoader(config.TEMPLATES_DIR), autoescape=select_autoescape(["html"]))
    env.filters["num"] = lambda n: f"{n:,}" if isinstance(n, int) else n
    env.filters["lang_color"] = lambda lang: LANG_COLORS.get(lang, "#8b949e")
    env.filters["label"] = i18n.label
    return env


def _stats(report: dict) -> dict:
    langs = Counter(r["language"] for r in report["repos"] if r.get("language"))
    cats = Counter(c for r in report["repos"] for c in r.get("categories", []))
    return {"languages": langs.most_common(6), "categories": cats.most_common()}


STATIC_FILES = ("icon.svg", "icon-192.png", "icon-512.png", "icon-maskable-512.png", "apple-touch-icon.png")


def _manifest(lang: str) -> dict:
    t = i18n.STRINGS[lang]
    assets = "../" * i18n.LANGS[lang].count("/")
    return {
        "name": t["site_title"],
        "short_name": "Trending",
        "description": t["site_description"],
        "lang": t["html_lang"],
        "start_url": "./",
        "scope": assets or "./",
        "display": "standalone",
        "background_color": "#0d1117",
        "theme_color": "#0d1117",
        "icons": [
            {"src": f"{assets}icon-192.png", "sizes": "192x192", "type": "image/png"},
            {"src": f"{assets}icon-512.png", "sizes": "512x512", "type": "image/png"},
            {"src": f"{assets}icon-maskable-512.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable"},
            {"src": f"{assets}icon.svg", "sizes": "any", "type": "image/svg+xml"},
        ],
        "shortcuts": [
            {"name": t["shortcut_daily"], "url": "daily/latest.html"},
            {"name": t["shortcut_weekly"], "url": "weekly/latest.html"},
        ],
    }


def _context(lang: str, page: str) -> dict:
    """page 是頁面在該語言根目錄下的路徑，例如 index.html、daily/2026-10-28.html。"""
    prefix = i18n.LANGS[lang]
    home = "../" * page.count("/")
    assets = home + "../" * prefix.count("/")
    return {
        "lang": lang,
        "t": i18n.STRINGS[lang],
        "zh": lang == "zh",
        "home": home,
        "assets": assets,
        # 其他語言的同一頁
        "alternates": [
            {"lang": other, "name": i18n.STRINGS[other]["lang_name"], "hreflang": i18n.STRINGS[other]["hreflang"],
             "href": assets + other_prefix + page, "url": config.PAGES_URL + other_prefix + page}
            for other, other_prefix in i18n.LANGS.items()
        ],
    }


def _render_site(env: Environment, lang: str, daily: list[dict], weekly: list[dict], picks: dict[str, dict]) -> list[str]:
    """輸出一種語言的所有頁面，回傳要預先快取的頁面（相對網站根目錄）。"""
    prefix = i18n.LANGS[lang]
    out = config.DOCS_DIR / prefix
    out.mkdir(parents=True, exist_ok=True)
    if prefix:
        (out / "manifest.webmanifest").write_text(json.dumps(_manifest(lang), ensure_ascii=False, indent=2) + "\n")

    page = env.get_template("report.html")
    precache = [f"{prefix}index.html", f"{prefix}offline.html"] + ([f"{prefix}manifest.webmanifest"] if prefix else [])
    for kind, reports in (("daily", daily), ("weekly", weekly)):
        (out / kind).mkdir(exist_ok=True)
        # reports 由新到舊：前一份（較舊）是 i+1，下一份（較新）是 i-1
        for i, report in enumerate(reports):
            path = f"{kind}/{report['id']}.html"
            html = page.render(report=report, stats=_stats(report), **_context(lang, path),
                               pick=picks.get(report["id"]) if kind == "daily" else None,
                               older=reports[i + 1] if i + 1 < len(reports) else None,
                               newer=reports[i - 1] if i > 0 else None)
            (out / path).write_text(html)
            if i == 0:  # 固定網址給 PWA 捷徑使用
                (out / kind / "latest.html").write_text(html)
                precache.append(prefix + path)

    (out / "index.html").write_text(env.get_template("index.html").render(
        daily=daily, weekly=weekly, pick=picks.get(daily[0]["id"]) if daily else None, **_context(lang, "index.html")))
    (out / "offline.html").write_text(env.get_template("offline.html").render(**_context(lang, "offline.html")))
    return precache


def render_all() -> None:
    env = _env()
    docs = config.DOCS_DIR
    docs.mkdir(parents=True, exist_ok=True)
    shutil.copy(config.TEMPLATES_DIR / "style.css", docs / "style.css")
    for name in STATIC_FILES:
        shutil.copy(config.TEMPLATES_DIR / "static" / name, docs / name)
    (docs / ".nojekyll").touch()
    (docs / "manifest.webmanifest").write_text(json.dumps(_manifest("zh"), ensure_ascii=False, indent=2) + "\n")

    daily, weekly, picks = list_reports("daily"), list_reports("weekly"), list_picks()
    # 預先快取首頁與最新報告；清單或樣式變了 sw.js 內容就會變，瀏覽器會自動更新
    precache = ["./", "style.css", "manifest.webmanifest", *STATIC_FILES]
    for lang in i18n.LANGS:
        precache += _render_site(env, lang, daily, weekly, picks)
    digest = hashlib.sha256()
    for name in precache[1:]:
        digest.update((docs / name).read_bytes())
    sw = env.get_template("sw.js").render(version=digest.hexdigest()[:12], precache=json.dumps(precache),
                                          langs=json.dumps([p for p in i18n.LANGS.values() if p]))
    (docs / "sw.js").write_text(sw)

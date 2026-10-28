"""把 data/ 裡的報告 JSON 輸出成 docs/ 下的 GitHub Pages 網頁。每次都全部重建，模板改了舊報告也會跟著更新。"""
from __future__ import annotations

import hashlib
import json
import shutil
from collections import Counter

from jinja2 import Environment, FileSystemLoader, select_autoescape

from . import config
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
    return env


def _stats(report: dict) -> dict:
    langs = Counter(r["language"] for r in report["repos"] if r.get("language"))
    cats = Counter(c for r in report["repos"] for c in r.get("categories", []))
    return {"languages": langs.most_common(6), "categories": cats.most_common()}


STATIC_FILES = ("icon.svg", "icon-192.png", "icon-512.png", "icon-maskable-512.png", "apple-touch-icon.png")


def _manifest() -> dict:
    return {
        "name": "GitHub Trending 報告",
        "short_name": "Trending",
        "description": "每天整理 GitHub 熱門 repo 是什麼、用在哪",
        "lang": "zh-Hant",
        "start_url": "./",
        "scope": "./",
        "display": "standalone",
        "background_color": "#0d1117",
        "theme_color": "#0d1117",
        "icons": [
            {"src": "icon-192.png", "sizes": "192x192", "type": "image/png"},
            {"src": "icon-512.png", "sizes": "512x512", "type": "image/png"},
            {"src": "icon-maskable-512.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable"},
            {"src": "icon.svg", "sizes": "any", "type": "image/svg+xml"},
        ],
        "shortcuts": [
            {"name": "最新日報", "url": "daily/latest.html"},
            {"name": "最新週報", "url": "weekly/latest.html"},
        ],
    }


def render_all() -> None:
    env = _env()
    docs = config.DOCS_DIR
    docs.mkdir(parents=True, exist_ok=True)
    shutil.copy(config.TEMPLATES_DIR / "style.css", docs / "style.css")
    for name in STATIC_FILES:
        shutil.copy(config.TEMPLATES_DIR / "static" / name, docs / name)
    (docs / ".nojekyll").touch()
    (docs / "manifest.webmanifest").write_text(json.dumps(_manifest(), ensure_ascii=False, indent=2) + "\n")

    daily, weekly = list_reports("daily"), list_reports("weekly")
    page = env.get_template("report.html")
    for kind, reports in (("daily", daily), ("weekly", weekly)):
        out_dir = docs / kind
        out_dir.mkdir(exist_ok=True)
        # reports 由新到舊：前一份（較舊）是 i+1，下一份（較新）是 i-1
        for i, report in enumerate(reports):
            html = page.render(report=report, stats=_stats(report), root="../",
                               older=reports[i + 1] if i + 1 < len(reports) else None,
                               newer=reports[i - 1] if i > 0 else None)
            (out_dir / f"{report['id']}.html").write_text(html)
            if i == 0:  # 固定網址給 PWA 捷徑使用
                (out_dir / "latest.html").write_text(html)

    (docs / "index.html").write_text(env.get_template("index.html").render(daily=daily, weekly=weekly, root=""))
    (docs / "offline.html").write_text(env.get_template("offline.html").render(root=""))

    # 預先快取首頁與最新報告；清單或樣式變了 sw.js 內容就會變，瀏覽器會自動更新
    precache = ["./", "index.html", "offline.html", "style.css", "manifest.webmanifest", *STATIC_FILES]
    precache += [f"{kind}/{reports[0]['id']}.html" for kind, reports in (("daily", daily), ("weekly", weekly)) if reports]
    digest = hashlib.sha256()
    for name in precache[1:]:
        digest.update((docs / name).read_bytes())
    sw = env.get_template("sw.js").render(version=digest.hexdigest()[:12], precache=json.dumps(precache))
    (docs / "sw.js").write_text(sw)

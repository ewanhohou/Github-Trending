"""把 data/ 裡的報告 JSON 輸出成 docs/ 下的 GitHub Pages 網頁。每次都全部重建，模板改了舊報告也會跟著更新。"""
from __future__ import annotations

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


def render_all() -> None:
    env = _env()
    docs = config.DOCS_DIR
    docs.mkdir(parents=True, exist_ok=True)
    shutil.copy(config.TEMPLATES_DIR / "style.css", docs / "style.css")
    (docs / ".nojekyll").touch()

    daily, weekly = list_reports("daily"), list_reports("weekly")
    page = env.get_template("report.html")
    for kind, reports in (("daily", daily), ("weekly", weekly)):
        out_dir = docs / kind
        out_dir.mkdir(exist_ok=True)
        for report in reports:
            html = page.render(report=report, stats=_stats(report), root="../")
            (out_dir / f"{report['id']}.html").write_text(html)

    (docs / "index.html").write_text(env.get_template("index.html").render(daily=daily, weekly=weekly, root=""))

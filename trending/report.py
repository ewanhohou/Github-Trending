"""產生每日／每週報告資料（data/daily/*.json、data/weekly/*.json）並維護上榜歷史。"""
from __future__ import annotations

import json
import logging
from datetime import date, datetime, timedelta

from . import config, github, translate
from .summarize import summarize

log = logging.getLogger(__name__)


def load_history() -> dict:
    if config.HISTORY_FILE.exists():
        return json.loads(config.HISTORY_FILE.read_text())
    return {"repos": {}}


def save_json(path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def today_local() -> date:
    return datetime.now(config.TZ).date()


def week_id(d: date) -> str:
    year, week, _ = d.isocalendar()
    return f"{year}-W{week:02d}"


def _streak(dates: set[str], day: date) -> int:
    n = 0
    while (day - timedelta(days=n)).isoformat() in dates:
        n += 1
    return n


def _summary_for(repo: dict, entry: dict, day: date) -> dict:
    summary = entry.get("summary")
    cached_at = entry.get("summary_date")
    if not (summary and cached_at and (day - date.fromisoformat(cached_at)).days < config.SUMMARY_TTL_DAYS):
        log.info("summarizing %s", repo["full_name"])
        meta = github.get_repo(repo["full_name"])
        readme = github.get_readme_html(repo["full_name"])
        summary = summarize(repo["full_name"], repo["description"], meta, readme)
        entry["summary"] = summary
        entry["summary_date"] = day.isoformat()
    # 還沒翻譯、上次失敗或描述改了才翻譯
    if translate.enabled() and translate.needs_translation(summary, repo["description"]):
        log.info("translating %s", repo["full_name"])
        translate.translate_summary(summary, repo["description"])
    return summary


def _enrich(repos: list[dict], history: dict, day: date, *, record: bool) -> None:
    """補上摘要與上榜資訊。record=True 時把今天記為一次每日上榜。"""
    for repo in repos:
        entry = history["repos"].setdefault(repo["full_name"], {"first_seen": day.isoformat(), "dates": []})
        dates = set(entry["dates"])
        previous = {d for d in dates if d < day.isoformat()}
        if record:
            dates.add(day.isoformat())
            entry["dates"] = sorted(dates)
        repo.update(_summary_for(repo, entry, day))
        repo["first_time"] = not previous
        repo["streak"] = _streak(dates, day)
        repo["appearances"] = len(dates)
        week_ago = (day - timedelta(days=6)).isoformat()
        repo["days_this_week"] = len([d for d in dates if d >= week_ago])
        created = repo.get("created_at", "")[:10]
        repo["is_new_repo"] = bool(created) and (day - date.fromisoformat(created)).days <= 30
        entry["last"] = {k: repo[k] for k in ("description", "language", "stars", "url")}


def build_daily(day: date | None = None) -> dict:
    day = day or today_local()
    repos, source = github.get_trending("daily", config.DAILY_LIMIT)
    history = load_history()
    _enrich(repos, history, day, record=True)
    report = {
        "kind": "daily",
        "id": day.isoformat(),
        "title": f"GitHub Trending 日報 {day.isoformat()}",
        "date": day.isoformat(),
        "generated_at": datetime.now(config.TZ).isoformat(timespec="seconds"),
        "source": source,
        "repos": repos,
    }
    save_json(config.HISTORY_FILE, history)
    save_json(config.DATA_DIR / "daily" / f"{report['id']}.json", report)
    return report


def build_weekly(day: date | None = None) -> dict:
    day = day or today_local()
    repos, source = github.get_trending("weekly", config.WEEKLY_LIMIT)
    history = load_history()
    _enrich(repos, history, day, record=False)

    # 本週最常出現在每日榜的 repo
    week_ago = (day - timedelta(days=6)).isoformat()
    frequent = []
    for name, entry in history["repos"].items():
        days = [d for d in entry.get("dates", []) if week_ago <= d <= day.isoformat()]
        if len(days) >= 2 and entry.get("last"):
            summary = entry.get("summary") or {}
            frequent.append({"full_name": name, "days": len(days), **entry["last"],
                             "description_zh": summary.get("description_zh", ""),
                             "categories": summary.get("categories", [])})
    frequent.sort(key=lambda r: (-r["days"], -r.get("stars", 0)))

    wid = week_id(day)
    report = {
        "kind": "weekly",
        "id": wid,
        "title": f"GitHub Trending 週報 {wid}",
        "date": day.isoformat(),
        "range": f"{(day - timedelta(days=6)).isoformat()} ~ {day.isoformat()}",
        "generated_at": datetime.now(config.TZ).isoformat(timespec="seconds"),
        "source": source,
        "repos": repos,
        "frequent": frequent[:10],
    }
    save_json(config.HISTORY_FILE, history)
    save_json(config.DATA_DIR / "weekly" / f"{wid}.json", report)
    return report


TRANSLATION_KEYS = ("description_zh", "intro_zh", "features_zh", "translated", "translation_version", "description_src")


def backfill_translations() -> int:
    """替既有報告補上翻譯（例如剛設定好 Cloudflare 時）。回傳這次翻譯的 repo 數。"""
    history = load_history()
    count = 0
    for kind in ("daily", "weekly"):
        for path in sorted((config.DATA_DIR / kind).glob("*.json")):
            report = json.loads(path.read_text())
            for repo in report["repos"]:
                summary = (history["repos"].get(repo["full_name"]) or {}).get("summary")
                if not summary:
                    continue
                if translate.enabled() and translate.needs_translation(summary, repo["description"]):
                    log.info("translating %s", repo["full_name"])
                    translate.translate_summary(summary, repo["description"])
                    count += 1
                repo.update({k: summary[k] for k in TRANSLATION_KEYS if k in summary})
            save_json(path, report)
    save_json(config.HISTORY_FILE, history)
    return count


def list_reports(kind: str) -> list[dict]:
    files = sorted((config.DATA_DIR / kind).glob("*.json"), reverse=True)
    return [json.loads(f.read_text()) for f in files]


def latest_report(kind: str) -> dict | None:
    files = sorted((config.DATA_DIR / kind).glob("*.json"))
    return json.loads(files[-1].read_text()) if files else None

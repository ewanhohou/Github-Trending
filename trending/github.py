"""GitHub 網頁與 REST API 的存取。"""
from __future__ import annotations

import logging
import re
import time
from datetime import date, timedelta

import requests
from bs4 import BeautifulSoup

from . import config

log = logging.getLogger(__name__)

_session = requests.Session()
_session.headers["User-Agent"] = config.USER_AGENT


def _get(url: str, *, api: bool = False, accept: str | None = None, params: dict | None = None) -> requests.Response:
    headers = {}
    if api:
        headers["Accept"] = accept or "application/vnd.github+json"
        headers["X-GitHub-Api-Version"] = "2022-11-28"
        if config.GITHUB_TOKEN:
            headers["Authorization"] = f"Bearer {config.GITHUB_TOKEN}"
    for attempt in range(3):
        resp = _session.get(url, headers=headers, params=params, timeout=30)
        if resp.status_code in (429, 502, 503, 504) and attempt < 2:
            time.sleep(5 * (attempt + 1))
            continue
        return resp
    return resp


def _to_int(text: str) -> int:
    digits = re.sub(r"[^\d]", "", text or "")
    return int(digits) if digits else 0


def fetch_trending(since: str = "daily", language: str = "") -> list[dict]:
    """解析 github.com/trending。since: daily | weekly | monthly。"""
    url = "https://github.com/trending" + (f"/{language}" if language else "")
    resp = _get(url, params={"since": since})
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    repos = []
    for rank, row in enumerate(soup.select("article.Box-row"), start=1):
        link = row.select_one("h2 a[href]")
        if not link:
            continue
        full_name = link["href"].strip("/")
        desc = row.select_one("p")
        lang = row.select_one('[itemprop="programmingLanguage"]')
        stars = row.select_one('a[href$="/stargazers"]')
        forks = row.select_one('a[href$="/forks"]')
        period = re.search(r"([\d,]+)\s+stars?\s+(today|this week|this month)", row.get_text(" "))
        repos.append({
            "rank": rank,
            "full_name": full_name,
            "url": f"https://github.com/{full_name}",
            "description": desc.get_text(" ", strip=True) if desc else "",
            "language": lang.get_text(strip=True) if lang else "",
            "stars": _to_int(stars.get_text()) if stars else 0,
            "forks": _to_int(forks.get_text()) if forks else 0,
            "stars_period": _to_int(period.group(1)) if period else 0,
        })
    return repos


def search_fallback(days: int, limit: int) -> list[dict]:
    """Trending 頁面解析失敗時的備案：近 N 天新建、星數最高的 repo。"""
    since = (date.today() - timedelta(days=days)).isoformat()
    resp = _get("https://api.github.com/search/repositories", api=True,
                params={"q": f"created:>{since}", "sort": "stars", "order": "desc", "per_page": limit})
    resp.raise_for_status()
    repos = []
    for rank, item in enumerate(resp.json().get("items", []), start=1):
        repos.append({
            "rank": rank,
            "full_name": item["full_name"],
            "url": item["html_url"],
            "description": item.get("description") or "",
            "language": item.get("language") or "",
            "stars": item.get("stargazers_count", 0),
            "forks": item.get("forks_count", 0),
            "stars_period": 0,
        })
    return repos


def get_trending(since: str, limit: int) -> tuple[list[dict], str]:
    """回傳 (repos, 資料來源)。"""
    try:
        repos = fetch_trending(since)
        if repos:
            return repos[:limit], "trending"
        log.warning("trending page parsed 0 repos, using search fallback")
    except requests.RequestException as e:
        log.warning("trending page failed (%s), using search fallback", e)
    return search_fallback(7 if since == "daily" else 30, limit), "search"


def get_repo(full_name: str) -> dict | None:
    resp = _get(f"https://api.github.com/repos/{full_name}", api=True)
    if resp.status_code != 200:
        log.warning("repo %s: HTTP %s", full_name, resp.status_code)
        return None
    return resp.json()


def get_readme_html(full_name: str) -> str:
    resp = _get(f"https://api.github.com/repos/{full_name}/readme", api=True,
                accept="application/vnd.github.html+json")
    if resp.status_code != 200:
        return ""
    return resp.text

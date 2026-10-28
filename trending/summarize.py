"""不靠 AI 的規則式摘要：從 README 擷取簡介、亮點、圖片，再用關鍵字判斷分類。"""
from __future__ import annotations

import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag

# (中文分類, 關鍵字)。關鍵字以小寫、空白分隔的形式比對；3 個字元以下的短字只比對 topics / 名稱 / 描述，
# 避免在 README 內文誤判。
CATEGORIES: list[tuple[str, list[str]]] = [
    ("AI Agent", ["agent", "agents", "agentic", "mcp", "model context protocol", "claude code", "codex",
                  "copilot", "coding agent", "ai agent", "multi agent", "computer use"]),
    ("大型語言模型 / LLM", ["llm", "llms", "gpt", "chatgpt", "openai", "claude", "gemini", "llama", "rag",
                       "prompt", "prompts", "transformer", "transformers", "inference", "fine tuning",
                       "deepseek", "qwen", "ollama", "vllm", "large language model", "chatbot"]),
    ("機器學習 / 深度學習", ["machine learning", "deep learning", "pytorch", "tensorflow", "neural network",
                      "computer vision", "diffusion", "stable diffusion", "ml", "reinforcement learning",
                      "nlp", "tts", "text to speech", "asr", "speech recognition", "ocr", "jax", "cuda"]),
    ("Web 前端", ["react", "vue", "svelte", "nextjs", "next js", "frontend", "front end", "css", "tailwind",
                "tailwindcss", "ui", "ui components", "component library", "angular", "vite", "web components"]),
    ("後端 / API", ["backend", "api", "rest api", "graphql", "microservices", "grpc", "web framework",
                 "http server", "fastapi", "django", "flask", "express", "spring boot"]),
    ("DevOps / 雲端", ["devops", "kubernetes", "k8s", "docker", "container", "containers", "ci", "terraform",
                     "aws", "azure", "gcp", "serverless", "infrastructure", "monitoring", "observability",
                     "deployment", "cloud native", "helm"]),
    ("資料庫 / 資料工程", ["database", "sql", "postgres", "postgresql", "mysql", "sqlite", "redis",
                     "vector database", "etl", "data pipeline", "analytics", "olap", "duckdb", "data engineering"]),
    ("資訊安全", ["security", "pentest", "pentesting", "penetration testing", "vulnerability", "exploit",
              "malware", "ctf", "osint", "privacy", "encryption", "red team", "cybersecurity", "reverse engineering"]),
    ("行動開發", ["android", "ios", "mobile", "flutter", "react native", "swiftui"]),
    ("開發者工具", ["cli", "terminal", "developer tools", "devtools", "ide", "code editor", "vscode",
               "neovim", "vim", "git", "linter", "compiler", "debugger", "sdk", "tooling", "productivity",
               "command line", "shell"]),
    ("自架服務", ["self hosted", "selfhosted", "homelab", "home assistant", "self host"]),
    ("學習資源 / 清單", ["awesome", "awesome list", "tutorial", "tutorials", "course", "learning", "roadmap",
                   "interview", "book", "books", "guide", "cheatsheet", "education", "resources", "curated list"]),
    ("遊戲 / 圖形", ["game", "games", "game engine", "gamedev", "graphics", "3d", "opengl", "vulkan", "webgl",
                "unity", "godot", "rendering"]),
    ("系統 / 底層", ["os", "kernel", "embedded", "operating system", "wasm", "webassembly", "runtime",
                "virtual machine", "emulator", "firmware", "linux"]),
    ("自動化 / 爬蟲", ["automation", "workflow", "workflows", "scraper", "scraping", "web scraping", "crawler",
                  "bot", "browser automation", "rpa", "n8n", "playwright", "puppeteer"]),
    ("多媒體", ["video", "audio", "music", "image editing", "media", "streaming", "ffmpeg", "media player",
             "image generation", "video generation"]),
    ("區塊鏈 / Web3", ["blockchain", "crypto", "web3", "ethereum", "solana", "bitcoin", "defi", "smart contracts"]),
    ("金融 / 量化", ["trading", "quant", "quantitative", "finance", "stock", "stocks", "backtesting"]),
    ("實用工具", ["downloader", "download", "userscript", "tampermonkey", "browser extension",
              "chrome extension", "utility", "網盤", "网盘", "下載", "下载", "腳本", "脚本"]),
]

KINDS: list[tuple[str, list[str]]] = [
    ("Agent Skills / 提示詞", ["skill", "skills", "agent skills", "system prompts", "prompts", "rules file"]),
    ("資源清單", ["awesome", "curated list", "awesome list", "list of"]),
    ("教學 / 課程", ["tutorial", "course", "learn", "lessons", "book", "roadmap"]),
    ("命令列工具", ["cli", "command line", "command-line", "terminal"]),
    ("外掛 / 擴充套件", ["plugin", "extension", "addon", "add-on"]),
    ("框架", ["framework"]),
    ("函式庫 / SDK", ["library", "sdk", "package", "toolkit"]),
    ("應用程式", ["app", "application", "desktop", "self-hosted", "platform", "client", "ide", "workspace", "editor"]),
]

BADGE_HINTS = [
    "shields.io", "badge", "badgen", "travis-ci", "codecov", "circleci", "coveralls", "star-history",
    "starchart", "contrib.rocks", "repobeats", "komarev", "visitor", "hits.", "github-readme-stats",
    "/workflows/", "buymeacoffee", "ko-fi", "producthunt", "trendshift", "opencollective", "paypal",
    "gitter", "patreon", "sponsor", "deepwiki", "zread", "discord", "trackgit", "api.netlify",
    "readme-typing-svg", "skillicons", "capsule-render", "/avatars/", "avatars.githubusercontent",
    "cc-by", "license", "creativecommons", "licensebuttons",
]

# 這類段落通常不是在介紹專案本身
BOILERPLATE = re.compile(
    r"contribut|pull request|star (us|this)|give .{0,20}star|welcome|sponsor|join (our|the)|discord|"
    r"if you (find|like|are)|^note\b|^warning|^⚠|^important|license|translation|readme in|"
    r"^\[?\d{4}[./-]\d{1,2}|^v?\d+\.\d+(\.\d+)? |release|changelog|news|"
    r"如果您|如果你|注意|贡献|貢獻|欢迎|歡迎|赞助|贊助|加入", re.I)
INSTALL_HEADING = re.compile(r"install|getting started|quick ?start|usage|setup|安裝|安装|快速|使用", re.I)

FEATURE_HEADING = re.compile(
    r"feature|highlight|why\b|what (it|can|does)|key|capabilit|特性|功能|特色|亮點|优势|優勢|特點|特点", re.I)


def _norm(text: str) -> str:
    return " " + re.sub(r"[^a-z0-9一-鿿]+", " ", text.lower()) + " "


def _has(keyword: str, text: str) -> bool:
    if re.search(r"[一-鿿]", keyword):  # 中文沒有空白斷詞，直接子字串比對
        return keyword in text
    return f" {_norm(keyword).strip()} " in text


def _score(keywords: list[str], strong: str, weak: str) -> int:
    score = 0
    for kw in keywords:
        if _has(kw, strong):
            score += 3
        elif len(kw) > 3 and _has(kw, weak):
            score += 1
    return score


def classify(name: str, description: str, topics: list[str], intro: str) -> tuple[list[str], str]:
    """回傳 (分類們, 專案類型)。"""
    own = _norm(" ".join([name.replace("-", " "), description]))
    strong = own + _norm(" ".join(topics))
    weak = _norm(intro)
    scored = sorted(((label, _score(kws, strong, weak)) for label, kws in CATEGORIES), key=lambda s: -s[1])
    categories = [label for label, score in scored if score >= 2][:3]
    if not categories:  # 只在 README 內文命中的弱訊號，最多取兩個
        categories = [label for label, score in scored if score >= 1][:2]

    # 類型優先看名稱與描述，再看 topics、README 簡介
    kind = ""
    for text in (own, strong, weak):
        kind = next((label for label, kws in KINDS if any(_has(k, text) for k in kws)), "")
        if kind:
            break
    return categories, kind


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    cut = text[:limit]
    # 盡量在句號斷開
    for sep in ("。", ". ", "！", "! ", "？", "? "):
        idx = cut.rfind(sep)
        if idx > limit * 0.5:
            return cut[: idx + len(sep)].strip()
    return cut.rstrip() + "…"


def _is_badge(img: Tag) -> bool:
    src = (img.get("data-canonical-src") or img.get("src") or "").lower()
    alt = (img.get("alt") or "").lower()
    if not src or src.startswith("data:"):
        return True
    if any(h in src for h in BADGE_HINTS) or "badge" in alt:
        return True
    for attr in ("width", "height"):
        val = str(img.get(attr, "")).rstrip("px")
        if val.isdigit() and int(val) < 80:
            return True
    return False


def _resolve_image(src: str, full_name: str) -> str:
    if src.startswith("//"):
        return "https:" + src
    if src.startswith(("http://", "https://")):
        if "jwt=" in src:  # private-user-images 的簽名網址幾分鐘就過期
            return ""
        m = re.match(r"https://github\.com/([^/]+/[^/]+)/blob/(.+)", src)
        if m:
            return f"https://raw.githubusercontent.com/{m.group(1)}/{m.group(2)}"
        return src
    return urljoin(f"https://raw.githubusercontent.com/{full_name}/HEAD/", src.lstrip("/"))


def pick_image(soup: BeautifulSoup, full_name: str) -> str:
    raster, vector = [], []
    for img in soup.find_all("img"):
        if _is_badge(img):
            continue
        url = _resolve_image(img.get("src", ""), full_name)
        if not url:
            continue
        canonical = (img.get("data-canonical-src") or url).lower().split("?")[0]
        (vector if canonical.endswith(".svg") else raster).append(url)
    if raster:
        return raster[0]
    if vector:
        return vector[0]
    return ""


def _link_ratio(tag: Tag, text: str) -> float:
    return sum(len(a.get_text()) for a in tag.find_all("a")) / max(len(text), 1)


def _before_install(tag: Tag) -> bool:
    """tag 是否出現在第一個「安裝／使用方式」標題之前。"""
    for heading in tag.find_all_previous(["h2", "h3"]):
        if INSTALL_HEADING.search(heading.get_text()):
            return False
    return True


def _intro(soup: BeautifulSoup, description: str) -> str:
    desc_norm = _norm(description)
    for p in soup.find_all(["p", "blockquote"]):
        if p.find_parent(["table", "details"]) or (p.name == "p" and p.find_parent("blockquote")):
            continue
        text = _clean(p.get_text(" "))
        cjk = len(re.findall(r"[一-鿿]", text))
        if len(text) + cjk < 50:  # 中文字資訊量較高，算兩倍長度
            continue
        if _link_ratio(p, text) > 0.5 or BOILERPLATE.search(text[:80]):
            continue
        if _norm(text) == desc_norm:
            continue
        return _truncate(text, 320)
    return ""


def _list_items(lst: Tag) -> list[str]:
    items = []
    for li in lst.find_all("li", recursive=False)[:6]:
        text = _clean(li.get_text(" "))
        if text:
            items.append(_truncate(text, 140))
    return items


def _features(soup: BeautifulSoup) -> list[str]:
    for heading in soup.find_all(["h2", "h3", "h4"]):
        if not FEATURE_HEADING.search(heading.get_text()):
            continue
        # 標題可能被包在 div.markdown-heading 裡，從外層往後找第一個清單
        anchor = heading.find_parent("div", class_="markdown-heading") or heading
        for sib in anchor.find_next_siblings():
            if sib.name in ("h1", "h2", "h3") or sib.find(["h1", "h2", "h3"]):
                break
            lst = sib if sib.name in ("ul", "ol") else sib.find(["ul", "ol"])
            if lst:
                items = _list_items(lst)
                if items:
                    return items
                break

    # 沒有「Features」標題時，退而取安裝說明之前、看起來像功能說明的第一個清單
    for lst in soup.find_all("ul"):
        if lst.find_parent(["li", "table", "details"]):
            continue
        items = _list_items(lst)
        text = " ".join(items)
        if len(items) < 3 or _link_ratio(lst, text) > 0.4 or not 15 <= len(text) / len(items) <= 160:
            continue
        if not _before_install(lst):
            break
        return items
    return []


def summarize(full_name: str, description: str, repo: dict | None, readme_html: str) -> dict:
    soup = BeautifulSoup(readme_html or "", "html.parser")
    topics = (repo or {}).get("topics", []) or []
    intro = _intro(soup, description)
    categories, kind = classify(full_name.split("/")[-1], description, topics, intro)
    image = pick_image(soup, full_name)
    return {
        "intro": intro,
        "features": _features(soup),
        "categories": categories,
        "kind": kind,
        "topics": topics[:8],
        "image": image,
        "image_is_og": not image,
        "og_image": f"https://opengraph.githubassets.com/1/{full_name}",
        "homepage": (repo or {}).get("homepage") or "",
        "license": ((repo or {}).get("license") or {}).get("spdx_id") or "",
        "created_at": (repo or {}).get("created_at", ""),
        "open_issues": (repo or {}).get("open_issues_count", 0),
        "owner_avatar": ((repo or {}).get("owner") or {}).get("avatar_url", ""),
    }

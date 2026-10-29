import os
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
DOCS_DIR = ROOT / "docs"
TEMPLATES_DIR = ROOT / "templates"
HISTORY_FILE = DATA_DIR / "history.json"

TZ = ZoneInfo("Asia/Taipei")

DAILY_LIMIT = int(os.environ.get("DAILY_LIMIT", "25"))
WEEKLY_LIMIT = int(os.environ.get("WEEKLY_LIMIT", "10"))
NOTIFY_TOP = int(os.environ.get("NOTIFY_TOP", "5"))

# 摘要快取超過幾天就重新抓 README
SUMMARY_TTL_DAYS = 7

PAGES_URL = (os.environ.get("PAGES_URL") or "https://ewanhohou.github.io/Github-Trending/").rstrip("/") + "/"

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
CLOUDFLARE_ACCOUNT_ID = os.environ.get("CLOUDFLARE_ACCOUNT_ID")
CLOUDFLARE_API_TOKEN = os.environ.get("CLOUDFLARE_API_TOKEN")
CLOUDFLARE_AI_MODEL = os.environ.get("CLOUDFLARE_AI_MODEL") or "@cf/google/gemma-4-26b-a4b-it"

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

USER_AGENT = "github-trending-report (+https://github.com/ewanhohou/Github-Trending)"

# 每日精選
PICKS_DIR = DATA_DIR / "picks"
PICK_DEDUPE_DAYS = int(os.environ.get("PICK_DEDUPE_DAYS", "90"))
CLOUDFLARE_IMAGE_MODEL = os.environ.get("CLOUDFLARE_IMAGE_MODEL") or "@cf/black-forest-labs/flux-1-schnell"
# 貼文口吻：優先用 VOICE_PROMPT，其次是本機的 voice.local.md（不進 repo），最後用 templates/voice.md 通用範本
VOICE_PROMPT = os.environ.get("VOICE_PROMPT")
VOICE_LOCAL_FILE = ROOT / "voice.local.md"

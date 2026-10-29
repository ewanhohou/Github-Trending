# GitHub Trending 報告

[English](README.md) | **繁體中文**

[![線上報告](https://img.shields.io/badge/%E7%B7%9A%E4%B8%8A%E5%A0%B1%E5%91%8A-ewanhohou.github.io-2ea44f?logo=github)](https://ewanhohou.github.io/Github-Trending/)
[![Trending report](https://github.com/ewanhohou/Github-Trending/actions/workflows/report.yml/badge.svg)](https://github.com/ewanhohou/Github-Trending/actions/workflows/report.yml)

**👉 每天看今天的熱門 repo：<https://ewanhohou.github.io/Github-Trending/>**

| | 繁體中文 | English |
|---|---|---|
| 首頁 | [所有報告](https://ewanhohou.github.io/Github-Trending/) | [All reports](https://ewanhohou.github.io/Github-Trending/en/) |
| 最新日報 | [daily/latest](https://ewanhohou.github.io/Github-Trending/daily/latest.html) | [en/daily/latest](https://ewanhohou.github.io/Github-Trending/en/daily/latest.html) |
| 最新週報 | [weekly/latest](https://ewanhohou.github.io/Github-Trending/weekly/latest.html) | [en/weekly/latest](https://ewanhohou.github.io/Github-Trending/en/weekly/latest.html) |

每天掃描 [GitHub Trending](https://github.com/trending)，整理每個熱門 repo「是什麼、用在哪、有什麼亮點」並附上圖片，產生網頁報告發佈到 GitHub Pages，再用 Telegram 通知。手機上可以「加入主畫面」當 App 使用。

## 功能

- 每日報告：台北時間 08:30，全語言 Top 25
- 每週精選：每週日 09:00，週榜 Top 10，加上本週最常上每日榜的 repo
- 每日精選：每天挑一個最值得推薦的 repo，90 天內不重複，做成可以直接發 Threads 的圖文送到 Telegram
  - 先用規則取前 5 名（今日星數、AI 相關、首次上榜、新專案加分，清單與教學類扣分），再讓 Workers AI 挑一個並寫推薦理由
  - 1080×1350 深色說明圖（Threads／IG 直式 4:5）：鉤子、是什麼、3 個重點、適合誰，背景由 Workers AI（FLUX）生成
  - Threads 貼文用聊天口吻：開頭鉤子、3 個重點、結尾提問引導留言。貼文只送到 Telegram，不存進 repo、也不放上網站，你發文前別人看不到
  - 口吻依序用 `VOICE_PROMPT` Secret、本機的 `voice.local.md`、通用範本 `templates/voice.md`（見[設定自己的口吻](#設定自己的口吻)）
  - 當天日報最上方與首頁都會顯示，說明圖可以直接下載
- 摘要用規則從 README 擷取，再用 Cloudflare Workers AI 翻成繁體中文：
  - **是什麼**：README 的第一段介紹（會略過 badge、貢獻說明、公告等段落）
  - **用在哪**：依 topics、描述、README 的關鍵字判斷分類（AI Agent、Web 前端、DevOps…）與專案類型
  - **亮點功能**：README 中 Features／Highlights 段落的清單
  - **圖片**：README 中第一張非 badge 的圖片；沒有就用 GitHub 自動產生的預覽圖
- 網頁有繁體中文與英文兩種版本，右上角可以切換：
  - 中文版顯示翻譯，英文原文收在每張卡片的「英文原文」裡；沒設定 Cloudflare 時顯示英文
  - 英文版顯示 README 原文，放在 `/en/` 底下
  - 首頁會記住你選的語言；沒選過的話，瀏覽器不是中文就會開英文版
- 上榜歷史記錄在 `data/history.json`：標示 🆕 首次上榜、🔥 連續上榜天數；同一個 repo 7 天內不重抓 README，翻譯也會快取
- 支援手機閱讀與 PWA：
  - iPhone 用 Safari 分享 → 加入主畫面；Android／桌面 Chrome 會出現「安裝」按鈕
  - 首頁、最新一期日報週報與看過的報告可以離線閱讀，圖片也會快取最近 80 張

## 設定

想自己架一份？Fork 這個 repo 後照下面設定，報告會發佈到 `https://<你的帳號>.github.io/<repo 名稱>/`。

1. **GitHub Pages**：Settings → Pages → Source 選 **GitHub Actions**
2. **Cloudflare Workers AI 翻譯**（Settings → Secrets and variables → Actions → New repository secret）
   - 到 Cloudflare dashboard → AI → Workers AI → **Use REST API**
   - `CLOUDFLARE_API_TOKEN`：選 **Create a Workers AI API Token** 建立
   - `CLOUDFLARE_ACCOUNT_ID`：同一頁的 **Account ID**
   - 免費方案每天 10,000 Neurons，每個 repo 翻譯約用 20 Neurons
   - 設定好之後到 Actions 用 `translate` 跑一次，可以替既有報告補上中文
3. **Telegram 通知**（同樣放在 repo Secrets）
   - `TELEGRAM_BOT_TOKEN`：在 Telegram 找 @BotFather，用 `/newbot` 建立 bot 後取得
   - `TELEGRAM_CHAT_ID`：先傳任意訊息給你的 bot，再開啟
     `https://api.telegram.org/bot<TOKEN>/getUpdates`，回應裡的 `message.chat.id` 就是
   - 沒設定的話流程照常跑，只是不發通知
   - 每日精選是第二則訊息：說明圖加上貼文，貼文放在有「複製」按鈕的區塊裡
4. 到 Actions → Trending report → Run workflow 手動跑一次確認

Public repo 使用 GitHub Actions 不計費，每次執行約 1～2 分鐘。

## 環境變數

在 GitHub Actions 裡，標示「Secret」的要放在 repo Secrets，其他的 workflow 已經設好。本機執行時用一般的環境變數設定。

| 變數 | 用途 | 預設值 | 沒設定時 |
|---|---|---|---|
| `GITHUB_TOKEN` | 呼叫 GitHub API 取得 repo 資訊與 README。也可以用 `GH_TOKEN`。Actions 會自動提供；本機可用 `$(gh auth token)` | — | 未登入的 API 每小時只有 60 次，一份報告就可能用完 |
| `CLOUDFLARE_ACCOUNT_ID` | Secret。Cloudflare 帳號 ID，用來呼叫 Workers AI 翻譯 | — | 不翻譯，中文版也顯示英文 |
| `CLOUDFLARE_API_TOKEN` | Secret。有 Workers AI 權限的 Cloudflare API token | — | 同上 |
| `CLOUDFLARE_AI_MODEL` | 翻譯用的 Workers AI 模型 | `@cf/google/gemma-4-26b-a4b-it` | 用預設模型 |
| `TELEGRAM_BOT_TOKEN` | Secret。發送通知的 Telegram bot token，向 @BotFather 取得 | — | 不發通知，只把訊息印在 log |
| `TELEGRAM_CHAT_ID` | Secret。通知要送到的聊天室 ID（個人、群組或頻道） | — | 同上 |
| `PAGES_URL` | 網站的公開網址，用在通知裡的報告連結與網頁的語言對照連結。Actions 會依 repo 自動設定 | `https://ewanhohou.github.io/Github-Trending/` | 用預設網址 |
| `DAILY_LIMIT` | 每日報告收錄幾個 repo | `25` | 用預設值 |
| `WEEKLY_LIMIT` | 每週精選收錄幾個 repo | `10` | 用預設值 |
| `NOTIFY_TOP` | Telegram 通知列出前幾名 | `5` | 用預設值 |
| `PICK_DEDUPE_DAYS` | 每日精選幾天內不重複 | `90` | 用預設值 |
| `CLOUDFLARE_IMAGE_MODEL` | 產生說明圖背景的 Workers AI 模型 | `@cf/black-forest-labs/flux-1-schnell` | 用預設模型 |
| `VOICE_PROMPT` | Secret，選填。你自己的 Threads 貼文口吻說明，不會出現在公開的 repo | — | 有 `voice.local.md` 就用它，否則用 `templates/voice.md` |

## 設定自己的口吻

`templates/voice.md` 是通用範本。想用自己的口吻又不公開：

1. 把範本複製成 repo 根目錄的 `voice.local.md`（已列在 `.gitignore`）再修改，本機執行會自動使用
2. 上傳成 `VOICE_PROMPT` Secret，讓 Actions 也用它：

   ```bash
   gh secret set VOICE_PROMPT < voice.local.md
   ```

3. 之後每次修改再執行一次上面的指令，下一次執行就會套用。想馬上試：Actions → Run workflow → 選 `pick`

## 本機執行

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
GITHUB_TOKEN=$(gh auth token) .venv/bin/python -m trending daily --no-notify
.venv/bin/python -m trending pick --no-notify   # 說明圖用本機安裝的 Google Chrome 截圖
.venv/bin/python -m http.server 8790 --directory docs
```

| 指令 | 說明 |
|---|---|
| `python -m trending daily [--no-notify]` | 產生今日報告、重建網頁、發通知 |
| `python -m trending weekly [--no-notify]` | 產生本週精選 |
| `python -m trending pick [--no-notify] [--redo] [--render-only]` | 挑今天的每日精選並產生說明圖與貼文。`--redo` 重新挑選，`--render-only` 只重畫說明圖 |
| `python -m trending render` | 只依 `data/` 重建網頁（改模板後用） |
| `python -m trending translate` | 替既有報告補上中文翻譯並重建網頁 |
| `python -m trending notify daily\|weekly\|pick` | 傳送最新一份報告或每日精選的通知 |

## 結構

```
trending/
  github.py     # 解析 Trending 頁面（失敗時改用 Search API）、呼叫 GitHub API
  summarize.py  # 規則式摘要、分類、選圖
  translate.py  # Cloudflare Workers AI 翻譯
  report.py     # 產生報告 JSON、維護上榜歷史
  pick.py       # 每日精選：挑選、說明圖文案、Threads 貼文、AI 背景圖、說明圖
  i18n.py       # 網頁介面文字與分類名稱的中英對照
  render.py     # 輸出 docs/ 網頁（中文在根目錄，英文在 docs/en/）
  notify.py     # Telegram 通知
templates/      # Jinja2 模板、CSS、service worker（sw.js）、App 圖示（static/）、
                #   說明圖版面（card.html）與貼文口吻（voice.md）
data/           # 報告 JSON、每日精選（picks/）與歷史（由 Actions 自動 commit）
docs/           # 產生的網頁
```

要加其他語言：在 `trending/i18n.py` 的 `LANGS`、`STRINGS`、`LABELS` 各加一組，網頁會輸出到 `docs/<語言>/`。
